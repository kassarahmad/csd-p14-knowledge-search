"""Embed every searchable passage with a given model into that model's own Qdrant collection.
Used to compare embedding models (ADR-005) on the same passages; the API uses EMBEDDING_MODEL.

Usage:
    python eval/build_dense_index.py --model ibm-granite/granite-embedding-107m-multilingual
"""

from __future__ import annotations

import argparse
import sys
import time

from qdrant_client import QdrantClient

from p14_search.config import get_settings
from p14_search.indexing.embedder import SentenceTransformerEmbedder
from p14_search.indexing.store import Store
from p14_search.indexing.vector_index import VectorIndex
from p14_search.ingestion.service import embedding_text


def build(model: str, rebuild: bool = False) -> VectorIndex:
    settings = get_settings()
    store = Store(settings.sqlite_path)
    embedder = SentenceTransformerEmbedder(model, settings.embedding_device)
    index = VectorIndex(QdrantClient(url=settings.qdrant_url, timeout=60), settings.qdrant_collection, embedder.name, embedder.dim)
    rows = store.query(
        """SELECT p.passage_id, p.text, p.section, d.title, d.document_id, d.access_level, d.office, d.type, d.source_id
           FROM passages p JOIN documents d ON d.document_id = p.document_id WHERE p.indexed = 1 ORDER BY p.rowid"""
    )
    if rebuild and index.client.collection_exists(index.collection):
        index.client.delete_collection(index.collection)
    index.ensure_collection()
    if index.count() == len(rows) and not rebuild:
        print(f"{index.collection}: already has {len(rows)} points, nothing to do")
        return index
    t0 = time.perf_counter()
    vectors = embedder.embed_passages([embedding_text(r["title"], r["section"], r["text"]) for r in rows])
    t1 = time.perf_counter()
    payloads = [{k: r[k] for k in ("passage_id", "document_id", "access_level", "office", "type", "source_id")} for r in rows]
    index.upsert(payloads, vectors)
    print(f"{index.collection}: {len(rows)} passages embedded in {t1 - t0:.1f}s, upserted in {time.perf_counter() - t1:.1f}s")
    return index


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()
    build(args.model, args.rebuild)
    return 0


if __name__ == "__main__":
    sys.exit(main())
