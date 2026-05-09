from __future__ import annotations

import base64
import io
import os
import tempfile
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image

_ultralytics_config_dir = Path(__file__).resolve().parents[2] / "outputs" / "ultralytics"
_ultralytics_config_dir.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("YOLO_CONFIG_DIR", str(_ultralytics_config_dir))

from ultralytics import YOLO

from app.core.config import settings
from app.services.device import yolo_device


def _resolve_path(path: Path) -> Path:
    if path.is_absolute():
        return path
    backend_root = Path(__file__).resolve().parents[2]
    return (backend_root / path).resolve()


class TheftSurveillanceService:
    def __init__(self) -> None:
        self.device = yolo_device()
        self.use_half = self.device != "cpu"
        self.theft_batch_size = 16
        self.person_model = YOLO(str(_resolve_path(settings.model4_person_weights_path)))
        self.theft_model = YOLO(str(_resolve_path(settings.model4_theft_weights_path)))
        self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        self.profile_face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_profileface.xml")
        self.eye_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_eye.xml")

        self.captures_dir = _resolve_path(Path("./captures"))
        self.captures_dir.mkdir(parents=True, exist_ok=True)
        self.suspect_faces_dir = self.captures_dir / "suspect_faces"
        self.suspect_faces_dir.mkdir(parents=True, exist_ok=True)
        self.latest_result: dict[str, Any] | None = None
        self.latest_job: dict[str, Any] = {
            "job_id": None,
            "status": "idle",
            "message": "No theft analysis job started yet.",
            "updated_at": None,
        }
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="theft-analysis")

    def _encode_data_url_jpg(self, bgr_img: np.ndarray, max_width: int = 640, quality: int = 70) -> str:
        if bgr_img.size == 0:
            return ""
        h, w = bgr_img.shape[:2]
        if w > max_width:
            scale = max_width / float(w)
            bgr_img = cv2.resize(bgr_img, (max_width, max(1, int(h * scale))), interpolation=cv2.INTER_AREA)
        ok, encoded = cv2.imencode(".jpg", bgr_img, [int(cv2.IMWRITE_JPEG_QUALITY), int(quality)])
        if not ok:
            return ""
        return "data:image/jpeg;base64," + base64.b64encode(encoded.tobytes()).decode("utf-8")

    def _crop_face_box(self, bgr_img: np.ndarray, x: int, y: int, w: int, h: int) -> tuple[list[int], np.ndarray]:
        pad = max(6, int(max(w, h) * 0.22))
        x1 = max(0, x - pad)
        y1 = max(0, y - pad)
        x2 = min(bgr_img.shape[1], x + w + pad)
        y2 = min(bgr_img.shape[0], y + h + pad)
        return [int(x1), int(y1), int(x2), int(y2)], bgr_img[y1:y2, x1:x2]

    def _has_face_features(self, bgr_img: np.ndarray) -> bool:
        if bgr_img.size == 0:
            return False
        h, w = bgr_img.shape[:2]
        if h < 28 or w < 28:
            return False
        aspect = w / max(1, h)
        if aspect < 0.55 or aspect > 1.65:
            return False
        gray = cv2.cvtColor(bgr_img, cv2.COLOR_BGR2GRAY)
        if float(np.std(gray)) < 8.0:
            return False

        try:
            import face_recognition  # type: ignore

            rgb = cv2.cvtColor(bgr_img, cv2.COLOR_BGR2RGB)
            if face_recognition.face_locations(rgb, number_of_times_to_upsample=1, model="hog"):
                return True
        except BaseException:
            pass

        equalized = cv2.equalizeHist(gray)
        min_eye = max(5, min(h, w) // 8)
        eyes = self.eye_cascade.detectMultiScale(
            equalized,
            scaleFactor=1.08,
            minNeighbors=3,
            minSize=(min_eye, min_eye),
        )
        if len(eyes) >= 1:
            return True

        profile = self.profile_face_cascade.detectMultiScale(
            equalized,
            scaleFactor=1.1,
            minNeighbors=4,
            minSize=(max(18, w // 3), max(18, h // 3)),
        )
        return len(profile) > 0

    def _find_face(self, bgr_img: np.ndarray, min_size: tuple[int, int] = (24, 24)) -> tuple[list[int] | None, np.ndarray | None]:
        if bgr_img.size == 0:
            return None, None
        try:
            import face_recognition  # type: ignore

            rgb = cv2.cvtColor(bgr_img, cv2.COLOR_BGR2RGB)
            locations = face_recognition.face_locations(rgb, number_of_times_to_upsample=1, model="hog")
            if locations:
                top, right, bottom, left = max(locations, key=lambda loc: (loc[2] - loc[0]) * (loc[1] - loc[3]))
                return self._crop_face_box(
                    bgr_img,
                    int(left),
                    int(top),
                    int(right - left),
                    int(bottom - top),
                )
        except BaseException:
            pass

        gray = cv2.cvtColor(bgr_img, cv2.COLOR_BGR2GRAY)
        equalized_gray = cv2.equalizeHist(gray)
        candidates: list[tuple[int, int, int, int]] = []
        for cascade, scale, neighbors in (
            (self.face_cascade, 1.12, 6),
            (self.profile_face_cascade, 1.12, 5),
        ):
            found = cascade.detectMultiScale(equalized_gray, scaleFactor=scale, minNeighbors=neighbors, minSize=min_size)
            candidates.extend((int(x), int(y), int(w), int(h)) for x, y, w, h in found)

        candidates.sort(key=lambda f: f[2] * f[3], reverse=True)
        for x, y, w, h in candidates:
            _, candidate_crop = self._crop_face_box(bgr_img, x, y, w, h)
            if self._has_face_features(candidate_crop):
                return self._crop_face_box(bgr_img, x, y, w, h)

        return None, None

    def _find_face_for_person(
        self,
        frame: np.ndarray,
        person_box: tuple[int, int, int, int],
    ) -> tuple[list[int] | None, np.ndarray | None, str]:
        x1, y1, x2, y2 = person_box
        crop = frame[y1:y2, x1:x2]
        local_box, face_crop = self._find_face(crop, min_size=(18, 18))
        if face_crop is not None and local_box is not None:
            fx1, fy1, fx2, fy2 = local_box
            return [x1 + fx1, y1 + fy1, x1 + fx2, y1 + fy2], face_crop, "person_crop"

        # Fallback: many CCTV faces are near the upper body but partially outside
        # the person crop. Search an expanded head/torso area in the full frame.
        person_w = x2 - x1
        person_h = y2 - y1
        ex1 = max(0, x1 - int(person_w * 0.25))
        ex2 = min(frame.shape[1], x2 + int(person_w * 0.25))
        ey1 = max(0, y1 - int(person_h * 0.18))
        ey2 = min(frame.shape[0], y1 + int(person_h * 0.55))
        expanded = frame[ey1:ey2, ex1:ex2]
        expanded_box, expanded_face = self._find_face(expanded, min_size=(16, 16))
        if expanded_face is not None and expanded_box is not None:
            fx1, fy1, fx2, fy2 = expanded_box
            return [ex1 + fx1, ey1 + fy1, ex1 + fx2, ey1 + fy2], expanded_face, "expanded_frame"

        return None, None, "none"

    def _is_face_crop_plausible(self, bgr_img: np.ndarray) -> bool:
        return self._has_face_features(bgr_img)

    def list_suspect_faces(self, limit: int = 60) -> dict[str, Any]:
        items: list[dict[str, Any]] = []
        paths = [path for path in self.suspect_faces_dir.glob("face_*.jpg")]
        for path in sorted(paths, key=lambda p: p.stat().st_mtime, reverse=True)[:limit]:
            img = cv2.imread(str(path))
            if img is None:
                continue
            if not self._is_face_crop_plausible(img):
                continue
            name_parts = path.stem.split("_")
            status = next((part.upper() for part in name_parts if part.lower() in {"suspect", "theft"}), "SUSPECT")
            items.append(
                {
                    "filename": path.name,
                    "status": status,
                    "created_at_unix_ms": int(path.stat().st_mtime * 1000),
                    "image_data_url": self._encode_data_url_jpg(img),
                }
            )
        return {"items": items, "count": len(items), "directory": str(self.suspect_faces_dir)}

    def _process_tracking_results(
        self,
        results,
        conf_theft: float = 0.4,
        max_frames: int | None = None,
    ) -> dict[str, Any]:
        id_history: dict[int, list[int]] = {}
        event_saved: set[int] = set()
        face_saved: set[int] = set()
        events: list[dict[str, Any]] = []
        max_inline_events = 25
        status_counts = {"NORMAL": 0, "SUSPECT": 0, "THEFT": 0}
        fps = 0.0
        frame_index = 0

        for r in results:
            if max_frames is not None and frame_index >= max_frames:
                break
            frame = r.orig_img
            clean_frame = frame.copy()
            if fps == 0.0:
                fps = float(getattr(r, "speed", {}).get("fps", 0.0) or 0.0)

            if r.boxes is not None and r.boxes.id is not None:
                boxes = r.boxes.xyxy.cpu().numpy()
                ids = r.boxes.id.cpu().numpy()
                detections: list[dict[str, Any]] = []
                crops: list[np.ndarray] = []

                for box, track_id_float in zip(boxes, ids):
                    track_id = int(track_id_float)
                    x1, y1, x2, y2 = map(int, box)
                    x1 = max(0, x1)
                    y1 = max(0, y1)
                    x2 = min(frame.shape[1], x2)
                    y2 = min(frame.shape[0], y2)
                    crop = clean_frame[y1:y2, x1:x2]
                    if crop.size == 0:
                        continue

                    detections.append(
                        {
                            "track_id": track_id,
                            "bbox": (x1, y1, x2, y2),
                            "crop": crop,
                        }
                    )
                    crops.append(crop)

                theft_flags = [0] * len(detections)
                for start in range(0, len(crops), self.theft_batch_size):
                    batch = crops[start : start + self.theft_batch_size]
                    theft_results = self.theft_model.predict(
                        batch,
                        conf=conf_theft,
                        device=self.device,
                        half=self.use_half,
                        verbose=False,
                    )
                    for offset, tr in enumerate(theft_results):
                        if tr.boxes is None:
                            continue
                        for cls in tr.boxes.cls:
                            if int(cls) == 0:
                                theft_flags[start + offset] = 1
                                break

                for detection, is_theft in zip(detections, theft_flags):
                    track_id = int(detection["track_id"])
                    x1, y1, x2, y2 = detection["bbox"]

                    if track_id not in id_history:
                        id_history[track_id] = []
                    id_history[track_id].append(is_theft)
                    id_history[track_id] = id_history[track_id][-10:]
                    score = sum(id_history[track_id])

                    if score >= 5:
                        status = "THEFT"
                        color = (0, 0, 255)
                    elif score >= 2:
                        status = "SUSPECT"
                        color = (0, 165, 255)
                    else:
                        status = "NORMAL"
                        color = (0, 255, 0)
                    status_counts[status] += 1

                    label = f"ID {track_id} {status}"
                    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                    cv2.putText(frame, label, (x1, max(20, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.65, color, 2)

                    face_abs_bbox = None
                    saved_face_data_url = ""
                    saved_face_path = ""
                    saved_source = "none"

                    if status in {"SUSPECT", "THEFT"}:
                        local_face_crop = None
                        face_detection_source = "none"
                        if track_id not in face_saved:
                            local_face_box, local_face_crop, face_detection_source = self._find_face_for_person(
                                clean_frame, (x1, y1, x2, y2)
                            )
                            if local_face_crop is not None:
                                face_abs_bbox = local_face_box
                                cv2.rectangle(
                                    frame,
                                    (face_abs_bbox[0], face_abs_bbox[1]),
                                    (face_abs_bbox[2], face_abs_bbox[3]),
                                    (255, 255, 0),
                                    2,
                                )
                                cv2.putText(
                                    frame,
                                    "FACE",
                                    (face_abs_bbox[0], max(20, face_abs_bbox[1] - 8)),
                                    cv2.FONT_HERSHEY_SIMPLEX,
                                    0.5,
                                    (255, 255, 0),
                                    2,
                                )

                        if (
                            local_face_crop is not None
                            and self._is_face_crop_plausible(local_face_crop)
                            and track_id not in face_saved
                        ):
                            face_saved.add(track_id)
                            capture_name = f"face_{int(time.time() * 1000)}_id_{track_id}_f{frame_index}_{status.lower()}.jpg"
                            capture_path = self.suspect_faces_dir / capture_name
                            cv2.imwrite(str(capture_path), local_face_crop)
                            saved_face_data_url = self._encode_data_url_jpg(local_face_crop)
                            saved_source = f"face_{face_detection_source}"
                            saved_face_path = str(capture_path)

                        if track_id not in event_saved:
                            event_saved.add(track_id)
                            if len(events) >= max_inline_events:
                                continue
                            events.append(
                            {
                                "track_id": track_id,
                                "status": status,
                                "timestamp_sec": round(frame_index / 30.0, 2),
                                "person_bbox": [x1, y1, x2, y2],
                                "face_bbox": face_abs_bbox,
                                "saved_source": saved_source,
                                "saved_image_path": saved_face_path,
                                "saved_image_data_url": saved_face_data_url,
                                "snapshot_data_url": self._encode_data_url_jpg(frame),
                            }
                            )
            frame_index += 1

        return {
            "processed_frames": frame_index,
            "fps": round(fps or 30.0, 2),
            "status_counts": status_counts,
            "events": events,
        }

    def analyze_video(
        self,
        video_bytes: bytes,
        conf_person: float = 0.3,
        conf_theft: float = 0.4,
        frame_stride: int = 2,
        max_frames: int | None = None,
    ) -> dict[str, Any]:
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
            tmp.write(video_bytes)
            tmp_path = tmp.name

        try:
            results = self.person_model.track(
                source=tmp_path,
                conf=conf_person,
                device=self.device,
                half=self.use_half,
                classes=[0],
                tracker="botsort.yaml",
                persist=True,
                stream=True,
                verbose=False,
                vid_stride=max(1, int(frame_stride)),
            )
            output = self._process_tracking_results(results, conf_theft=conf_theft, max_frames=max_frames)
        finally:
            try:
                Path(tmp_path).unlink(missing_ok=True)
            except OSError:
                pass

        self.latest_result = output

        return output

    def latest(self) -> dict[str, Any]:
        if self.latest_result is None:
            return {
                "processed_frames": 0,
                "fps": 0.0,
                "status_counts": {"NORMAL": 0, "SUSPECT": 0, "THEFT": 0},
                "events": [],
            }
        return self.latest_result

    def latest_job_status(self) -> dict[str, Any]:
        return self.latest_job

    def _run_job(
        self,
        *,
        job_id: str,
        video_bytes: bytes,
        conf_person: float,
        conf_theft: float,
        frame_stride: int,
        max_frames: int | None,
    ) -> None:
        self.latest_result = {
            "processed_frames": 0,
            "fps": 0.0,
            "status_counts": {"NORMAL": 0, "SUSPECT": 0, "THEFT": 0},
            "events": [],
        }
        self.latest_job = {
            "job_id": job_id,
            "status": "running",
            "message": "Theft analysis in progress.",
            "updated_at": int(time.time()),
        }
        try:
            self.analyze_video(
                video_bytes,
                conf_person=conf_person,
                conf_theft=conf_theft,
                frame_stride=frame_stride,
                max_frames=max_frames,
            )
            self.latest_job = {
                "job_id": job_id,
                "status": "completed",
                "message": "Theft analysis completed.",
                "updated_at": int(time.time()),
            }
        except Exception as exc:
            self.latest_job = {
                "job_id": job_id,
                "status": "failed",
                "message": f"Theft analysis failed: {exc}",
                "updated_at": int(time.time()),
            }

    def submit_video_job(
        self,
        video_bytes: bytes,
        conf_person: float = 0.3,
        conf_theft: float = 0.4,
        frame_stride: int = 2,
        max_frames: int | None = None,
    ) -> dict[str, str]:
        if self.latest_job.get("status") == "running":
            return {
                "job_id": str(self.latest_job.get("job_id") or ""),
                "status": "running",
                "message": "A theft analysis job is already running.",
            }

        job_id = str(uuid.uuid4())
        self.latest_job = {
            "job_id": job_id,
            "status": "queued",
            "message": "Theft analysis queued.",
            "updated_at": int(time.time()),
        }
        self.executor.submit(
            self._run_job,
            job_id=job_id,
            video_bytes=video_bytes,
            conf_person=conf_person,
            conf_theft=conf_theft,
            frame_stride=frame_stride,
            max_frames=max_frames,
        )
        return {
            "job_id": job_id,
            "status": "queued",
            "message": "Theft analysis started in background.",
        }

    def analyze_youtube(
        self,
        youtube_url: str,
        conf_person: float = 0.3,
        conf_theft: float = 0.4,
        frame_stride: int = 2,
        max_frames: int = 900,
    ) -> dict[str, Any]:
        if not youtube_url.strip():
            raise ValueError("youtube_url is required.")
        results = self.person_model.track(
            source=youtube_url.strip(),
            conf=conf_person,
            device=self.device,
            half=self.use_half,
            classes=[0],
            tracker="botsort.yaml",
            persist=True,
            stream=True,
            verbose=False,
            vid_stride=max(1, int(frame_stride)),
        )
        return self._process_tracking_results(results, conf_theft=conf_theft, max_frames=max_frames)


theft_surveillance_service = TheftSurveillanceService()

