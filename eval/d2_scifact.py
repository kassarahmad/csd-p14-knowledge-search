"""D2 sanity benchmark: BEIR SciFact (English, independent qrels). Not the case study.

Builds a SEPARATE index (data/processed/d2_scifact.sqlite + Qdrant collection d2_scifact__<model>) with the same
pipeline (parser, chunker, FTS5, dense), then evaluates B0/S1/S2 on the 300 test queries at DOCUMENT level
(BEIR convention: passages are mapped to their abstract, first occurrence wins).

Usage:
    python eval/d2_scifact.py   (also called by eval/run_eval.py)
"""

from __future__ import annotations

import base64
import csv
import json
import sys
import time

from common import RESULTS, ROOT, timestamp, write_json
from qdrant_client import QdrantClient

from p14_search.config import Settings, get_settings
from p14_search.evaluation.metrics import mrr_at, ndcg_at, recall_at
from p14_search.evaluation.runner import mean
from p14_search.indexing.embedder import SentenceTransformerEmbedder
from p14_search.indexing.store import Store
from p14_search.indexing.vector_index import VectorIndex
from p14_search.ingestion.service import IngestionService
from p14_search.models import AccessLevel, IngestDocument
from p14_search.retrieval.retrievers import BM25Retriever, DenseRetriever
from p14_search.retrieval.service import SearchService
from p14_search.security.principals import Principal

D2 = ROOT / "data" / "raw" / "d2" / "scifact"
ADMIN = Principal("d2-admin", "admin", AccessLevel.restricted, ("*",))


def build(settings: Settings) -> SearchService:
    store = Store(ROOT / "data" / "processed" / "d2_scifact.sqlite")
    embedder = SentenceTransformerEmbedder(settings.embedding_model, settings.embedding_device)
    index = VectorIndex(QdrantClient(url=settings.qdrant_url, timeout=60), "d2_scifact", embedder.name, embedder.dim)
    index.ensure_collection()
    ingestion = IngestionService(store, index, embedder, 5 * 1024 * 1024)
    done = store.query("SELECT COUNT(*) AS n FROM documents WHERE status = 'approved'")[0]["n"]
    docs = [json.loads(line) for line in (D2 / "corpus.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    if done < len(docs):
        t0 = time.perf_counter()
        for d in docs:
            text = (d.get("title", "") + "\n\n" + d["text"]).encode("utf-8")
            doc = IngestDocument(
                source_id="d2", external_id=f"scifact-{d['_id']}", title=d.get("title") or d["_id"],
                file={"filename": f"{d['_id']}.txt", "media_type": "text/plain", "content_base64": base64.b64encode(text).decode()},
                metadata={"office": "research", "type": "abstract"}, access_level=AccessLevel.public, owner="BEIR SciFact",
            )
            res = ingestion.ingest(doc, ADMIN)
            if res.status != "approved":
                ingestion.approve(res.document_id, ADMIN, "D2 benchmark load", refresh_snapshot=False)
        store.refresh_snapshot_id()
        print(f"D2 indexed {len(docs)} abstracts in {time.perf_counter() - t0:.0f}s")
    return SearchService(store, BM25Retriever(store), DenseRetriever(index, embedder), settings)


def evaluate(settings: Settings | None = None) -> dict:
    settings = (settings or get_settings()).model_copy(update={"ie_min_dense": 0.0, "ie_min_bm25": 0.0})
    search = build(settings)
    queries = {q["_id"]: q["text"] for q in map(json.loads, (D2 / "queries.jsonl").read_text(encoding="utf-8").splitlines())}
    qrels: dict[str, dict[str, int]] = {}
    with open(D2 / "qrels" / "test.tsv", encoding="utf-8") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            qrels.setdefault(row["query-id"], {})[f"d2:scifact-{row['corpus-id']}"] = 2 if int(row["score"]) > 0 else 0
    doc_of = {r["passage_id"]: r["document_id"] for r in search.store.query("SELECT passage_id, document_id FROM passages")}
    per_system = {}
    t0 = time.perf_counter()
    for system in ("B0", "S1", "S2"):
        rows = []
        for qid, grades in qrels.items():
            hits = search.rank_all(queries[qid], ADMIN, 50, (system,))[system].hits
            ranked_docs = list(dict.fromkeys(doc_of[h.passage_id] for h in hits))
            rows.append({"ndcg@10": ndcg_at(ranked_docs, grades, 10), "recall@10": recall_at(ranked_docs, grades, 10),
                         "mrr@10": mrr_at(ranked_docs, grades, 10)})
        per_system[system] = {m: mean(r[m] for r in rows) for m in ("ndcg@10", "recall@10", "mrr@10")} | {"n_queries": len(rows)}
    return {
        "dataset": "BEIR SciFact test (claims CC BY 4.0, abstracts ODC-By 1.0)",
        "level": "document",
        "embedding_model": search.dense.embedder.name,
        "overall": per_system,
        "seconds": round(time.perf_counter() - t0, 1),
    }


def main() -> int:
    report = evaluate()
    write_json(RESULTS / f"d2_scifact_{timestamp()}.json", report)
    print(json.dumps(report, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
