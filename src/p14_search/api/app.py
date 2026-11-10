"""FastAPI application factory."""

from __future__ import annotations

import logging
import time
import uuid

from fastapi import FastAPI, Request

from p14_search import __version__
from p14_search.config import Settings, get_settings
from p14_search.observability.logging import configure_logging
from p14_search.versions import CHUNKER_VERSION, PIPELINE_VERSION

log = logging.getLogger("p14.api")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)
    app = FastAPI(
        title="P14 Knowledge Search API",
        version=__version__,
        description="Search across organizational knowledge with verifiable citations (AI Puzzle piece P14).",
    )
    app.state.settings = settings

    @app.middleware("http")
    async def request_log(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        request.state.request_id = request_id
        start = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        log.info(
            "request",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "latency_ms": round((time.perf_counter() - start) * 1000, 1),
            },
        )
        return response

    @app.get("/v1/health", tags=["meta"])
    def health() -> dict:
        return {"status": "ok"}

    @app.get("/v1/version", tags=["meta"])
    def version() -> dict:
        return {
            "pipeline_version": PIPELINE_VERSION,
            "chunker_version": CHUNKER_VERSION,
            "embedding_model": settings.embedding_model,
            "reranker_model": settings.reranker_model,
        }

    return app
