from __future__ import annotations

import base64
import hashlib
import io
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from app.core.config import settings
from app.services.device import torch_device


def _resolve_path(path: Path) -> Path:
    if path.is_absolute():
        return path
    backend_root = Path(__file__).resolve().parents[2]
    return (backend_root / path).resolve()


def _to_data_url(arr: np.ndarray) -> str:
    img = Image.fromarray(arr.astype("uint8"))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"


def _is_jpeg_magic(data: bytes) -> bool:
    # JPEG SOI marker FF D8 and EOI FF D9 (simple heuristic)
    return len(data) >= 4 and data[0] == 0xFF and data[1] == 0xD8 and data[-2] == 0xFF and data[-1] == 0xD9


class ForgedDocsService:
    def __init__(self) -> None:
        self._load_error: str | None = None
        self._predictor = None
        self._threshold = float(settings.model8_threshold)
        self._quality = int(settings.model8_quality)
        self._forged_class_idx = int(settings.model8_forged_class_idx)
        self._require_true_jpeg = bool(settings.model8_require_true_jpeg)
        self._init()

    def _init(self) -> None:
        code_dir = _resolve_path(settings.model8_code_dir)
        ckpt = _resolve_path(settings.model8_checkpoint_path)
        project_root = Path(__file__).resolve().parents[3]
        if not code_dir.exists():
            self._load_error = f"MODEL8_CODE_DIR not found: {code_dir}"
            return
        if not ckpt.exists():
            self._load_error = f"MODEL8_CHECKPOINT_PATH not found: {ckpt}"
            return

        try:
            if str(project_root) not in sys.path:
                sys.path.insert(0, str(project_root))
            if str(code_dir) not in sys.path:
                sys.path.insert(0, str(code_dir))
            models_dir = code_dir / "models"
            if str(models_dir) not in sys.path:
                sys.path.insert(0, str(models_dir))
            cwd_before = os.getcwd()
            os.chdir(str(code_dir))
            from inference import DTDPredictor  # type: ignore

            device = torch_device()
            self._predictor = DTDPredictor(checkpoint_path=str(ckpt), device=device)
            os.chdir(cwd_before)
        except Exception as exc:
            self._load_error = f"Model8 init failed: {exc}"
            try:
                os.chdir(cwd_before)
            except Exception:
                pass

    def verify(self, image_bytes: bytes) -> dict[str, Any]:
        if self._load_error:
            return {
                "ok": False,
                "message": self._load_error,
                "is_forged": False,
                "score": 0.0,
                "threshold": self._threshold,
                "mask_data_url": "",
                "heatmap_data_url": "",
                "original_data_url": "",
            }
        if self._predictor is None:
            return {
                "ok": False,
                "message": "Model8 predictor is not initialized.",
                "is_forged": False,
                "score": 0.0,
                "threshold": self._threshold,
                "mask_data_url": "",
                "heatmap_data_url": "",
                "original_data_url": "",
            }

        input_note = ""
        is_magic_jpeg = _is_jpeg_magic(image_bytes)
        with Image.open(io.BytesIO(image_bytes)) as probe:
            src_format = (probe.format or "").upper()
            src_w, src_h = probe.size
        input_sha1 = hashlib.sha1(image_bytes).hexdigest()[:12]

        # Notebook-aligned behavior:
        # 1) run on original input bytes as-is (PNG/JPEG/etc)
        # 2) convert+resize to JPEG only inside _predict_safe on ValueError.
        suffix = ".jpg"
        if src_format == "PNG":
            suffix = ".png"
        elif src_format in {"JPG", "JPEG"}:
            suffix = ".jpg"
        elif src_format == "WEBP":
            suffix = ".webp"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(image_bytes)
            image_path = tmp.name

        try:
            result = self._predict_safe(image_path=image_path, quality=self._quality)
            mask = np.array(result["mask"]).astype(np.float32) / 255.0
            # Notebook behavior: score is mean of binary mask.
            mask_score = float(mask.mean())
            prob_score = float(result.get("forgery_score", 0.0))
            score = mask_score
            is_forged = score >= self._threshold
            verdict = "FORGED" if is_forged else "AUTHENTIC"
            c0 = float(result.get("class0_score", 0.0))
            c1 = float(result.get("class1_score", 0.0))
            dct_backend = str(result.get("dct_backend", "unknown"))
            if dct_backend == "scipy_fallback":
                input_note = " Using scipy DCT fallback (no native jpegio)."
            forged_pixels = int((mask > 0.5).sum())
            total_pixels = int(mask.size)
            message = (
                f"{verdict} (score={score:.6f}, threshold={self._threshold:.6f}, "
                f"forged_class={self._forged_class_idx}, class0={c0:.6f}, class1={c1:.6f}, "
                f"prob_score={prob_score:.6f}, mask_score={mask_score:.6f}, "
                f"forged_pixels={forged_pixels}/{total_pixels}, "
                f"src_format={src_format}, src_size={src_w}x{src_h}, "
                f"input_sha1={input_sha1}, magic_jpeg={is_magic_jpeg}, "
                f"dct_backend={dct_backend})."
                f"{input_note}"
            )
            return {
                "ok": True,
                "message": message,
                "is_forged": is_forged,
                "score": float(score),
                "threshold": self._threshold,
                "mask_data_url": _to_data_url(np.array(result["mask"])),
                "heatmap_data_url": _to_data_url(np.array(result["heatmap"])),
                "original_data_url": _to_data_url(np.array(result["original"])),
            }
        finally:
            try:
                os.unlink(image_path)
            except Exception:
                pass

    def _predict_safe(self, image_path: str, quality: int) -> dict[str, Any]:
        """Notebook-aligned safe inference:
        1) direct predict
        2) on ValueError, resize to 32-multiple + JPEG retry
        """
        assert self._predictor is not None
        try:
            return self._predictor.predict(
                image_path,
                quality=quality,
                forged_class_idx=self._forged_class_idx,
                use_native_jpeg_dct=False,
            )
        except Exception:
            img = Image.open(image_path).convert("RGB")
            w, h = img.size
            new_w = max(32, (w // 32) * 32)
            new_h = max(32, (h // 32) * 32)
            img_resized = img.resize((new_w, new_h), Image.BILINEAR)

            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                img_resized.save(tmp.name, "JPEG", quality=95)
                tmp_path = tmp.name

            try:
                return self._predictor.predict(
                    tmp_path,
                    quality=quality,
                    forged_class_idx=self._forged_class_idx,
                    use_native_jpeg_dct=False,
                )
            finally:
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass


forged_docs_service = ForgedDocsService()
