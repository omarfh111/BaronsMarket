from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from PIL import UnidentifiedImageError

from app.core.config import settings
from app.schemas import (
    AssistantChatRequest,
    AssistantChatResponse,
    CatalogResponse,
    CheckoutSaveRequest,
    CheckoutSaveResponse,
    DetectResponse,
    IntegrationsHealthResponse,
    FidelityCardResponse,
    ForgedDocsResponse,
    EmployeeAccessResponse,
    EmployeeFaceRegisterResponse,
    MeatFreshnessResponse,
    Model3ImageResponse,
    Model3VideoResponse,
    ProductPrediction,
    QueueRecommendationJobResponse,
    QueueRecommendationJobStatusResponse,
    QueueRecommendationResponse,
    StoreAnalyticsResponse,
    TheftVideoJobResponse,
    TheftVideoJobStatusResponse,
    TheftVideoResponse,
    VegetableFreshnessResponse,
)
from app.services.catalog_service import catalog_service
from app.services.checkout_service import checkout_repository, integrations_health_service
from app.services.device import device_info
from app.services.model5_service import model5_service
from app.services.model6_service import vegetable_freshness_service
from app.services.meat_freshness_service import meat_freshness_service
from app.services.assistant_service import assistant_service
from app.services.model3_service import model3_service
from app.services.model4_service import model4_service
from app.services.model_service import product_service
from app.services.qdrant_service import qdrant_service
from app.services.model7_service import fidelity_card_service
from app.services.model8_service import forged_docs_service
from app.services.model9_service import employee_access_service
from app.services.store_analytics_service import store_analytics_service

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

project_root = Path(__file__).resolve().parents[2]
employee_web_dir = project_root / "apps" / "web-employee" / "public"
if employee_web_dir.exists():
    app.mount("/employee", StaticFiles(directory=str(employee_web_dir), html=True), name="employee")


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/models/device")
def models_device() -> dict:
    return device_info()


@app.get("/integrations/health", response_model=IntegrationsHealthResponse)
def integrations_health() -> IntegrationsHealthResponse:
    return IntegrationsHealthResponse(**integrations_health_service.check())


@app.post("/assistant/chat", response_model=AssistantChatResponse)
def assistant_chat(payload: AssistantChatRequest) -> AssistantChatResponse:
    result = assistant_service.chat(
        user_message=payload.message,
        session_id=payload.session_id,
        budget_tnd=payload.budget_tnd,
        cart_items=[item.model_dump() for item in payload.cart_items],
    )
    return AssistantChatResponse(**result)


@app.post("/checkout/save", response_model=CheckoutSaveResponse)
def checkout_save(payload: CheckoutSaveRequest) -> CheckoutSaveResponse:
    result = checkout_repository.save_checkout(payload.model_dump())
    return CheckoutSaveResponse(**result)


@app.get("/analytics/store", response_model=StoreAnalyticsResponse)
def analytics_store(
    days: int = Query(default=30, ge=1, le=365),
    top_k: int = Query(default=8, ge=3, le=20),
) -> StoreAnalyticsResponse:
    result = store_analytics_service.analyze(days=days, top_k=top_k)
    return StoreAnalyticsResponse(**result)


@app.post("/qdrant/ingest-catalog")
def qdrant_ingest_catalog(limit: int = Query(default=2000, ge=1, le=5000)) -> dict:
    return qdrant_service.ingest_catalog(limit=limit)


@app.get("/qdrant/search-products")
def qdrant_search_products(query: str = Query(..., min_length=1), top_k: int = Query(default=5, ge=1, le=10)) -> dict:
    return {"items": qdrant_service.search_products(query=query, top_k=top_k)}


@app.get("/catalog/products", response_model=CatalogResponse)
async def catalog_products(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=30, ge=1, le=100),
    category: str | None = Query(default=None),
    query: str | None = Query(default=None),
) -> CatalogResponse:
    data = catalog_service.list_products(
        page=page,
        page_size=page_size,
        category=category,
        query=query,
    )
    return CatalogResponse(**data)


@app.get("/catalog/image/{product_id}")
async def catalog_image(product_id: str) -> FileResponse:
    image_path = catalog_service.get_image_path(product_id)
    if image_path is None or not image_path.exists():
        raise HTTPException(status_code=404, detail="Product image not found.")
    return FileResponse(str(image_path))


@app.post("/fidelity/verify", response_model=FidelityCardResponse)
async def fidelity_verify(image: UploadFile = File(...)) -> FidelityCardResponse:
    if image.content_type and not (
        image.content_type.startswith("image/")
        or image.content_type == "application/octet-stream"
    ):
        raise HTTPException(status_code=400, detail="Only image uploads are supported.")

    payload = await image.read()
    if not payload:
        raise HTTPException(status_code=400, detail="Empty image file.")

    try:
        result = fidelity_card_service.verify(payload)
    except UnidentifiedImageError as exc:
        raise HTTPException(status_code=400, detail="Invalid image content.") from exc
    except OSError as exc:
        raise HTTPException(status_code=400, detail="Invalid image content.") from exc

    return FidelityCardResponse(**result)


@app.post("/model8/verify-doc", response_model=ForgedDocsResponse)
async def verify_forged_doc(image: UploadFile = File(...)) -> ForgedDocsResponse:
    if image.content_type and not (
        image.content_type.startswith("image/")
        or image.content_type == "application/octet-stream"
    ):
        raise HTTPException(status_code=400, detail="Only image uploads are supported.")

    payload = await image.read()
    if not payload:
        raise HTTPException(status_code=400, detail="Empty image file.")

    try:
        result = forged_docs_service.verify(payload)
    except UnidentifiedImageError as exc:
        raise HTTPException(status_code=400, detail="Invalid image content.") from exc
    except OSError as exc:
        raise HTTPException(status_code=400, detail="Invalid image content.") from exc

    return ForgedDocsResponse(**result)


@app.post("/model9/verify-access", response_model=EmployeeAccessResponse)
async def verify_employee_access(image: UploadFile = File(...)) -> EmployeeAccessResponse:
    if image.content_type and not (
        image.content_type.startswith("image/")
        or image.content_type == "application/octet-stream"
    ):
        raise HTTPException(status_code=400, detail="Only image uploads are supported.")

    payload = await image.read()
    if not payload:
        raise HTTPException(status_code=400, detail="Empty image file.")

    try:
        result = employee_access_service.verify(payload)
    except UnidentifiedImageError as exc:
        raise HTTPException(status_code=400, detail="Invalid image content.") from exc
    except OSError as exc:
        raise HTTPException(status_code=400, detail="Invalid image content.") from exc

    return EmployeeAccessResponse(**result)


@app.post("/model9/register-face", response_model=EmployeeFaceRegisterResponse)
async def register_employee_face(
    employee_name: str = Query(..., min_length=1),
    image: UploadFile = File(...),
) -> EmployeeFaceRegisterResponse:
    if image.content_type and not (
        image.content_type.startswith("image/")
        or image.content_type == "application/octet-stream"
    ):
        raise HTTPException(status_code=400, detail="Only image uploads are supported.")

    payload = await image.read()
    if not payload:
        raise HTTPException(status_code=400, detail="Empty image file.")

    try:
        result = employee_access_service.register_face(payload, employee_name=employee_name.strip())
    except UnidentifiedImageError as exc:
        raise HTTPException(status_code=400, detail="Invalid image content.") from exc
    except OSError as exc:
        raise HTTPException(status_code=400, detail="Invalid image content.") from exc

    return EmployeeFaceRegisterResponse(**result)


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


@app.post("/meat-freshness", response_model=MeatFreshnessResponse)
async def meat_freshness(image: UploadFile = File(...)) -> MeatFreshnessResponse:
    if image.content_type and not (
        image.content_type.startswith("image/")
        or image.content_type == "application/octet-stream"
    ):
        raise HTTPException(status_code=400, detail="Only image uploads are supported.")

    payload = await image.read()
    if not payload:
        raise HTTPException(status_code=400, detail="Empty image file.")

    try:
        result = meat_freshness_service.predict(payload)
    except UnidentifiedImageError as exc:
        raise HTTPException(status_code=400, detail="Invalid image content.") from exc
    except OSError as exc:
        raise HTTPException(status_code=400, detail="Invalid image content.") from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return MeatFreshnessResponse(**result)


@app.post("/vegetable-freshness", response_model=VegetableFreshnessResponse)
async def vegetable_freshness(image: UploadFile = File(...)) -> VegetableFreshnessResponse:
    if image.content_type and not (
        image.content_type.startswith("image/")
        or image.content_type == "application/octet-stream"
    ):
        raise HTTPException(status_code=400, detail="Only image uploads are supported.")

    payload = await image.read()
    if not payload:
        raise HTTPException(status_code=400, detail="Empty image file.")

    try:
        result = vegetable_freshness_service.predict(payload)
    except UnidentifiedImageError as exc:
        raise HTTPException(status_code=400, detail="Invalid image content.") from exc
    except OSError as exc:
        raise HTTPException(status_code=400, detail="Invalid image content.") from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return VegetableFreshnessResponse(**result)


@app.post("/model3/predict-image", response_model=Model3ImageResponse)
async def model3_predict_image(
    image: UploadFile = File(...),
    min_confidence: float = Query(default=0.6, ge=0.0, le=1.0),
) -> Model3ImageResponse:
    if image.content_type and not (
        image.content_type.startswith("image/")
        or image.content_type == "application/octet-stream"
    ):
        raise HTTPException(status_code=400, detail="Only image uploads are supported.")

    payload = await image.read()
    if not payload:
        raise HTTPException(status_code=400, detail="Empty image file.")

    try:
        result = model3_service.predict_image_bytes(payload, min_confidence=min_confidence)
    except UnidentifiedImageError as exc:
        raise HTTPException(status_code=400, detail="Invalid image content.") from exc
    except OSError as exc:
        raise HTTPException(status_code=400, detail="Invalid image content.") from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return Model3ImageResponse(**result)


@app.post("/model3/analyze-video", response_model=Model3VideoResponse)
async def model3_analyze_video(
    video: UploadFile = File(...),
    sample_every_sec: float = Query(default=1.0, ge=0.2, le=10.0),
    event_threshold: float = Query(default=0.6, ge=0.0, le=1.0),
    min_confidence: float = Query(default=0.6, ge=0.0, le=1.0),
    target_label: str = Query(default="all", pattern="^(all|animal|bag)$"),
) -> Model3VideoResponse:
    payload = await video.read()
    if not payload:
        raise HTTPException(status_code=400, detail="Empty video file.")

    try:
        result = model3_service.analyze_video_bytes(
            payload,
            sample_every_sec=sample_every_sec,
            event_threshold=event_threshold,
            min_confidence=min_confidence,
            target_label=target_label,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return Model3VideoResponse(**result)


@app.post("/model3/analyze-youtube")
async def model3_analyze_youtube() -> dict[str, str]:
    return {
        "status": "coming_soon",
        "message": "YouTube URL analysis endpoint reserved. Not enabled yet.",
    }


@app.post("/theft/analyze-video", response_model=TheftVideoResponse)
async def theft_analyze_video(
    video: UploadFile = File(...),
    conf_person: float = Query(default=0.3, ge=0.0, le=1.0),
    conf_theft: float = Query(default=0.4, ge=0.0, le=1.0),
    frame_stride: int = Query(default=2, ge=1, le=10),
) -> TheftVideoResponse:
    payload = await video.read()
    if not payload:
        raise HTTPException(status_code=400, detail="Empty video file.")
    result = model4_service.analyze_video(
        payload,
        conf_person=conf_person,
        conf_theft=conf_theft,
        frame_stride=frame_stride,
    )
    return TheftVideoResponse(**result)


@app.post("/theft/submit-video", response_model=TheftVideoJobResponse)
async def theft_submit_video(
    video: UploadFile = File(...),
    conf_person: float = Query(default=0.3, ge=0.0, le=1.0),
    conf_theft: float = Query(default=0.4, ge=0.0, le=1.0),
    frame_stride: int = Query(default=2, ge=1, le=10),
    max_frames: int = Query(default=0, ge=0, le=5000),
) -> TheftVideoJobResponse:
    payload = await video.read()
    if not payload:
        raise HTTPException(status_code=400, detail="Empty video file.")
    job = model4_service.submit_video_job(
        payload,
        conf_person=conf_person,
        conf_theft=conf_theft,
        frame_stride=frame_stride,
        max_frames=max_frames or None,
    )
    return TheftVideoJobResponse(**job)


@app.get("/theft/latest", response_model=TheftVideoResponse)
async def theft_latest() -> TheftVideoResponse:
    return TheftVideoResponse(**model4_service.latest())


@app.get("/theft/job-latest", response_model=TheftVideoJobStatusResponse)
async def theft_job_latest() -> TheftVideoJobStatusResponse:
    return TheftVideoJobStatusResponse(**model4_service.latest_job_status())


@app.get("/theft/suspect-faces")
async def theft_suspect_faces(limit: int = Query(default=60, ge=1, le=200)) -> dict:
    return model4_service.list_suspect_faces(limit=limit)


@app.post("/theft/analyze-youtube", response_model=TheftVideoResponse)
async def theft_analyze_youtube(
    youtube_url: str = Query(..., min_length=10),
    conf_person: float = Query(default=0.3, ge=0.0, le=1.0),
    conf_theft: float = Query(default=0.4, ge=0.0, le=1.0),
    frame_stride: int = Query(default=2, ge=1, le=10),
    max_frames: int = Query(default=900, ge=60, le=5000),
) -> TheftVideoResponse:
    try:
        result = model4_service.analyze_youtube(
            youtube_url=youtube_url,
            conf_person=conf_person,
            conf_theft=conf_theft,
            frame_stride=frame_stride,
            max_frames=max_frames,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Impossible de lire le lien YouTube directement. Detail: {exc}",
        ) from exc
    return TheftVideoResponse(**result)


@app.post("/queue-recommendation/analyze-video", response_model=QueueRecommendationResponse)
async def queue_recommendation_analyze_video(
    video: UploadFile = File(...),
    conf_person: float = Query(default=0.25, ge=0.0, le=1.0),
    iou: float = Query(default=0.5, ge=0.0, le=1.0),
    imgsz: int = Query(default=1280, ge=320, le=1920),
    frame_stride: int = Query(default=1, ge=1, le=10),
    min_overlap: float = Query(default=0.2, ge=0.0, le=1.0),
    min_valid_count: int = Query(default=1, ge=0, le=100),
) -> QueueRecommendationResponse:
    payload = await video.read()
    if not payload:
        raise HTTPException(status_code=400, detail="Empty video file.")
    try:
        result = model5_service.analyze_video(
            payload,
            conf_person=conf_person,
            iou=iou,
            imgsz=imgsz,
            frame_stride=frame_stride,
            min_overlap=min_overlap,
            min_valid_count=min_valid_count,
        )
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return QueueRecommendationResponse(**result)


@app.get("/queue-recommendation/latest", response_model=QueueRecommendationResponse)
async def queue_recommendation_latest() -> QueueRecommendationResponse:
    return QueueRecommendationResponse(**model5_service.latest())


@app.post("/queue-recommendation/submit-video", response_model=QueueRecommendationJobResponse)
async def queue_recommendation_submit_video(
    video: UploadFile = File(...),
    conf_person: float = Query(default=0.25, ge=0.0, le=1.0),
    iou: float = Query(default=0.5, ge=0.0, le=1.0),
    imgsz: int = Query(default=1280, ge=320, le=1920),
    frame_stride: int = Query(default=1, ge=1, le=10),
    min_overlap: float = Query(default=0.2, ge=0.0, le=1.0),
    min_valid_count: int = Query(default=1, ge=0, le=100),
    max_frames: int = Query(default=3000, ge=60, le=5000),
) -> QueueRecommendationJobResponse:
    payload = await video.read()
    if not payload:
        raise HTTPException(status_code=400, detail="Empty video file.")
    try:
        job = model5_service.submit_video_job(
            payload,
            conf_person=conf_person,
            iou=iou,
            imgsz=imgsz,
            frame_stride=frame_stride,
            min_overlap=min_overlap,
            min_valid_count=min_valid_count,
            max_frames=max_frames,
        )
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return QueueRecommendationJobResponse(**job)


@app.get("/queue-recommendation/job-latest", response_model=QueueRecommendationJobStatusResponse)
async def queue_recommendation_job_latest() -> QueueRecommendationJobStatusResponse:
    return QueueRecommendationJobStatusResponse(**model5_service.latest_job_status())


@app.post("/queue-recommendation/analyze-youtube", response_model=QueueRecommendationResponse)
async def queue_recommendation_analyze_youtube() -> QueueRecommendationResponse:
    raise HTTPException(
        status_code=400,
        detail="YouTube direct stream not enabled yet for queue recommendation on this environment.",
    )
