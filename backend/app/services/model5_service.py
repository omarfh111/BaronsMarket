from __future__ import annotations

import json
import tempfile
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from ultralytics import YOLO

from app.core.config import settings


def _resolve_path(path: Path) -> Path:
    if path.is_absolute():
        return path
    backend_root = Path(__file__).resolve().parents[2]
    return (backend_root / path).resolve()


class Model5Service:
    def __init__(self) -> None:
        weights = settings.model5_weights_path
        resolved = _resolve_path(Path(weights))
        self.model = YOLO(str(resolved if resolved.exists() else weights))

        self.output_dir = _resolve_path(settings.model5_output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.latest_result: dict[str, Any] | None = None
        self.latest_job: dict[str, Any] = {
            "job_id": None,
            "status": "idle",
            "message": "No queue analysis job started yet.",
            "updated_at": None,
        }
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="queue-reco")
        self.model5_config = self._load_model5_config()

    def _load_model5_config(self) -> dict[str, Any]:
        default_path = _resolve_path(Path("../ml/models/model_5/queue_config.json"))
        if default_path.exists():
            return json.loads(default_path.read_text(encoding="utf-8"))
        return {}

    def _load_queue_zones(self) -> dict[str, np.ndarray]:
        # Priority 1: official notebook config file (ml/models/model_5/queue_config.json)
        if isinstance(self.model5_config, dict) and "zones" in self.model5_config:
            zones_data = self.model5_config["zones"]
            zones: dict[str, np.ndarray] = {}
            for name, points in zones_data.items():
                arr = np.array(points, dtype=np.int32)
                if arr.ndim != 2 or arr.shape[1] != 2 or len(arr) < 3:
                    continue
                zones[str(name)] = arr
            if zones:
                return zones

        # Priority 2: web-editable zones json under model/model_5/queue_zones.json
        zones_path = _resolve_path(settings.model5_queue_zones_path)
        if not zones_path.exists():
            raise FileNotFoundError(
                f"Queue zones file not found: {zones_path}. "
                "Create model/model_5/queue_zones.json first."
            )
        raw = json.loads(zones_path.read_text(encoding="utf-8"))
        zones_data = raw.get("zones", raw)
        zones: dict[str, np.ndarray] = {}
        for name, points in zones_data.items():
            arr = np.array(points, dtype=np.int32)
            if arr.ndim != 2 or arr.shape[1] != 2 or len(arr) < 3:
                continue
            zones[str(name)] = arr
        if not zones:
            raise ValueError("No valid queue polygons found in queue_zones.json.")
        return zones

    @staticmethod
    def _bbox_polygon(box: list[int]) -> np.ndarray:
        x1, y1, x2, y2 = box
        return np.array([[x1, y1], [x2, y1], [x2, y2], [x1, y2]], dtype=np.int32)

    @staticmethod
    def _polygon_overlap_ratio(box: list[int], zone_polygon: np.ndarray) -> float:
        x1, y1, x2, y2 = box
        w = max(0, x2 - x1)
        h = max(0, y2 - y1)
        if w == 0 or h == 0:
            return 0.0

        box_poly = Model5Service._bbox_polygon(box).astype(np.float32)
        zone_poly = zone_polygon.astype(np.float32)
        inter_area, _ = cv2.intersectConvexConvex(box_poly, zone_poly)
        if inter_area <= 0:
            return 0.0
        box_area = float(w * h)
        return float(inter_area / max(box_area, 1.0))

    def _assign_box_to_queue(
        self,
        box: list[int],
        queue_zones: dict[str, np.ndarray],
        min_overlap: float,
    ) -> tuple[str | None, float]:
        # Match notebook logic:
        # 1) FOOT point must be inside polygon (hard constraint)
        # 2) overlap threshold (soft constraint)
        x1, y1, x2, y2 = box
        foot_x = int((x1 + x2) / 2)
        foot_y = int(y2)

        best_queue = None
        best_overlap = 0.0
        for queue_name, polygon in queue_zones.items():
            inside = cv2.pointPolygonTest(polygon, (foot_x, foot_y), False) >= 0
            if not inside:
                continue
            overlap = self._polygon_overlap_ratio(box, polygon)
            if overlap > best_overlap:
                best_overlap = overlap
                best_queue = queue_name
        if best_overlap < min_overlap:
            return None, best_overlap
        return best_queue, best_overlap

    @staticmethod
    def _choose_best_queue(queue_counts: dict[str, int], min_valid_count: int = 1) -> str:
        valid = {k: v for k, v in queue_counts.items() if v >= min_valid_count}
        if valid:
            return min(valid, key=valid.get)
        return min(queue_counts, key=queue_counts.get)

    @staticmethod
    def _draw_zone(frame: np.ndarray, polygon: np.ndarray, color: tuple[int, int, int], label: str) -> None:
        cv2.polylines(frame, [polygon], isClosed=True, color=color, thickness=2)
        px, py = polygon[0]
        cv2.putText(frame, label, (int(px), max(24, int(py) - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.65, color, 2)

    def analyze_video(
        self,
        video_bytes: bytes,
        conf_person: float = 0.25,
        iou: float = 0.5,
        imgsz: int = 1280,
        frame_stride: int = 1,
        min_overlap: float = 0.2,
        min_valid_count: int = 1,
        max_frames: int = 600,
    ) -> dict[str, Any]:
        queue_zones = self._load_queue_zones()
        queue_names = list(queue_zones.keys())

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
            tmp.write(video_bytes)
            tmp_path = tmp.name

        cap = cv2.VideoCapture(tmp_path)
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 25.0)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 1280)
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 720)
        cap.release()

        output_name = f"queue_reco_{int(time.time())}.mp4"
        output_path = self.output_dir / output_name
        writer = cv2.VideoWriter(
            str(output_path),
            cv2.VideoWriter_fourcc(*"mp4v"),
            max(1.0, fps),
            (width, height),
        )

        detection_cfg = self.model5_config.get("detection", {}) if isinstance(self.model5_config, dict) else {}
        assignment_cfg = self.model5_config.get("assignment", {}) if isinstance(self.model5_config, dict) else {}
        smoothing_window = int(self.model5_config.get("smoothing_window", 10)) if isinstance(self.model5_config, dict) else 10
        live_update_every = int(self.model5_config.get("live_update_every", 1)) if isinstance(self.model5_config, dict) else 1

        conf_person = float(conf_person if conf_person is not None else detection_cfg.get("conf", 0.25))
        iou = float(iou if iou is not None else detection_cfg.get("iou", 0.5))
        imgsz = int(imgsz if imgsz is not None else detection_cfg.get("imgsz", 1280))
        classes = detection_cfg.get("classes", [0])
        min_overlap = float(min_overlap if min_overlap is not None else assignment_cfg.get("min_overlap", 0.2))

        results = self.model.track(
            source=tmp_path,
            conf=conf_person,
            iou=iou,
            imgsz=imgsz,
            classes=classes,
            tracker="bytetrack.yaml",
            persist=True,
            stream=True,
            verbose=False,
            vid_stride=max(1, int(frame_stride)),
        )

        counts_history: list[dict[str, int]] = []
        processed_frames = 0

        for r in results:
            frame = r.orig_img
            frame_counts = {q: 0 for q in queue_names}
            seen_ids: set[int] = set()
            assignment_by_id: dict[int, str] = {}

            if r.boxes is not None and r.boxes.id is not None:
                boxes = r.boxes.xyxy.cpu().numpy()
                ids = r.boxes.id.cpu().numpy()
                for box_arr, track_id_raw in zip(boxes, ids):
                    track_id = int(track_id_raw)
                    if track_id in seen_ids:
                        continue
                    seen_ids.add(track_id)

                    x1, y1, x2, y2 = map(int, box_arr)
                    x1 = max(0, min(x1, frame.shape[1] - 1))
                    y1 = max(0, min(y1, frame.shape[0] - 1))
                    x2 = max(x1 + 1, min(x2, frame.shape[1]))
                    y2 = max(y1 + 1, min(y2, frame.shape[0]))
                    box = [x1, y1, x2, y2]

                    queue_name, overlap = self._assign_box_to_queue(box, queue_zones, min_overlap=min_overlap)
                    if queue_name is not None:
                        frame_counts[queue_name] += 1
                        assignment_by_id[track_id] = queue_name
                        color = (255, 120, 0)
                    else:
                        color = (160, 160, 160)

                    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                    if queue_name is not None:
                        cv2.putText(
                            frame,
                            f"ID {track_id} {queue_name} ({overlap:.2f})",
                            (x1, max(20, y1 - 8)),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.5,
                            color,
                            2,
                        )

            counts_history.append(frame_counts)

            if len(counts_history) > 1:
                smooth_counts: dict[str, int] = {}
                window = max(1, smoothing_window)
                recent = counts_history[-window:]
                for q in queue_names:
                    values = [hist[q] for hist in recent]
                    smooth_counts[q] = int(round(float(np.median(values))))
            else:
                smooth_counts = frame_counts

            best_queue = self._choose_best_queue(smooth_counts, min_valid_count=min_valid_count)

            for qname, polygon in queue_zones.items():
                is_best = qname == best_queue
                color = (0, 255, 0) if is_best else (120, 120, 120)
                label = f"{qname}: {smooth_counts[qname]}" + ("  BEST" if is_best else "")
                self._draw_zone(frame, polygon, color=color, label=label)

            writer.write(frame)
            processed_frames += 1
            if processed_frames % max(1, live_update_every) == 0:
                # Live UI should move quickly; use short recent window.
                recent_live = counts_history[-3:] if len(counts_history) >= 3 else counts_history
                live_counts = {q: 0 for q in queue_names}
                for q in queue_names:
                    values = [h[q] for h in recent_live]
                    live_counts[q] = int(round(float(np.mean(values)))) if values else 0
                self.latest_result = {
                    "processed_frames": processed_frames,
                    "fps": round(max(1.0, fps), 2),
                    "queue_counts": live_counts,
                    "best_queue": self._choose_best_queue(live_counts, min_valid_count=min_valid_count),
                    "min_valid_count": int(min_valid_count),
                    "output_video_path": str(output_path),
                    "updated_at": int(time.time()),
                }
            if processed_frames >= max(1, int(max_frames)):
                break

        writer.release()
        Path(tmp_path).unlink(missing_ok=True)

        final_counts = {q: 0 for q in queue_names}
        if counts_history:
            window = max(1, smoothing_window)
            recent = counts_history[-window:]
            for q in queue_names:
                final_counts[q] = int(round(float(np.median([h[q] for h in recent]))))
        best_queue = self._choose_best_queue(final_counts, min_valid_count=min_valid_count)

        payload = {
            "processed_frames": processed_frames,
            "fps": round(max(1.0, fps), 2),
            "queue_counts": final_counts,
            "best_queue": best_queue,
            "min_valid_count": int(min_valid_count),
            "output_video_path": str(output_path),
            "updated_at": int(time.time()),
        }
        self.latest_result = payload
        return payload

    def latest(self) -> dict[str, Any]:
        if self.latest_result is None:
            return {
                "processed_frames": 0,
                "fps": 0.0,
                "queue_counts": {},
                "best_queue": "N/A",
                "min_valid_count": 1,
                "output_video_path": "",
                "updated_at": None,
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
        iou: float,
        imgsz: int,
        frame_stride: int,
        min_overlap: float,
        min_valid_count: int,
        max_frames: int,
    ) -> None:
        # Reset visible latest value at job start to avoid stale data from previous run.
        self.latest_result = {
            "processed_frames": 0,
            "fps": 0.0,
            "queue_counts": {},
            "best_queue": "N/A",
            "min_valid_count": int(min_valid_count),
            "output_video_path": "",
            "updated_at": int(time.time()),
        }
        self.latest_job = {
            "job_id": job_id,
            "status": "running",
            "message": "Queue analysis in progress.",
            "updated_at": int(time.time()),
        }
        try:
            self.analyze_video(
                video_bytes,
                conf_person=conf_person,
                iou=iou,
                imgsz=imgsz,
                frame_stride=frame_stride,
                min_overlap=min_overlap,
                min_valid_count=min_valid_count,
                max_frames=max_frames,
            )
            self.latest_job = {
                "job_id": job_id,
                "status": "completed",
                "message": "Queue analysis completed.",
                "updated_at": int(time.time()),
            }
        except Exception as exc:
            self.latest_job = {
                "job_id": job_id,
                "status": "failed",
                "message": f"Queue analysis failed: {exc}",
                "updated_at": int(time.time()),
            }

    def submit_video_job(
        self,
        video_bytes: bytes,
        conf_person: float = 0.25,
        iou: float = 0.5,
        imgsz: int = 1280,
        frame_stride: int = 1,
        min_overlap: float = 0.2,
        min_valid_count: int = 1,
        max_frames: int = 600,
    ) -> dict[str, str]:
        if self.latest_job.get("status") == "running":
            return {
                "job_id": str(self.latest_job.get("job_id") or ""),
                "status": "running",
                "message": "A queue analysis job is already running.",
            }

        job_id = str(uuid.uuid4())
        self.latest_job = {
            "job_id": job_id,
            "status": "queued",
            "message": "Queue analysis queued.",
            "updated_at": int(time.time()),
        }
        self.executor.submit(
            self._run_job,
            job_id=job_id,
            video_bytes=video_bytes,
            conf_person=conf_person,
            iou=iou,
            imgsz=imgsz,
            frame_stride=frame_stride,
            min_overlap=min_overlap,
            min_valid_count=min_valid_count,
            max_frames=max_frames,
        )
        return {
            "job_id": job_id,
            "status": "queued",
            "message": "Queue analysis started in background.",
        }


model5_service = Model5Service()
