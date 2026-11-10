"""Runtime settings, read from environment variables and the .env file."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    qdrant_url: str = "http://127.0.0.1:6333"
    qdrant_collection: str = "p14_passages"
    embedding_model: str = "intfloat/multilingual-e5-small"
    embedding_device: str = "cuda"
    reranker_model: str | None = None
    sqlite_path: Path = Path("data/processed/p14.sqlite")
    principals_path: Path = Path("config/principals.json")
    max_upload_mb: int = 20
    log_level: str = "INFO"
    # Shadow mode: the display system is shown to the user; the shadow system runs on the same query and is
    # only logged (shadow_log). Validation protocol of EVALUATION.md: display B0, shadow S2.
    display_system: str = "S2"
    shadow_system: str | None = "B0"
    # insufficient_evidence thresholds (top dense cosine for S1/S2, top BM25 score for B0).
    # 0 = never flag; calibrated on the tuning set by eval/calibrate_threshold.py.
    ie_min_dense: float = 0.0
    ie_min_bm25: float = 0.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
