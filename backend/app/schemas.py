from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class ProductPrediction(BaseModel):
    name: str
    brand: str
    price: float
    image: str
    confidence: Optional[float] = None
    detector_confidence: Optional[float] = None


class DetectResponse(BaseModel):
    predictions: list[ProductPrediction]


class MeatFreshnessResponse(BaseModel):
    label: str
    confidence: float
    probabilities: dict[str, float]


class VegetableFreshnessResponse(BaseModel):
    label: str
    confidence: float
    probabilities: dict[str, float]


class Model3ImageResponse(BaseModel):
    label: str
    raw_label: str
    confidence: float
    probabilities: dict[str, float]
    bbox: list[int]
    annotated_image_data_url: str


class Model3VideoEvent(BaseModel):
    timestamp_sec: float
    label: str
    raw_label: str
    confidence: float
    bbox: list[int]
    snapshot_data_url: str


class Model3VideoResponse(BaseModel):
    fps: float
    sampled_frames: int
    class_counts: dict[str, int]
    events: list[Model3VideoEvent]
    event_threshold: float
    sample_every_sec: float
    min_confidence: float
    target_label: str


class TheftVideoEvent(BaseModel):
    track_id: int
    status: str
    timestamp_sec: float
    person_bbox: list[int]
    face_bbox: list[int] | None = None
    saved_source: str
    saved_image_path: str
    saved_image_data_url: str
    snapshot_data_url: str


class TheftVideoResponse(BaseModel):
    processed_frames: int
    fps: float
    status_counts: dict[str, int]
    events: list[TheftVideoEvent]


class TheftVideoJobResponse(BaseModel):
    job_id: str
    status: str
    message: str


class TheftVideoJobStatusResponse(BaseModel):
    job_id: str | None = None
    status: str
    message: str
    updated_at: int | None = None


class QueueRecommendationResponse(BaseModel):
    processed_frames: int
    fps: float
    queue_counts: dict[str, int]
    best_queue: str
    min_valid_count: int
    output_video_path: str


class QueueRecommendationJobResponse(BaseModel):
    job_id: str
    status: str
    message: str


class QueueRecommendationJobStatusResponse(BaseModel):
    job_id: str | None = None
    status: str
    message: str
    updated_at: int | None = None


class CatalogProduct(BaseModel):
    id: str
    name: str
    brand: str
    price: float
    category: str
    image: str


class CatalogResponse(BaseModel):
    items: list[CatalogProduct]
    total: int
    page: int
    page_size: int
    categories: list[str]


class AssistantChatMessage(BaseModel):
    role: str
    content: str


class AssistantCartItem(BaseModel):
    product_id: str | None = None
    name: str
    brand: str
    quantity: int = Field(default=1, ge=1)
    unit_price: float = Field(default=0.0, ge=0.0)


class AssistantChatRequest(BaseModel):
    message: str = Field(min_length=1)
    session_id: str | None = None
    budget_tnd: float | None = Field(default=None, ge=0.0)
    cart_items: list[AssistantCartItem] = Field(default_factory=list)


class AssistantChatResponse(BaseModel):
    session_id: str
    active_agent: str
    assistant_message: str
    mode: str = "step_by_step"
    steps: list[str] = Field(default_factory=list)
    show_products_now: bool = False
    recommended_products: list[dict[str, Any]] = Field(default_factory=list)


class CheckoutItem(BaseModel):
    product_id: str | None = None
    name: str
    brand: str
    quantity: int = Field(ge=1)
    unit_price: float = Field(ge=0.0)


class CheckoutSaveRequest(BaseModel):
    cart_id: str | None = None
    recommended_queue: str
    total_price: float = Field(ge=0.0)
    items: list[CheckoutItem] = Field(default_factory=list)
    created_at_unix_ms: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class CheckoutSaveResponse(BaseModel):
    cart_id: str
    recommended_queue: str
    total_price: float
    checkout_at_unix_ms: int
    duration_seconds: int | None = None
    stored_in: str


class IntegrationStatus(BaseModel):
    configured: bool
    ok: bool
    details: str


class IntegrationsHealthResponse(BaseModel):
    openai: IntegrationStatus
    supabase: IntegrationStatus
    qdrant: IntegrationStatus


class FidelityCardResponse(BaseModel):
    valid: bool
    discount_percent: int
    message: str
    card_id: str | None = None
    customer_name: str | None = None
    cnn_class: str | None = None
    cnn_confidence: float | None = None
    ocr_pass: str | None = None


class ForgedDocsResponse(BaseModel):
    ok: bool
    message: str
    is_forged: bool
    score: float
    threshold: float
    mask_data_url: str
    heatmap_data_url: str
    original_data_url: str


class EmployeeAccessResponse(BaseModel):
    ok: bool
    message: str
    access_granted: bool
    liveness_score: float
    liveness_threshold: float
    badge_ok: bool
    badge_text: str
    expected_badge_text: str
    face_detected: bool
    face_registered: bool = False
    employee_name: str | None = None
    debug: dict[str, Any] = Field(default_factory=dict)


class EmployeeFaceRegisterResponse(BaseModel):
    ok: bool
    message: str
    employee_name: str
    stored_in: str


class EmployeeFaceEnrollResponse(BaseModel):
    ok: bool
    message: str
    employee_name: str
    stored_in: str
    embedding_dim: int


class AnalyticsCandle(BaseModel):
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int


class AnalyticsSeriesPoint(BaseModel):
    date: str
    value: float


class AnalyticsTopProduct(BaseModel):
    name: str
    brand: str
    quantity: int
    revenue: float
    avg_price: float


class AnalyticsStockRisk(BaseModel):
    name: str
    brand: str
    estimated_days_left: float
    avg_daily_qty: float
    risk_level: str


class AnalyticsAgentInsight(BaseModel):
    agent: str
    title: str
    summary: str
    recommendations: list[str] = Field(default_factory=list)
    details: list[str] = Field(default_factory=list)


class StoreAnalyticsResponse(BaseModel):
    ok: bool
    message: str
    kpis: dict[str, Any]
    revenue_candles: list[AnalyticsCandle]
    revenue_trend: list[AnalyticsSeriesPoint]
    top_products: list[AnalyticsTopProduct]
    queue_distribution: dict[str, int]
    queue_revenue: dict[str, float]
    avg_time_in_store_sec: float
    predicted_next_day_revenue: float
    stock_risk: list[AnalyticsStockRisk]
    agent_insights: list[AnalyticsAgentInsight]
