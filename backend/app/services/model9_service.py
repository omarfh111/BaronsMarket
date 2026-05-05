from __future__ import annotations

import base64
import io
import json
import os
import sys
import time
from urllib import error, parse, request
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image

from app.core.config import settings


def _resolve_path(path: Path) -> Path:
    if path.is_absolute():
        return path
    backend_root = Path(__file__).resolve().parents[2]
    return (backend_root / path).resolve()


class EmployeeAccessService:
    def __init__(self) -> None:
        self._load_error: str | None = None
        self._predictor = None
        self._ocr_reader = None
        self._supermarket_name = settings.model9_supermarket_name
        self._liveness_threshold = float(settings.model9_liveness_min)
        self._face_match_threshold = float(settings.model9_face_match_threshold)
        self._face_table = settings.model9_face_table
        self._face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
        backend_root = Path(__file__).resolve().parents[2]
        self._local_face_store = backend_root / "outputs" / "employee_faces.jsonl"
        self._local_face_store.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _init(self) -> None:
        model9_dir = _resolve_path(settings.model9_dir)
        repo_dir = model9_dir / "Silent-Face-Anti-Spoofing"
        if not model9_dir.exists() or not repo_dir.exists():
            self._load_error = f"MODEL9_DIR or repo not found: {model9_dir}"
            return

        try:
            if str(model9_dir) not in sys.path:
                sys.path.insert(0, str(model9_dir))
            if str(repo_dir) not in sys.path:
                sys.path.insert(0, str(repo_dir))

            # Ensure anti_spoof_v2 resolves repo path correctly regardless CWD.
            os.environ.setdefault("MODEL9_REPO_PATH", str(repo_dir))
            from anti_spoof_v2 import AntiSpoofPredictor  # type: ignore

            self._predictor = AntiSpoofPredictor()

            try:
                import easyocr  # type: ignore
                import torch

                self._ocr_reader = easyocr.Reader(["en"], gpu=torch.cuda.is_available())
            except Exception:
                self._ocr_reader = None
        except Exception as exc:
            self._load_error = f"Model9 init failed: {exc}"

    def _extract_face_embedding(self, frame: np.ndarray, face_box: list[int]) -> np.ndarray | None:
        # Try face_recognition first (lightweight and deterministic for matching).
        try:
            import face_recognition  # type: ignore

            x, y, w, h = face_box
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            top, right, bottom, left = y, x + w, y + h, x
            encs = face_recognition.face_encodings(rgb, [(top, right, bottom, left)])
            if encs:
                return np.asarray(encs[0], dtype=np.float32)
        except BaseException:
            pass
        return None

    def _cosine_distance(self, a: np.ndarray, b: np.ndarray) -> float:
        na = np.linalg.norm(a)
        nb = np.linalg.norm(b)
        if na <= 1e-9 or nb <= 1e-9:
            return 1.0
        return float(1.0 - float(np.dot(a, b) / (na * nb)))

    def _box_iou(self, a: list[int], b: list[int]) -> float:
        ax, ay, aw, ah = a
        bx, by, bw, bh = b
        x1 = max(ax, bx)
        y1 = max(ay, by)
        x2 = min(ax + aw, bx + bw)
        y2 = min(ay + ah, by + bh)
        inter = max(0, x2 - x1) * max(0, y2 - y1)
        union = max(1, aw * ah + bw * bh - inter)
        return float(inter / union)

    def _merge_face_boxes(self, boxes: list[list[int]]) -> list[list[int]]:
        merged: list[list[int]] = []
        for box in sorted(boxes, key=lambda b: b[2] * b[3], reverse=True):
            if box[2] < 24 or box[3] < 24:
                continue
            if any(self._box_iou(box, kept) > 0.35 for kept in merged):
                continue
            merged.append(box)
        return merged

    def _detect_faces(self, frame: np.ndarray) -> list[list[int]]:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        raw_boxes: list[list[int]] = [
            [int(x), int(y), int(w), int(h)]
            for x, y, w, h in self._face_cascade.detectMultiScale(gray, 1.1, 6, minSize=(40, 40))
        ]

        # face_recognition/HOG is better than Haar for small printed badge portraits.
        try:
            import face_recognition  # type: ignore

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            for top, right, bottom, left in face_recognition.face_locations(rgb, number_of_times_to_upsample=1, model="hog"):
                raw_boxes.append([int(left), int(top), int(right - left), int(bottom - top)])
        except BaseException:
            pass

        return self._merge_face_boxes(raw_boxes)

    def _supabase_headers(self) -> dict[str, str]:
        return {
            "apikey": settings.supabase_service_role_key,
            "Authorization": f"Bearer {settings.supabase_service_role_key}",
            "Content-Type": "application/json",
        }

    def _save_face_supabase(self, record: dict[str, Any]) -> None:
        if not settings.supabase_url.strip() or not settings.supabase_service_role_key.strip():
            raise RuntimeError("Supabase non configure")
        base = settings.supabase_url.rstrip("/")
        req = request.Request(
            url=f"{base}/rest/v1/{self._face_table}",
            method="POST",
            data=json.dumps(record).encode("utf-8"),
            headers={**self._supabase_headers(), "Prefer": "return=minimal"},
        )
        with request.urlopen(req, timeout=20):
            return

    def _save_face_local(self, record: dict[str, Any]) -> None:
        with self._local_face_store.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=True) + "\n")

    def register_face(self, image_bytes: bytes, employee_name: str) -> dict[str, Any]:
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        frame = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self._face_cascade.detectMultiScale(gray, 1.1, 6, minSize=(40, 40))
        if len(faces) == 0:
            return {
                "ok": False,
                "message": "No face detected for registration.",
                "employee_name": employee_name,
                "stored_in": "none",
            }
        x, y, w, h = max(faces, key=lambda b: int(b[2]) * int(b[3]))
        emb = self._extract_face_embedding(frame, [int(x), int(y), int(w), int(h)])
        if emb is None:
            return {
                "ok": False,
                "message": "Face embedding extraction failed. Install face_recognition dependency.",
                "employee_name": employee_name,
                "stored_in": "none",
            }

        record = {
            "employee_name": employee_name,
            "embedding": emb.tolist(),
            "created_at_unix_ms": int(time.time() * 1000),
        }
        stored_in = "local_jsonl"
        try:
            self._save_face_supabase(record)
            stored_in = "supabase"
        except Exception:
            self._save_face_local(record)

        return {
            "ok": True,
            "message": f"Face registered for {employee_name}.",
            "employee_name": employee_name,
            "stored_in": stored_in,
        }

    def _list_faces_supabase(self) -> list[dict[str, Any]]:
        if not settings.supabase_url.strip() or not settings.supabase_service_role_key.strip():
            return []
        base = settings.supabase_url.rstrip("/")
        q = parse.urlencode({"select": "employee_name,embedding,created_at_unix_ms", "limit": "5000"})
        req = request.Request(
            url=f"{base}/rest/v1/{self._face_table}?{q}",
            method="GET",
            headers={**self._supabase_headers(), "Accept": "application/json"},
        )
        with request.urlopen(req, timeout=20) as resp:
            payload = resp.read().decode("utf-8")
            data = json.loads(payload)
            return data if isinstance(data, list) else []

    def _list_faces_local(self) -> list[dict[str, Any]]:
        if not self._local_face_store.exists():
            return []
        rows: list[dict[str, Any]] = []
        with self._local_face_store.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except Exception:
                    continue
        return rows

    def _find_best_match(self, emb: np.ndarray | None) -> tuple[bool, str | None, float]:
        if emb is None:
            return (False, None, 1.0)
        candidates = self._list_faces_supabase()
        if not candidates:
            candidates = self._list_faces_local()
        best_name: str | None = None
        best_dist = 1.0
        for row in candidates:
            vec = row.get("embedding")
            if not isinstance(vec, list) or not vec:
                continue
            try:
                db_emb = np.asarray(vec, dtype=np.float32)
                dist = self._cosine_distance(emb, db_emb)
                if dist < best_dist:
                    best_dist = dist
                    best_name = str(row.get("employee_name") or "")
            except Exception:
                continue
        matched = best_name is not None and best_dist <= self._face_match_threshold
        return (matched, best_name if matched else None, float(best_dist))

    def _select_live_and_badge_faces(self, faces: Any) -> tuple[list[int] | None, list[int] | None]:
        boxes = [[int(x), int(y), int(w), int(h)] for x, y, w, h in faces]
        if not boxes:
            return (None, None)

        boxes.sort(key=lambda b: b[2] * b[3], reverse=True)
        live_box = boxes[0]
        live_area = max(1, live_box[2] * live_box[3])
        live_cx = live_box[0] + live_box[2] / 2
        live_cy = live_box[1] + live_box[3] / 2

        badge_candidates: list[list[int]] = []
        for box in boxes[1:]:
            x, y, w, h = box
            area = w * h
            cx = x + w / 2
            cy = y + h / 2
            center_distance = ((cx - live_cx) ** 2 + (cy - live_cy) ** 2) ** 0.5
            center_y = y + h / 2
            # Badge portraits must be a separate, smaller face, not a duplicate
            # detection on the live face. This prevents false ACCESS GRANTED.
            if (
                area <= live_area * 0.65
                and area >= live_area * 0.015
                and self._box_iou(live_box, box) <= 0.08
                and center_distance >= min(live_box[2], live_box[3]) * 0.45
                and center_y >= live_box[1] - live_box[3] * 0.25
            ):
                badge_candidates.append(box)

        badge_box = badge_candidates[0] if badge_candidates else None
        return (live_box, badge_box)

    def verify(self, image_bytes: bytes) -> dict[str, Any]:
        if self._load_error:
            return {
                "ok": False,
                "message": self._load_error,
                "access_granted": False,
                "liveness_score": 0.0,
                "liveness_threshold": self._liveness_threshold,
                "badge_ok": False,
                "badge_text": "",
                "expected_badge_text": self._supermarket_name,
                "face_detected": False,
                "debug": {},
            }

        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        frame = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        faces = self._detect_faces(frame)

        if len(faces) == 0:
            return {
                "ok": True,
                "message": "No face detected.",
                "access_granted": False,
                "liveness_score": 0.0,
                "liveness_threshold": self._liveness_threshold,
                "badge_ok": False,
                "badge_text": "",
                "expected_badge_text": self._supermarket_name,
                "face_detected": False,
                "debug": {"faces_count": 0},
            }

        live_box, badge_box = self._select_live_and_badge_faces(faces)
        if live_box is None:
            return {
                "ok": True,
                "message": "No face detected.",
                "access_granted": False,
                "liveness_score": 0.0,
                "liveness_threshold": self._liveness_threshold,
                "badge_ok": False,
                "badge_text": "",
                "expected_badge_text": self._supermarket_name,
                "face_detected": False,
                "face_registered": False,
                "employee_name": None,
                "debug": {"faces_count": int(len(faces))},
            }

        x, y, w, h = live_box
        debug = {
            "faces_count": int(len(faces)),
            "live_face_box": [int(x), int(y), int(w), int(h)],
            "badge_face_box": badge_box,
            "image_size": [int(frame.shape[1]), int(frame.shape[0])],
            "input_sha1": base64.b16encode(__import__("hashlib").sha1(image_bytes).digest()).decode("ascii")[:12],
            "check_order": ["liveness", "badge_face_match", "monoprix_badge", "registered_face"],
            "face_match_threshold": self._face_match_threshold,
        }

        # Strict access order:
        # 1) real/live face, 2) badge portrait matches live face,
        # 3) Monoprix badge/text, 4) registered employee face.
        liveness_score = float(self._predictor.predict(frame, [int(x), int(y), int(w), int(h)]))
        is_live = liveness_score >= self._liveness_threshold
        debug["is_live"] = is_live
        if not is_live:
            return {
                "ok": True,
                "message": (
                    f"ACCESS DENIED - liveness failed "
                    f"(score={liveness_score:.4f}, threshold={self._liveness_threshold:.4f})."
                ),
                "access_granted": False,
                "liveness_score": liveness_score,
                "liveness_threshold": self._liveness_threshold,
                "badge_ok": False,
                "badge_text": "",
                "expected_badge_text": self._supermarket_name,
                "face_detected": True,
                "face_registered": False,
                "employee_name": None,
                "debug": debug,
            }

        if badge_box is None:
            return {
                "ok": True,
                "message": "ACCESS DENIED - badge face not detected.",
                "access_granted": False,
                "liveness_score": liveness_score,
                "liveness_threshold": self._liveness_threshold,
                "badge_ok": False,
                "badge_text": "",
                "expected_badge_text": self._supermarket_name,
                "face_detected": True,
                "face_registered": False,
                "employee_name": None,
                "debug": debug,
            }

        live_emb = self._extract_face_embedding(frame, [int(x), int(y), int(w), int(h)])
        badge_emb = self._extract_face_embedding(frame, badge_box)
        badge_face_distance = self._cosine_distance(live_emb, badge_emb) if live_emb is not None and badge_emb is not None else 1.0
        badge_face_match = bool(live_emb is not None and badge_emb is not None and badge_face_distance <= self._face_match_threshold)
        debug["badge_face_distance"] = badge_face_distance
        debug["badge_face_match"] = badge_face_match
        if not badge_face_match:
            return {
                "ok": True,
                "message": (
                    f"ACCESS DENIED - live face does not match badge face "
                    f"(face_distance={badge_face_distance:.4f}, threshold={self._face_match_threshold:.4f})."
                ),
                "access_granted": False,
                "liveness_score": liveness_score,
                "liveness_threshold": self._liveness_threshold,
                "badge_ok": False,
                "badge_text": "",
                "expected_badge_text": self._supermarket_name,
                "face_detected": True,
                "face_registered": False,
                "employee_name": None,
                "debug": debug,
            }

        badge_text = ""
        badge_ok = False
        if self._ocr_reader is not None:
            ocr_results = self._ocr_reader.readtext(frame)
            badge_text = " ".join([str(r[1]) for r in ocr_results]).strip()
            badge_ok = self._supermarket_name.lower() in badge_text.lower()
        debug["badge_checked"] = True
        debug["badge_ok"] = badge_ok
        if not badge_ok:
            return {
                "ok": True,
                "message": (
                    f"ACCESS DENIED - Monoprix badge/text not found "
                    f"(expected={self._supermarket_name})."
                ),
                "access_granted": False,
                "liveness_score": liveness_score,
                "liveness_threshold": self._liveness_threshold,
                "badge_ok": False,
                "badge_text": badge_text,
                "expected_badge_text": self._supermarket_name,
                "face_detected": True,
                "face_registered": False,
                "employee_name": None,
                "debug": debug,
            }

        face_registered, employee_name, face_distance = self._find_best_match(live_emb)
        debug["face_distance"] = face_distance
        debug["face_registered"] = face_registered
        if not face_registered:
            return {
                "ok": True,
                "message": (
                    f"ACCESS DENIED - face not registered, contact technical service "
                    f"(face_distance={face_distance:.4f}, threshold={self._face_match_threshold:.4f})."
                ),
                "access_granted": False,
                "liveness_score": liveness_score,
                "liveness_threshold": self._liveness_threshold,
                "badge_ok": badge_ok,
                "badge_text": badge_text,
                "expected_badge_text": self._supermarket_name,
                "face_detected": True,
                "face_registered": False,
                "employee_name": None,
                "debug": debug,
            }

        return {
            "ok": True,
            "message": (
                f"ACCESS GRANTED - welcome {employee_name} "
                f"(liveness={liveness_score:.4f}, badge_face_distance={badge_face_distance:.4f}, "
                f"badge_ok={badge_ok}, "
                f"face_distance={face_distance:.4f})."
            ),
            "access_granted": True,
            "liveness_score": liveness_score,
            "liveness_threshold": self._liveness_threshold,
            "badge_ok": badge_ok,
            "badge_text": badge_text,
            "expected_badge_text": self._supermarket_name,
            "face_detected": True,
            "face_registered": face_registered,
            "employee_name": employee_name,
            "debug": debug,
        }


employee_access_service = EmployeeAccessService()
