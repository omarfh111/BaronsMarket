from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = Field(default="Smart Shopping Assistant API", alias="APP_NAME")
    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")

    model_dir: Path = Field(default=Path("../model/model_1"), alias="MODEL_DIR")
    yolo_model_path: Path = Field(default=Path("../model/model_1/best.pt"), alias="YOLO_MODEL_PATH")
    faiss_index_path: Path = Field(default=Path("../model/model_1/index.faiss"), alias="FAISS_INDEX_PATH")
    product_embeddings_path: Path = Field(
        default=Path("../model/model_1/product_embeddings_aug.npy"),
        alias="PRODUCT_EMBEDDINGS_PATH",
    )
    products_json_path: Path = Field(
        default=Path("../model/model_1/products_clean .json"),
        alias="PRODUCTS_JSON_PATH",
    )

    yolo_confidence: float = Field(default=0.25, alias="YOLO_CONFIDENCE")
    top_k: int = Field(default=3, alias="TOP_K")
    model_device: str = Field(default="auto", alias="MODEL_DEVICE")

    model3_weights_path: Path = Field(
        default=Path("../ml/models/model_3/final_model_efficientnetB0_____ (1).pth"),
        alias="MODEL3_WEIGHTS_PATH",
    )
    model3_image_size: int = Field(default=224, alias="MODEL3_IMAGE_SIZE")
    model4_person_weights_path: Path = Field(
        default=Path("../ml/models/model_4/person_model.pt"),
        alias="MODEL4_PERSON_WEIGHTS_PATH",
    )
    model4_theft_weights_path: Path = Field(
        default=Path("../ml/models/model_4/theft_model.pt"),
        alias="MODEL4_THEFT_WEIGHTS_PATH",
    )
    model5_weights_path: str = Field(default="yolov8m.pt", alias="MODEL5_WEIGHTS_PATH")
    model5_queue_zones_path: Path = Field(
        default=Path("../model/model_5/queue_zones.json"),
        alias="MODEL5_QUEUE_ZONES_PATH",
    )
    model5_output_dir: Path = Field(default=Path("./outputs/model5"), alias="MODEL5_OUTPUT_DIR")
    model6_weights_path: Path = Field(
        default=Path("../model/model_6/mobilenet_v3_large_best.pt"),
        alias="MODEL6_WEIGHTS_PATH",
    )
    model6_pipeline_state_path: Path = Field(
        default=Path("../model/model_6/pipeline_state.pkl"),
        alias="MODEL6_PIPELINE_STATE_PATH",
    )
    market_catalog_dir: Path = Field(default=Path("../market"), alias="MARKET_CATALOG_DIR")

    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")
    openai_base_url: str = Field(default="https://api.openai.com/v1", alias="OPENAI_BASE_URL")
    openai_embedding_model: str = Field(default="text-embedding-3-small", alias="OPENAI_EMBEDDING_MODEL")

    supabase_url: str = Field(default="", alias="SUPABASE_URL")
    supabase_service_role_key: str = Field(default="", alias="SUPABASE_SERVICE_ROLE_KEY")
    supabase_checkout_table: str = Field(default="checkout_sessions", alias="SUPABASE_CHECKOUT_TABLE")

    qdrant_url: str = Field(default="", alias="QDRANT_URL")
    qdrant_api_key: str = Field(default="", alias="QDRANT_API_KEY")
    qdrant_collection_name: str = Field(default="product_knowledge", alias="QDRANT_COLLECTION_NAME")

    model7_checkpoint_path: Path = Field(
        default=Path("../model/model_7/fidelity_checkpoint_20260501_1147.pth"),
        alias="MODEL7_CHECKPOINT_PATH",
    )
    model7_db_json_path: Path = Field(
        default=Path("../model/model_7/fidelity_db.json"),
        alias="MODEL7_DB_JSON_PATH",
    )
    model7_cnn_threshold: float = Field(default=0.75, alias="MODEL7_CNN_THRESHOLD")

    model8_code_dir: Path = Field(default=Path("../ml/models/model_8_code"), alias="MODEL8_CODE_DIR")
    model8_checkpoint_path: Path = Field(
        default=Path("../ml/models/model_8/dtd_seg_finetuned_best.pth"),
        alias="MODEL8_CHECKPOINT_PATH",
    )
    # Inference threshold aligned with notebook inference cell.
    model8_threshold: float = Field(default=0.000240, alias="MODEL8_THRESHOLD")
    model8_quality: int = Field(default=90, alias="MODEL8_QUALITY")
    model8_forged_class_idx: int = Field(default=1, alias="MODEL8_FORGED_CLASS_IDX")
    model8_require_true_jpeg: bool = Field(default=True, alias="MODEL8_REQUIRE_TRUE_JPEG")

    model9_dir: Path = Field(default=Path("../ml/models/model_9"), alias="MODEL9_DIR")
    model9_supermarket_name: str = Field(default="Monoprix", alias="MODEL9_SUPERMARKET_NAME")
    model9_liveness_min: float = Field(default=0.90, alias="MODEL9_LIVENESS_MIN")
    model9_face_table: str = Field(default="employee_faces", alias="MODEL9_FACE_TABLE")
    model9_face_match_threshold: float = Field(default=0.68, alias="MODEL9_FACE_MATCH_THRESHOLD")


settings = Settings()
