import io
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List

import faiss
import numpy as np
import torch
from PIL import Image
from transformers import CLIPModel, CLIPProcessor

_ultralytics_config_dir = Path(__file__).resolve().parents[2] / "outputs" / "ultralytics"
_ultralytics_config_dir.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("YOLO_CONFIG_DIR", str(_ultralytics_config_dir))

from ultralytics import YOLO

from app.core.config import settings
from app.services.device import torch_device, yolo_device


def _resolve_path(path: Path) -> Path:
    if path.is_absolute():
        return path
    backend_root = Path(__file__).resolve().parents[2]
    return (backend_root / path).resolve()


class ProductRetrievalService:
    def __init__(self) -> None:
        self.device = torch_device()
        self.yolo_device = yolo_device()

        self.yolo_model = YOLO(str(_resolve_path(settings.yolo_model_path)))
        clip_model_id = "openai/clip-vit-base-patch32"
        self.clip_processor = CLIPProcessor.from_pretrained(clip_model_id)
        # Transformers blocks torch.load on torch<2.6 for CVE-2025-32434.
        # The official CLIP checkpoint provides safetensors, so we load that
        # format explicitly and avoid the unsafe pickle-based path.
        self.clip_model = CLIPModel.from_pretrained(clip_model_id, use_safetensors=True).to(self.device)
        self.clip_model.eval()

        index_path = _resolve_path(settings.faiss_index_path)
        self.faiss_index = faiss.read_index(str(index_path))

        emb_path = _resolve_path(settings.product_embeddings_path)
        self.product_embeddings = np.load(str(emb_path)).astype(np.float32)

        self.products = self._load_products()
        self.product_id_to_pos = self._build_product_id_map()
        self.image_paths = self._load_image_paths()
        self.aug_factor = self._infer_aug_factor()
        self.embedding_to_product = self._build_embedding_to_product_map()
        self.product_centroid_index, self.product_centroids = self._build_product_centroid_index()

    def _load_products(self) -> List[Dict[str, Any]]:
        candidate = _resolve_path(settings.products_json_path)
        if candidate.exists():
            with candidate.open("r", encoding="utf-8") as handle:
                content = json.load(handle)
                return content["products"] if isinstance(content, dict) and "products" in content else content

        model_dir = _resolve_path(settings.model_dir)
        json_candidates = sorted(model_dir.glob("products_clean*.json"))
        if not json_candidates:
            raise FileNotFoundError(f"Could not find product metadata in: {model_dir}")
        with json_candidates[0].open("r", encoding="utf-8") as handle:
            content = json.load(handle)
            return content["products"] if isinstance(content, dict) and "products" in content else content

    def _build_product_id_map(self) -> Dict[int, int]:
        mapping: Dict[int, int] = {}
        for pos, product in enumerate(self.products):
            raw_id = product.get("id")
            if isinstance(raw_id, (int, float)):
                mapping[int(raw_id)] = pos
        return mapping

    def _load_image_paths(self) -> List[str]:
        image_paths_file = _resolve_path(settings.model_dir) / "image_paths_aug.txt"
        if not image_paths_file.exists():
            return []
        return image_paths_file.read_text(encoding="utf-8", errors="ignore").splitlines()

    def _infer_aug_factor(self) -> int:
        if not self.image_paths or not self.products:
            return 1
        if len(self.image_paths) % len(self.products) == 0:
            return max(1, len(self.image_paths) // len(self.products))
        if len(self.product_embeddings) % len(self.products) == 0:
            return max(1, len(self.product_embeddings) // len(self.products))
        return 1

    def _build_embedding_to_product_map(self) -> np.ndarray:
        total = len(self.product_embeddings)
        mapping = np.full(total, -1, dtype=np.int32)

        # Primary mapping strategy:
        # augmented embeddings are contiguous by product in groups (usually x4).
        if self.aug_factor > 1:
            for emb_idx in range(total):
                prod_pos = emb_idx // self.aug_factor
                if 0 <= prod_pos < len(self.products):
                    mapping[emb_idx] = prod_pos

        # Secondary override (when available):
        # use product_<id>.jpg from image_paths and match id in products json.
        if self.image_paths:
            rx = re.compile(r"product_(\d+)\.jpg$")
            for emb_idx, raw_path in enumerate(self.image_paths[:total]):
                match = rx.search(raw_path)
                if not match:
                    continue
                product_id = int(match.group(1))
                if product_id in self.product_id_to_pos:
                    mapping[emb_idx] = self.product_id_to_pos[product_id]

        # Final fallback: clamp unresolved positions by index.
        unresolved = np.where(mapping < 0)[0]
        for emb_idx in unresolved:
            mapping[emb_idx] = min(emb_idx, len(self.products) - 1)
        return mapping

    def _build_product_centroid_index(self) -> tuple[faiss.Index, np.ndarray]:
        product_count = len(self.products)
        emb_dim = int(self.product_embeddings.shape[1])
        centroids = np.zeros((product_count, emb_dim), dtype=np.float32)
        counts = np.zeros((product_count,), dtype=np.int32)

        for emb_idx, prod_idx in enumerate(self.embedding_to_product):
            if 0 <= prod_idx < product_count:
                centroids[prod_idx] += self.product_embeddings[emb_idx].astype(np.float32)
                counts[prod_idx] += 1

        valid = counts > 0
        centroids[valid] /= counts[valid, None].astype(np.float32)

        norms = np.linalg.norm(centroids, axis=1, keepdims=True)
        centroids = centroids / np.clip(norms, 1e-12, None)

        index = faiss.IndexFlatIP(emb_dim)
        index.add(centroids.astype(np.float32))
        return index, centroids

    @staticmethod
    def _safe_crop(image: Image.Image, box: np.ndarray) -> Image.Image:
        width, height = image.size
        x1, y1, x2, y2 = box.astype(int).tolist()
        x1 = max(0, min(x1, width - 1))
        y1 = max(0, min(y1, height - 1))
        x2 = max(x1 + 1, min(x2, width))
        y2 = max(y1 + 1, min(y2, height))
        return image.crop((x1, y1, x2, y2))

    def _encode_image(self, image: Image.Image) -> np.ndarray:
        inputs = self.clip_processor(images=image, return_tensors="pt").to(self.device)
        with torch.no_grad():
            image_features = self.clip_model.get_image_features(**inputs)
        vector = image_features.detach().cpu().numpy().astype(np.float32)
        norms = np.linalg.norm(vector, axis=1, keepdims=True)
        return vector / np.clip(norms, 1e-12, None)

    @staticmethod
    def _pick_value(item: Dict[str, Any], keys: List[str], fallback: Any) -> Any:
        for key in keys:
            if key in item and item[key] is not None:
                return item[key]
        return fallback

    def _normalize_product(self, raw: Dict[str, Any], similarity: float, detector_conf: float) -> Dict[str, Any]:
        name = str(self._pick_value(raw, ["name", "product_name", "title"], "Unknown Product"))
        brand = str(self._pick_value(raw, ["brand", "manufacturer"], "Unknown Brand"))
        price_raw = self._pick_value(raw, ["price", "unit_price"], 0.0)
        image = str(self._pick_value(raw, ["image", "image_url", "thumbnail"], ""))
        price = self._parse_price(price_raw)
        return {
            "name": name,
            "brand": brand,
            "price": round(price, 2),
            "image": image,
            "confidence": round(float(similarity), 4),
            "detector_confidence": round(float(detector_conf), 4),
        }

    @staticmethod
    def _parse_price(price_raw: Any) -> float:
        if isinstance(price_raw, (int, float)):
            return float(price_raw)
        if price_raw is None:
            return 0.0

        text = str(price_raw).strip().replace("\u00a0", " ").replace("DT", "").strip()
        text = re.sub(r"[^\d,.\-]", "", text)
        if not text:
            return 0.0

        # Handle mixed separators by treating the right-most separator as decimal.
        last_comma = text.rfind(",")
        last_dot = text.rfind(".")
        if last_comma > -1 and last_dot > -1:
            decimal_sep = "," if last_comma > last_dot else "."
            thousands_sep = "." if decimal_sep == "," else ","
            text = text.replace(thousands_sep, "")
            text = text.replace(decimal_sep, ".")
        else:
            text = text.replace(",", ".")

        try:
            return float(text)
        except ValueError:
            return 0.0

    @staticmethod
    def _score_to_similarity(score: float) -> float:
        # Convert cosine/IP score in [-1, 1] to [0, 1] for UI readability.
        return max(0.0, min(1.0, (score + 1.0) / 2.0))

    def _retrieve_candidates(
        self,
        query_embedding: np.ndarray,
        requested_k: int,
        detector_conf: float,
    ) -> List[Dict[str, Any]]:
        search_k = min(max(requested_k, 1), len(self.products))
        scores, indices = self.product_centroid_index.search(query_embedding, search_k)

        predictions: List[Dict[str, Any]] = []
        for score, product_idx in zip(scores[0], indices[0]):
            if product_idx < 0 or product_idx >= len(self.products):
                continue
            similarity = self._score_to_similarity(float(score))
            predictions.append(self._normalize_product(self.products[product_idx], similarity, detector_conf))
            if len(predictions) >= requested_k:
                break
        return predictions

    def detect_and_retrieve(self, image_bytes: bytes, top_k: int | None = None) -> List[Dict[str, Any]]:
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

        results = self.yolo_model.predict(
            image,
            conf=settings.yolo_confidence,
            device=self.yolo_device,
            verbose=False,
        )
        requested_k = max(1, top_k or settings.top_k)
        if not results:
            query_embedding = self._encode_image(image)
            return self._retrieve_candidates(query_embedding, requested_k=requested_k, detector_conf=0.0)

        boxes = results[0].boxes
        if boxes is None or len(boxes) == 0:
            query_embedding = self._encode_image(image)
            return self._retrieve_candidates(query_embedding, requested_k=requested_k, detector_conf=0.0)

        # Evaluate detections by confidence; keep best retrieval result.
        confs = boxes.conf.detach().cpu().numpy()
        box_coords = boxes.xyxy.detach().cpu().numpy()
        ordered = np.argsort(-confs)

        best_predictions: List[Dict[str, Any]] = []
        best_score = -1.0
        for box_idx in ordered[: min(3, len(ordered))]:
            detector_conf = float(confs[box_idx])
            crop = self._safe_crop(image, box_coords[box_idx])
            query_embedding = self._encode_image(crop)
            preds = self._retrieve_candidates(query_embedding, requested_k=requested_k, detector_conf=detector_conf)
            if not preds:
                continue
            score = float(preds[0].get("confidence") or 0.0) + detector_conf
            if score > best_score:
                best_score = score
                best_predictions = preds

        if best_predictions:
            return best_predictions

        # Final fallback on full image embedding.
        query_embedding = self._encode_image(image)
        return self._retrieve_candidates(query_embedding, requested_k=requested_k, detector_conf=0.0)


product_retrieval_service = ProductRetrievalService()

