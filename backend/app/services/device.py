from __future__ import annotations

from typing import Any

import torch

from app.core.config import settings


def torch_device() -> str:
    requested = str(settings.model_device or "auto").strip().lower()
    cuda_available = torch.cuda.is_available()

    if requested in {"cpu"}:
        return "cpu"
    if requested in {"cuda", "gpu"}:
        return "cuda" if cuda_available else "cpu"
    if requested.startswith("cuda:"):
        return requested if cuda_available else "cpu"
    return "cuda" if cuda_available else "cpu"


def yolo_device() -> int | str:
    device = torch_device()
    if device == "cuda":
        return 0
    if device.startswith("cuda:"):
        try:
            return int(device.split(":", 1)[1])
        except (IndexError, ValueError):
            return 0
    return "cpu"


def easyocr_gpu_enabled() -> bool:
    return torch_device().startswith("cuda")


def device_info() -> dict[str, Any]:
    device = torch_device()
    return {
        "requested": settings.model_device,
        "torch_device": device,
        "yolo_device": yolo_device(),
        "cuda_available": torch.cuda.is_available(),
        "cuda_version": torch.version.cuda,
        "gpu_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
    }
