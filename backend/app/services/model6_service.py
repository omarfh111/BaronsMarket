from __future__ import annotations

import io
import pathlib
import pickle
from pathlib import Path
from typing import Dict

import torch
from torchvision import models, transforms
from PIL import Image

from app.core.config import settings


def _resolve_path(path: Path) -> Path:
    if path.is_absolute():
        return path
    backend_root = Path(__file__).resolve().parents[2]
    return (backend_root / path).resolve()


class VegetableFreshnessService:
    def __init__(self) -> None:
        self.model = None
        self.resize_to = 256
        self.crop_to = 224
        self.norm_mean = [0.485, 0.456, 0.406]
        self.norm_std = [0.229, 0.224, 0.225]
        self.idx_to_label = {0: "Healthy", 1: "Rotten"}
        self._load_error: str | None = None
        self._init_model()

    def _init_model(self) -> None:
        model_path = _resolve_path(settings.model6_weights_path)
        if not model_path.exists():
            self._load_error = f"Vegetable freshness model not found: {model_path}"
            return

        self._load_pipeline_state()

        model = models.mobilenet_v3_large(weights=None)
        in_features = model.classifier[-1].in_features
        model.classifier[-1] = torch.nn.Linear(in_features, 1)

        checkpoint = torch.load(model_path, map_location="cpu", weights_only=False)
        if isinstance(checkpoint, dict) and "state_dict" in checkpoint:
            state_dict = checkpoint["state_dict"]
        elif isinstance(checkpoint, dict):
            state_dict = checkpoint
        else:
            self._load_error = "Invalid checkpoint format for model_6."
            return

        cleaned_state: dict[str, torch.Tensor] = {}
        for key, value in state_dict.items():
            new_key = key[7:] if str(key).startswith("module.") else str(key)
            cleaned_state[new_key] = value

        model.load_state_dict(cleaned_state, strict=True)
        model.eval()
        self.model = model

    def _load_pipeline_state(self) -> None:
        pipeline_path = _resolve_path(settings.model6_pipeline_state_path)
        if not pipeline_path.exists():
            return
        try:
            # Compatibility for pipeline pickles created on Linux.
            pathlib.PosixPath = pathlib.WindowsPath  # type: ignore[misc,assignment]
            with pipeline_path.open("rb") as f:
                state = pickle.load(f)
            if not isinstance(state, dict):
                return
            self.resize_to = int(state.get("resize_to", self.resize_to))
            self.crop_to = int(state.get("crop_to", self.crop_to))
            mean = state.get("norm_mean")
            std = state.get("norm_std")
            if isinstance(mean, (list, tuple)) and len(mean) == 3:
                self.norm_mean = [float(v) for v in mean]
            if isinstance(std, (list, tuple)) and len(std) == 3:
                self.norm_std = [float(v) for v in std]
            label_map = state.get("label_map", {})
            if isinstance(label_map, dict) and label_map:
                self.idx_to_label = {int(v): str(k) for k, v in label_map.items()}
        except Exception:
            return

    def predict(self, image_bytes: bytes) -> Dict[str, object]:
        if self.model is None:
            if self._load_error:
                raise FileNotFoundError(self._load_error)
            raise RuntimeError("Vegetable freshness model is not initialized.")

        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        preprocess = transforms.Compose(
            [
                transforms.Resize(self.resize_to),
                transforms.CenterCrop(self.crop_to),
                transforms.ToTensor(),
                transforms.Normalize(mean=self.norm_mean, std=self.norm_std),
            ]
        )
        x = preprocess(image).unsqueeze(0)

        with torch.inference_mode():
            logit = self.model(x).squeeze().float()
            rotten_prob = torch.sigmoid(logit).item()

        healthy_prob = 1.0 - rotten_prob
        probabilities: Dict[str, float] = {
            "Healthy": round(float(healthy_prob), 6),
            "Rotten": round(float(rotten_prob), 6),
        }
        is_rotten = rotten_prob > 0.5
        best_idx = 1 if is_rotten else 0
        best_label = self.idx_to_label.get(best_idx, "Rotten" if is_rotten else "Healthy")
        best_conf = rotten_prob if is_rotten else healthy_prob

        return {
            "label": str(best_label),
            "confidence": round(float(best_conf), 6),
            "probabilities": probabilities,
        }


vegetable_freshness_service = VegetableFreshnessService()
