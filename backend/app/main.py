from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from PIL import UnidentifiedImageError

from app.core.config import settings
from app.schemas import DetectResponse, ProductPrediction
from app.services.model_service import product_service

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/detect", response_model=DetectResponse)
async def detect(
    image: UploadFile = File(...),
    top_k: int = Query(default=settings.top_k, ge=1, le=10),
) -> DetectResponse:
    # Some mobile clients upload camera files as application/octet-stream.
    # We accept it and validate by attempting real image decoding.
    if image.content_type and not (
        image.content_type.startswith("image/")
        or image.content_type == "application/octet-stream"
    ):
        raise HTTPException(status_code=400, detail="Only image uploads are supported.")

    payload = await image.read()
    if not payload:
        raise HTTPException(status_code=400, detail="Empty image file.")

    try:
        predictions = product_service.detect_and_retrieve(payload, top_k=top_k)
    except UnidentifiedImageError as exc:
        raise HTTPException(status_code=400, detail="Invalid image content.") from exc
    except OSError as exc:
        raise HTTPException(status_code=400, detail="Invalid image content.") from exc

    return DetectResponse(predictions=[ProductPrediction(**pred) for pred in predictions])
