
import cv2
import numpy as np
import pandas as pd
from ultralytics import YOLO
import json
from queue_utils import assign_box_to_queue, choose_best_queue

VIDEO_PATH = "input.mp4"
MODEL_PATH = "yolov8m.pt"

# Load config
with open("queue_config.json") as f:
    config = json.load(f)

QUEUE_ZONES = {k: np.array(v, dtype=np.int32) for k, v in config["zones"].items()}
zone_colors = config["zone_colors"]

model = YOLO(MODEL_PATH)

cap = cv2.VideoCapture(VIDEO_PATH)

while True:
    ret, frame = cap.read()
    if not ret:
        break

    results = model.track(
        frame,
        persist=True,
        conf=config["detection"]["conf"],
        iou=config["detection"]["iou"],
        imgsz=config["detection"]["imgsz"],
        classes=config["detection"]["classes"],
        verbose=False
    )

    boxes = results[0].boxes
    queue_counts = {q: 0 for q in QUEUE_ZONES}

    if boxes is not None:
        for box in boxes:
            qname, overlap = assign_box_to_queue(
                box,
                QUEUE_ZONES,
                min_overlap=config["assignment"]["min_overlap"]
            )
            if qname:
                queue_counts[qname] += 1

    best_queue = choose_best_queue(queue_counts, min_valid_count=1)

    print(best_queue, queue_counts)

cap.release()
