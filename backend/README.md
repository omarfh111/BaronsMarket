# Backend - FastAPI Inference Service

## What this service does

1. Detect product area with YOLOv8 (`best.pt`)
2. Build CLIP image embedding from crop (or full image fallback)
3. Retrieve top matching products with FAISS
4. Return normalized product payload used by mobile app

## Python dependencies

Install exactly from `requirements.txt`:

- fastapi, uvicorn, python-multipart
- pydantic-settings
- numpy, Pillow, opencv-python
- faiss-cpu
- torch, transformers, ultralytics

## System requirements

- Python `3.10+` recommended
- Model assets available under `../model/model_1/`
- Enough RAM for model/index loading

## Environment variables

Copy `.env.example` to `.env` and adjust if needed:

- `MODEL_DIR`
- `YOLO_MODEL_PATH`
- `FAISS_INDEX_PATH`
- `PRODUCT_EMBEDDINGS_PATH`
- `PRODUCTS_JSON_PATH`
- `YOLO_CONFIDENCE`
- `TOP_K`

## Setup

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

## Run

```powershell
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Health:

```powershell
curl http://127.0.0.1:8000/health
```

## API

### `GET /health`

Returns:

```json
{ "status": "ok" }
```

### `POST /detect`

- Content type: `multipart/form-data`
- File field: `image`
- Optional query param: `top_k` (`1..10`)

Response:

```json
{
  "predictions": [
    {
      "name": "Spaghetti bucatini",
      "brand": "SPIGA",
      "price": 0.41,
      "image": "https://...",
      "confidence": 0.82,
      "detector_confidence": 0.93
    }
  ]
}
```

## Notes

- Mobile uploads with `application/octet-stream` are accepted and validated as real images.
- Price parsing supports formats like `"0,410 DT"` and normalizes to float.
