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


settings = Settings()

