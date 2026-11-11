"""Helpers shared by the eval/ scripts (paths, loading, service construction)."""

from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

from qdrant_client import QdrantClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "eval"))

from build_qrels import load_queries  # noqa: E402

from p14_search.config import Settings, get_settings  # noqa: E402
from p14_search.indexing.embedder import SentenceTransformerEmbedder  # noqa: E402
from p14_search.indexing.store import Store  # noqa: E402
from p14_search.indexing.vector_index import VectorIndex  # noqa: E402
from p14_search.retrieval.retrievers import BM25Retriever, DenseRetriever  # noqa: E402
from p14_search.retrieval.service import SearchService  # noqa: E402

RESULTS = ROOT / "eval" / "results"
CALIBRATION = RESULTS / "calibration.json"


def timestamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d-%H%M%S")


def load_qrels() -> dict[str, dict[str, int]]:
    return json.loads((ROOT / "eval" / "qrels" / "d1_qrels.json").read_text(encoding="utf-8"))["qrels"]


def queries(split: str) -> list[dict]:
    return [q for q in load_queries() if q["split"] == split]


def search_service(model: str | None = None, settings: Settings | None = None) -> SearchService:
    """SearchService over the ingested D1 index, with the dense collection of `model`."""
    settings = settings or get_settings().model_copy()
    store = Store(settings.sqlite_path)
    embedder = SentenceTransformerEmbedder(model or settings.embedding_model, settings.embedding_device)
    index = VectorIndex(QdrantClient(url=settings.qdrant_url, timeout=60), settings.qdrant_collection, embedder.name, embedder.dim)
    if not index.client.collection_exists(index.collection):
        raise SystemExit(f"missing collection {index.collection}: run eval/build_dense_index.py --model {embedder.name}")
    return SearchService(store, BM25Retriever(store), DenseRetriever(index, embedder), settings)


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8", newline="\n")
