"""Search: ranking (B0/S1/S2), evidence, citations, insufficient-evidence flag, extractive summary,
query log and shadow mode."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from p14_search.config import Settings
from p14_search.indexing.store import Store, dumps
from p14_search.models import (
    Citation,
    DocumentMetadata,
    Evidence,
    Passage,
    ResultDocument,
    SearchFilters,
    SearchRequest,
    SearchResponse,
    Versions,
)
from p14_search.retrieval.retrievers import CANDIDATES, BM25Retriever, DenseRetriever, Hit, rrf_fuse
from p14_search.retrieval.summary import extractive_summary
from p14_search.security import acl
from p14_search.security.principals import Principal
from p14_search.versions import CHUNKER_VERSION, PIPELINE_VERSION

log = logging.getLogger("p14.search")
SYSTEMS = ("B0", "S1", "S2")


@dataclass
class Ranking:
    system: str
    hits: list[Hit]
    insufficient_evidence: bool
    top_bm25: float | None
    top_dense: float | None


class SearchService:
    def __init__(self, store: Store, bm25: BM25Retriever, dense: DenseRetriever, settings: Settings):
        self.store = store
        self.bm25 = bm25
        self.dense = dense
        self.settings = settings

    # --- ranking -----------------------------------------------------------------------------
    def rank_all(
        self, query: str, principal: Principal, k: int, systems: tuple[str, ...], filters: SearchFilters | None = None
    ) -> dict[str, Ranking]:
        """Rank with several systems sharing the same retriever runs (shadow mode costs no extra retrieval)."""
        need_bm25 = any(s in ("B0", "S2") for s in systems)
        need_dense = any(s in ("S1", "S2") for s in systems)
        bm25_run = self.bm25.retrieve(query, principal, max(k, CANDIDATES), filters) if need_bm25 else []
        dense_run = self.dense.retrieve(query, principal, max(k, CANDIDATES), filters) if need_dense else []
        top_bm25 = bm25_run[0].score if bm25_run else None
        top_dense = dense_run[0].score if dense_run else None
        out = {}
        for system in systems:
            if system == "B0":
                hits = bm25_run[:k]
            elif system == "S1":
                hits = dense_run[:k]
            elif system == "S2":
                hits = rrf_fuse({"bm25": bm25_run, "dense": dense_run}, k)
            else:
                raise ValueError(f"unknown system {system}")
            out[system] = Ranking(system, hits, self._insufficient(system, hits, top_bm25, top_dense), top_bm25, top_dense)
        return out

    def _insufficient(self, system: str, hits: list[Hit], top_bm25: float | None, top_dense: float | None) -> bool:
        """Thresholds come from configuration and are calibrated on the tuning set only (eval/calibrate)."""
        if not hits:
            return True
        if system == "B0":
            return (top_bm25 or 0.0) < self.settings.ie_min_bm25
        return (top_dense or 0.0) < self.settings.ie_min_dense

    # --- full search -------------------------------------------------------------------------
    def search(self, req: SearchRequest, principal: Principal, request_id: str) -> SearchResponse:
        start = time.perf_counter()
        shown = self.settings.display_system
        shadow = self.settings.shadow_system if self.settings.shadow_system not in (None, "", shown) else None
        rankings = self.rank_all(req.query, principal, req.top_k, (shown,) + ((shadow,) if shadow else ()), req.filters)
        ranking = rankings[shown]
        results = self.hydrate(ranking.hits, principal)
        summary = None
        if req.with_summary and not ranking.insufficient_evidence:
            ordered = sorted((p for d in results for p in d.passages), key=lambda p: p.evidence.rank)
            summary = extractive_summary(req.query, [(p.passage_id, p.text) for p in ordered])
        response = SearchResponse(
            request_id=request_id,
            query=req.query,
            system=shown,
            results=results,
            insufficient_evidence=ranking.insufficient_evidence,
            summary=summary,
            versions=self.versions(),
        )
        latency_ms = (time.perf_counter() - start) * 1000
        self.store.log_query(
            request_id=request_id,
            principal_hash=principal.pseudonym,
            query=req.query,
            filters_json=dumps(req.filters.model_dump() if req.filters else None),
            system=shown,
            versions_json=dumps(response.versions.model_dump()),
            results_json=dumps([[h.passage_id, h.rank, round(h.score, 6)] for h in ranking.hits]),
            insufficient_evidence=int(ranking.insufficient_evidence),
            latency_ms=round(latency_ms, 2),
        )
        if shadow:
            a = [h.passage_id for h in ranking.hits]
            b = [h.passage_id for h in rankings[shadow].hits]
            self.store.log_shadow(
                request_id=request_id,
                shown_system=shown,
                shadow_system=shadow,
                shown_json=dumps(a),
                shadow_json=dumps(b),
                overlap_at_k=len(set(a) & set(b)) / max(req.top_k, 1),
            )
        log.info("search", extra={"request_id": request_id, "system": shown, "results": len(ranking.hits), "latency_ms": round(latency_ms, 1)})
        return response

    def versions(self) -> Versions:
        return Versions(
            pipeline_version=PIPELINE_VERSION,
            chunker_version=CHUNKER_VERSION,
            embedding_model=self.dense.embedder.name,
            reranker_model=self.settings.reranker_model,
            index_snapshot_id=self.store.get_meta("index_snapshot_id"),
        )

    # --- hydration ---------------------------------------------------------------------------
    def hydrate(self, hits: list[Hit], principal: Principal) -> list[ResultDocument]:
        """Load passage/document data and group by document. The ACL is re-checked here (defence in depth):
        a hit that is not searchable or not allowed is dropped, never returned."""
        if not hits:
            return []
        ids = [h.passage_id for h in hits]
        rows = self.store.query(
            f"""SELECT p.*, d.title, d.office, d.type, d.author, d.date, d.project, d.source_url, d.access_level,
                       d.owner, d.synthetic, d.llm_generated
                FROM passages p JOIN documents d ON d.document_id = p.document_id
                WHERE p.passage_id IN ({','.join('?' * len(ids))}) AND p.indexed = 1""",
            ids,
        )
        by_id = {r["passage_id"]: r for r in rows}
        docs: dict[str, ResultDocument] = {}
        for h in hits:
            r = by_id.get(h.passage_id)
            if r is None or not acl.allows(principal, r["access_level"], r["office"]):
                continue
            passage = Passage(
                passage_id=r["passage_id"],
                text=r["text"],
                citation=Citation(
                    document_id=r["document_id"],
                    document_version=r["document_version"],
                    title=r["title"],
                    section=r["section"],
                    page=r["page"],
                    char_start=r["char_start"],
                    char_end=r["char_end"],
                    source_url=r["source_url"],
                ),
                evidence=Evidence(score=round(h.score, 6), rank=h.rank, retriever_ranks=h.retriever_ranks, retriever_scores=h.retriever_scores),
            )
            doc = docs.get(r["document_id"])
            if doc is None:
                doc = docs[r["document_id"]] = ResultDocument(
                    document_id=r["document_id"],
                    document_version=r["document_version"],
                    title=r["title"],
                    access_level=r["access_level"],
                    metadata=DocumentMetadata(
                        office=r["office"], type=r["type"], author=r["author"], date=r["date"], project=r["project"], source_url=r["source_url"]
                    ),
                    owner=r["owner"],
                    synthetic=bool(r["synthetic"]),
                    llm_generated=bool(r["llm_generated"]),
                    best_rank=h.rank,
                    passages=[],
                )
            doc.passages.append(passage)
        return sorted(docs.values(), key=lambda d: d.best_rank)
