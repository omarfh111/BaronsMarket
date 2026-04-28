# Backend - FastAPI AI Gateway

This backend serves both:
- mobile client APIs
- employee web APIs and static web app at `/employee`

## Modules

1. Product retrieval (Model 1)
- `/detect`
- YOLO + CLIP + FAISS

2. Meat freshness (Model 2)
- `/meat-freshness`

3. Animal & Bag (Model 3)
- `/model3/predict-image`
- `/model3/analyze-video`

4. Theft surveillance (Model 4)
- `/theft/analyze-video`
- `/theft/analyze-youtube`

5. Queue recommendation (Model 5)
- `/queue-recommendation/submit-video` (async job)
- `/queue-recommendation/job-latest`
- `/queue-recommendation/latest`
- `/queue-recommendation/analyze-video` (sync/debug)

## Requirements

Install from `requirements.txt`:
- fastapi, uvicorn, python-multipart
- pydantic-settings
- numpy, pillow, opencv-python
- faiss-cpu
- torch, torchvision, timm
- transformers
- ultralytics
- lap

## Environment Setup

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

## Important ENV variables

`.env` includes:
- model1 paths (`YOLO_MODEL_PATH`, `FAISS_INDEX_PATH`, ...)
- model3 path (`MODEL3_WEIGHTS_PATH`)
- model4 paths (`MODEL4_PERSON_WEIGHTS_PATH`, `MODEL4_THEFT_WEIGHTS_PATH`)
- model5 paths (`MODEL5_WEIGHTS_PATH`, `MODEL5_QUEUE_ZONES_PATH`, `MODEL5_OUTPUT_DIR`)

## Run

```powershell
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Health check:

```powershell
curl http://127.0.0.1:8000/health
```

Employee web:

```text
http://127.0.0.1:8000/employee/
```

## Queue Recommendation Runtime Notes

- Uses notebook-aligned config from:
  - `ml/models/model_5/queue_config.json` (priority)
  - `model/model_5/queue_zones.json` (fallback)
- Queue assignment uses foot-point + overlap logic.
- Async job updates latest recommendation during processing.

## YouTube Endpoints

YouTube depends on runtime environment.
If direct stream fails, install and configure:
- `ffmpeg`
- `yt-dlp`
