"""Runtime settings, read from environment variables and the .env file."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "p14_passages"
    embedding_model: str = "intfloat/multilingual-e5-small"
    embedding_device: str = "cuda"
    reranker_model: str | None = None
    sqlite_path: Path = Path("data/processed/p14.sqlite")
    principals_path: Path = Path("config/principals.json")
    max_upload_mb: int = 20
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
