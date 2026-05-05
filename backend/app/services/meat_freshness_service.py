from __future__ import annotations

import io
from pathlib import Path
from typing import Dict, List

import timm
import torch
import torch.nn as nn
from PIL import Image
from torchvision import transforms


def _resolve_path(path: Path) -> Path:
    if path.is_absolute():
        return path
    backend_root = Path(__file__).resolve().parents[2]
    return (backend_root / path).resolve()


class MeatFreshnessNet(nn.Module):
    def __init__(self, num_classes: int = 3) -> None:
        super().__init__()
        self.backbone = timm.create_model("efficientnet_b0", pretrained=False, num_classes=0)
        self.classifier = nn.Sequential(
            nn.Linear(1280, 512),
            nn.LayerNorm(512),
            nn.ReLU(inplace=True),
            nn.Dropout(0.4),
            nn.Linear(512, 256),
            nn.LayerNorm(256),
            nn.ReLU(inplace=True),
            nn.Dropout(0.3),
            nn.Linear(256, num_classes),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        features = self.backbone(x)
        return self.classifier(features)


class MeatFreshnessService:
    def __init__(self) -> None:
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.labels: List[str] = ["Fresh", "Half-Fresh", "Spoiled"]
        self.model = MeatFreshnessNet(num_classes=len(self.labels)).to(self.device)
        self.model.eval()

        model_path = _resolve_path(Path("../model/model_2/best_model_meat_freshness_detection_Efficent_Net.pth"))
        if not model_path.exists():
            raise FileNotFoundError(f"Meat freshness model not found: {model_path}")

        checkpoint = torch.load(str(model_path), map_location=self.device)
        if isinstance(checkpoint, dict):
            if "model_state_dict" in checkpoint:
                state_dict = checkpoint["model_state_dict"]
            elif "state_dict" in checkpoint:
                state_dict = checkpoint["state_dict"]
            else:
                state_dict = checkpoint
        else:
            state_dict = checkpoint

        cleaned = {}
        for key, value in state_dict.items():
            cleaned[key.replace("module.", "")] = value
        self.model.load_state_dict(cleaned, strict=True)

        self.transform = transforms.Compose(
            [
                transforms.Resize((224, 224)),
                transforms.ToTensor(),
                transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
            ]
        )

    def predict(self, image_bytes: bytes) -> Dict[str, object]:
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        tensor = self.transform(image).unsqueeze(0).to(self.device)

        with torch.no_grad():
            logits = self.model(tensor)
            probs = torch.softmax(logits, dim=1).squeeze(0).detach().cpu().tolist()

        best_idx = max(range(len(probs)), key=lambda idx: probs[idx])
        probabilities = {self.labels[idx]: round(float(probs[idx]), 6) for idx in range(len(self.labels))}

        return {
            "label": self.labels[best_idx],
            "confidence": round(float(probs[best_idx]), 6),
            "probabilities": probabilities,
        }


meat_freshness_service = MeatFreshnessService()

