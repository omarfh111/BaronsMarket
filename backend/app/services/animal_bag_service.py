from __future__ import annotations

import base64
import io
import tempfile
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import torch
import torch.nn as nn
from PIL import Image
from torchvision import transforms
from torchvision.models import efficientnet_b0

from app.core.config import settings
from app.services.device import torch_device


def _resolve_path(path: Path) -> Path:
    if path.is_absolute():
        return path
    backend_root = Path(__file__).resolve().parents[2]
    return (backend_root / path).resolve()


class AnimalBagService:
    def __init__(self) -> None:
        self.device = torch_device()
        self.labels = ["animal", "bag"]
        self.model = self._build_model().to(self.device)
        self.model.eval()
        self.transform = transforms.Compose(
            [
                transforms.Resize((settings.model3_image_size, settings.model3_image_size)),
                transforms.ToTensor(),
                transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
            ]
        )
        self._last_conv_activations: torch.Tensor | None = None
        self._last_conv_grads: torch.Tensor | None = None
        self._register_hooks()

    def _register_hooks(self) -> None:
        def forward_hook(_module, _inp, output):
            self._last_conv_activations = output

        def backward_hook(_module, grad_input, grad_output):
            _ = grad_input
            self._last_conv_grads = grad_output[0]

        # EfficientNetB0 last feature block
        target_layer = self.model.features[-1]
        target_layer.register_forward_hook(forward_hook)
        target_layer.register_full_backward_hook(backward_hook)

    def _build_model(self) -> nn.Module:
        model = efficientnet_b0(weights=None)
        in_features = model.classifier[1].in_features
        model.classifier[1] = nn.Sequential(
            nn.Linear(in_features, 256),
            nn.ReLU(inplace=True),
            nn.Dropout(0.4),
            nn.Linear(256, 2),
        )

        weights_path = _resolve_path(settings.model3_weights_path)
        if not weights_path.exists():
            raise FileNotFoundError(f"Model 3 weights not found: {weights_path}")

        checkpoint = torch.load(str(weights_path), map_location=self.device)
        if isinstance(checkpoint, dict):
            if "model_state_dict" in checkpoint:
                state_dict = checkpoint["model_state_dict"]
            elif "state_dict" in checkpoint:
                state_dict = checkpoint["state_dict"]
            else:
                state_dict = checkpoint
        else:
            state_dict = checkpoint

        cleaned = {str(k).replace("module.", ""): v for k, v in state_dict.items()}
        model.load_state_dict(cleaned, strict=True)
        return model

    def _encode_data_url_jpg(self, bgr_img: np.ndarray) -> str:
        ok, encoded = cv2.imencode(".jpg", bgr_img)
        if not ok:
            return ""
        return "data:image/jpeg;base64," + base64.b64encode(encoded.tobytes()).decode("utf-8")

    def _gradcam_bbox(self, image_rgb: np.ndarray, class_idx: int) -> tuple[list[int], str]:
        self.model.zero_grad(set_to_none=True)
        pil_img = Image.fromarray(image_rgb)
        tensor = self.transform(pil_img).unsqueeze(0).to(self.device)
        tensor.requires_grad_(True)
        logits = self.model(tensor)
        target_score = logits[0, class_idx]
        target_score.backward()

        if self._last_conv_activations is None or self._last_conv_grads is None:
            h, w = image_rgb.shape[:2]
            return [0, 0, w - 1, h - 1], self._encode_data_url_jpg(cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR))

        acts = self._last_conv_activations[0].detach().cpu().numpy()
        grads = self._last_conv_grads[0].detach().cpu().numpy()
        weights = grads.mean(axis=(1, 2), keepdims=True)
        cam = (weights * acts).sum(axis=0)
        cam = np.maximum(cam, 0)
        if cam.max() > 0:
            cam = cam / cam.max()
        cam = cv2.resize(cam.astype(np.float32), (image_rgb.shape[1], image_rgb.shape[0]))

        mask = (cam > 0.45).astype(np.uint8)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        h, w = image_rgb.shape[:2]
        if contours:
            cnt = max(contours, key=cv2.contourArea)
            x, y, bw, bh = cv2.boundingRect(cnt)
            bbox = [int(x), int(y), int(x + bw), int(y + bh)]
        else:
            bbox = [0, 0, w - 1, h - 1]

        heat = (cam * 255).astype(np.uint8)
        heatmap = cv2.applyColorMap(heat, cv2.COLORMAP_JET)
        bgr = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR)
        overlay = cv2.addWeighted(bgr, 0.65, heatmap, 0.35, 0)

        color = (40, 220, 90) if class_idx == 0 else (30, 60, 255)
        cv2.rectangle(overlay, (bbox[0], bbox[1]), (bbox[2], bbox[3]), color, 2)
        label = self.labels[class_idx]
        cv2.putText(
            overlay,
            f"{label}",
            (bbox[0], max(20, bbox[1] - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            color,
            2,
            cv2.LINE_AA,
        )

        return bbox, self._encode_data_url_jpg(overlay)

    def _predict_pil(self, image: Image.Image, min_confidence: float = 0.6) -> dict[str, Any]:
        image = image.convert("RGB")
        tensor = self.transform(image).unsqueeze(0).to(self.device)
        with torch.no_grad():
            logits = self.model(tensor)
            probs = torch.softmax(logits, dim=1).squeeze(0).detach().cpu().tolist()

        best_idx = max(range(len(probs)), key=lambda idx: probs[idx])
        best_conf = float(probs[best_idx])
        probabilities = {self.labels[i]: round(float(probs[i]), 6) for i in range(len(self.labels))}
        final_label = self.labels[best_idx] if best_conf >= min_confidence else "uncertain"

        np_rgb = np.array(image)
        bbox, annotated = self._gradcam_bbox(np_rgb, best_idx)
        return {
            "label": final_label,
            "raw_label": self.labels[best_idx],
            "confidence": round(best_conf, 6),
            "probabilities": probabilities,
            "bbox": bbox,
            "annotated_image_data_url": annotated,
        }

    def predict_image_bytes(self, image_bytes: bytes, min_confidence: float = 0.6) -> dict[str, Any]:
        image = Image.open(io.BytesIO(image_bytes))
        return self._predict_pil(image, min_confidence=min_confidence)

    def analyze_video_bytes(
        self,
        video_bytes: bytes,
        sample_every_sec: float = 1.0,
        event_threshold: float = 0.6,
        min_confidence: float = 0.6,
        target_label: str = "all",
    ) -> dict[str, Any]:
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
            tmp.write(video_bytes)
            tmp_path = tmp.name

        cap = cv2.VideoCapture(tmp_path)
        if not cap.isOpened():
            raise ValueError("Invalid or unreadable video file.")

        fps = cap.get(cv2.CAP_PROP_FPS)
        if not fps or fps <= 0:
            fps = 25.0
        frame_step = max(1, int(fps * max(0.2, sample_every_sec)))

        frame_idx = 0
        sampled = 0
        events: list[dict[str, Any]] = []
        class_counts = {label: 0 for label in self.labels}

        try:
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                if frame_idx % frame_step != 0:
                    frame_idx += 1
                    continue

                sampled += 1
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                pil_img = Image.fromarray(rgb)
                pred = self._predict_pil(pil_img, min_confidence=min_confidence)
                class_counts[pred["raw_label"]] += 1

                include_label = (
                    target_label == "all"
                    or pred["raw_label"] == target_label
                )
                is_event = include_label and pred["confidence"] >= event_threshold
                if is_event:
                    events.append(
                        {
                            "timestamp_sec": round(frame_idx / fps, 2),
                            "label": pred["label"],
                            "raw_label": pred["raw_label"],
                            "confidence": pred["confidence"],
                            "bbox": pred["bbox"],
                            "snapshot_data_url": pred["annotated_image_data_url"],
                        }
                    )
                frame_idx += 1
        finally:
            cap.release()
            try:
                Path(tmp_path).unlink(missing_ok=True)
            except OSError:
                pass

        return {
            "fps": round(float(fps), 3),
            "sampled_frames": sampled,
            "class_counts": class_counts,
            "events": events,
            "event_threshold": event_threshold,
            "sample_every_sec": sample_every_sec,
            "min_confidence": min_confidence,
            "target_label": target_label,
        }


animal_bag_service = AnimalBagService()

