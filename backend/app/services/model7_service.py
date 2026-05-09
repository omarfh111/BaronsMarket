from __future__ import annotations

import io
import json
import re
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import cv2
import easyocr
import numpy as np
import torch
import torch.nn as nn
from PIL import Image
from torchvision import models, transforms

from app.core.config import settings
from app.services.device import easyocr_gpu_enabled, torch_device


def _resolve_path(path: Path) -> Path:
    if path.is_absolute():
        return path
    backend_root = Path(__file__).resolve().parents[2]
    return (backend_root / path).resolve()


class FidelityCardService:
    def __init__(self) -> None:
        self._load_error: str | None = None
        self._checkpoint_path = _resolve_path(settings.model7_checkpoint_path)
        self._db_path = _resolve_path(settings.model7_db_json_path)
        self._threshold = float(settings.model7_cnn_threshold)
        self._classes = ["fake", "real"]
        self._device = torch.device(torch_device())
        self._transform = transforms.Compose(
            [
                transforms.Resize((224, 224)),
                transforms.ToTensor(),
                transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
            ]
        )
        self._reader = None
        self._model = None
        self._db: dict[str, dict[str, Any]] = {}
        self._init()

    def _init(self) -> None:
        if not self._checkpoint_path.exists():
            self._load_error = f"Model 7 checkpoint not found: {self._checkpoint_path}"
            return
        if not self._db_path.exists():
            self._load_error = f"Fidelity DB not found: {self._db_path}"
            return

        with self._db_path.open("r", encoding="utf-8") as f:
            raw = json.load(f)
        if isinstance(raw, dict):
            self._db = {str(k).upper(): v for k, v in raw.items()}
        else:
            self._load_error = "Fidelity DB format is invalid."
            return

        model = self._build_model()
        ckpt = torch.load(self._checkpoint_path, map_location=self._device, weights_only=False)
        state_dict = ckpt.get("state_dict", ckpt) if isinstance(ckpt, dict) else ckpt
        model.load_state_dict(state_dict, strict=False)
        model.to(self._device)
        model.eval()
        self._model = model

        self._reader = easyocr.Reader(["fr", "en"], gpu=easyocr_gpu_enabled())

    @staticmethod
    def _build_model() -> nn.Module:
        model = models.efficientnet_b0(weights=None)
        in_features = model.classifier[1].in_features
        model.classifier = nn.Sequential(
            nn.Dropout(0.3),
            nn.Linear(in_features, 256),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(256, 2),
        )
        return model

    def _cnn_predict(self, image: Image.Image) -> tuple[str, float]:
        x = self._transform(image.convert("RGB")).unsqueeze(0).to(self._device)
        with torch.no_grad():
            probs = torch.softmax(self._model(x), dim=1).detach().cpu().numpy()[0]
        idx = int(np.argmax(probs))
        return self._classes[idx], float(probs[idx])

    @staticmethod
    def _preprocess_clahe(img_bgr: np.ndarray) -> np.ndarray:
        lab = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        l2 = clahe.apply(l)
        merged = cv2.merge([l2, a, b])
        return cv2.cvtColor(merged, cv2.COLOR_LAB2BGR)

    @staticmethod
    def _preprocess_adaptive(img_bgr: np.ndarray) -> np.ndarray:
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        up = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        thr = cv2.adaptiveThreshold(up, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 7)
        return cv2.cvtColor(thr, cv2.COLOR_GRAY2BGR)

    @staticmethod
    def _preprocess_sharpen(img_bgr: np.ndarray) -> np.ndarray:
        kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]], dtype=np.float32)
        return cv2.filter2D(img_bgr, -1, kernel)

    @staticmethod
    def _clean_text(text: str) -> str:
        t = re.sub(r"\s+", " ", text or "").strip()
        return t.upper()

    def _ocr_multipass(self, image_bgr: np.ndarray) -> tuple[str, str]:
        passes = [
            ("CLAHE", self._preprocess_clahe),
            ("Adaptive", self._preprocess_adaptive),
            ("Sharpen", self._preprocess_sharpen),
        ]
        best_text = ""
        best_pass = "fallback"
        for name, fn in passes:
            processed = fn(image_bgr)
            raw = self._reader.readtext(processed, detail=0) if self._reader else []
            text = self._clean_text(" ".join(raw))
            if len(text) > len(best_text):
                best_text = text
                best_pass = name
            if re.search(r"MNP[-\s]?\d{8}", text):
                return text, name
        return best_text, best_pass

    @staticmethod
    def _extract_fields(text: str) -> dict[str, str | None]:
        fields: dict[str, str | None] = {"card_id": None, "expiry": None}
        m_id = re.search(r"MNP[-\s]?(\d{8})", text)
        if m_id:
            fields["card_id"] = f"MNP-{m_id.group(1)}"
        m_exp = re.search(r"(0[1-9]|1[0-2])[\/\-](20\d{2})", text)
        if m_exp:
            fields["expiry"] = f"{m_exp.group(1)}/{m_exp.group(2)}"
        return fields

    @staticmethod
    def _parse_expiry(expiry: str | None) -> datetime | None:
        if not expiry:
            return None
        m = re.match(r"(0[1-9]|1[0-2])[\/\-](20\d{2})$", expiry.strip())
        if not m:
            return None
        month = int(m.group(1))
        year = int(m.group(2))
        return datetime(year, month, 1)

    def _find_card(self, card_id: str) -> tuple[str | None, dict[str, Any] | None]:
        normalized = card_id.upper().strip()
        if normalized in self._db:
            return normalized, self._db[normalized]

        best_key = None
        best_score = 0.0
        for key in self._db.keys():
            score = SequenceMatcher(None, normalized, key).ratio()
            if score > best_score:
                best_key = key
                best_score = score
        if best_key and best_score >= 0.88:
            return best_key, self._db[best_key]
        return None, None

    def verify(self, image_bytes: bytes) -> dict[str, Any]:
        if self._load_error:
            return {"valid": False, "discount_percent": 0, "message": self._load_error}
        if self._model is None:
            return {"valid": False, "discount_percent": 0, "message": "Model 7 is not initialized."}

        pil_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        cnn_class, cnn_conf = self._cnn_predict(pil_image)
        if cnn_class == "fake" and cnn_conf >= self._threshold:
            return {
                "valid": False,
                "discount_percent": 0,
                "message": f"Carte rejetee: detectee comme FAKE ({cnn_conf:.2%})",
                "card_id": None,
                "customer_name": None,
                "cnn_class": cnn_class,
                "cnn_confidence": round(cnn_conf, 4),
                "ocr_pass": None,
            }

        bgr = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
        text, ocr_pass = self._ocr_multipass(bgr)
        fields = self._extract_fields(text)
        card_id = fields.get("card_id")
        if not card_id:
            return {
                "valid": False,
                "discount_percent": 0,
                "message": "Carte rejetee: card_id introuvable (format MNP-XXXXXXXX).",
                "card_id": None,
                "customer_name": None,
                "cnn_class": cnn_class,
                "cnn_confidence": round(cnn_conf, 4),
                "ocr_pass": ocr_pass,
            }

        matched_id, card_data = self._find_card(card_id)
        if not matched_id or not card_data:
            return {
                "valid": False,
                "discount_percent": 0,
                "message": f"Carte rejetee: {card_id} absente de la base.",
                "card_id": card_id,
                "customer_name": None,
                "cnn_class": cnn_class,
                "cnn_confidence": round(cnn_conf, 4),
                "ocr_pass": ocr_pass,
            }

        status = str(card_data.get("status", "")).upper().strip()
        if status not in {"ACTIF", "ACTIVE"}:
            return {
                "valid": False,
                "discount_percent": 0,
                "message": f"Carte rejetee: statut {status}.",
                "card_id": matched_id,
                "customer_name": card_data.get("name"),
                "cnn_class": cnn_class,
                "cnn_confidence": round(cnn_conf, 4),
                "ocr_pass": ocr_pass,
            }

        expiry_str = str(card_data.get("expiry", "")).strip()
        exp = self._parse_expiry(expiry_str)
        now = datetime.utcnow().replace(day=1)
        if exp is not None and exp < now:
            return {
                "valid": False,
                "discount_percent": 0,
                "message": f"Carte rejetee: expiree ({expiry_str}).",
                "card_id": matched_id,
                "customer_name": card_data.get("name"),
                "cnn_class": cnn_class,
                "cnn_confidence": round(cnn_conf, 4),
                "ocr_pass": ocr_pass,
            }

        customer_name = str(card_data.get("name", "Client Fidelite"))
        return {
            "valid": True,
            "discount_percent": 10,
            "message": f"Carte acceptee. Bienvenue {customer_name} - remise 10% appliquee.",
            "card_id": matched_id,
            "customer_name": customer_name,
            "cnn_class": cnn_class,
            "cnn_confidence": round(cnn_conf, 4),
            "ocr_pass": ocr_pass,
        }


fidelity_card_service = FidelityCardService()
