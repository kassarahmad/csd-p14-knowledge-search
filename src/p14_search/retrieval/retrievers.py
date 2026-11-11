"""Retrievers (B0 BM25, S1 dense) and RRF fusion (S2). The ACL filter is applied inside each retriever."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from p14_search.indexing.embedder import Embedder
from p14_search.indexing.store import Store
from p14_search.indexing.vector_index import VectorIndex
from p14_search.models import SearchFilters
from p14_search.security import acl
from p14_search.security.principals import Principal

RRF_K = 60
CANDIDATES = 50  # per-retriever depth used for fusion

# Function words dropped from BM25 queries (Italian + English). FTS5 has no Italian stemmer (ADR-004).
STOPWORDS = set(
    """il lo la i gli le un uno una di a da in con su per tra fra e ed o od ma se che chi cui non ne ci si
    del dello della dei degli delle al allo alla ai agli alle dal dallo dalla dai dagli dalle nel nello nella
    nei negli nelle sul sullo sulla sui sugli sulle col coi è sono ha hanno come quale quali quando dove
    cosa devo posso può puo mio mia miei mie suo sua loro questo questa questi queste quello quella
    the a an of to in on for and or is are be can do does how what when where which who with my i""".split()
)


@dataclass
class Hit:
    passage_id: str
    score: float
    rank: int
    retriever_ranks: dict[str, int | None] = field(default_factory=dict)
    retriever_scores: dict[str, float | None] = field(default_factory=dict)


def fts_query(text: str) -> str | None:
    tokens = [t for t in re.findall(r"\w+", text.lower()) if t not in STOPWORDS and len(t) > 1]
    if not tokens:
        return None
    return " OR ".join(f'"{t}"' for t in dict.fromkeys(tokens))


class BM25Retriever:
    name = "bm25"

    def __init__(self, store: Store):
        self.store = store

    def retrieve(self, query: str, principal: Principal, k: int, filters: SearchFilters | None = None) -> list[Hit]:
        match = fts_query(query)
        if match is None:
            return []
        where, params = acl.sql_clause(principal, filters, "d")
        rows = self.store.query(
            f"""SELECT p.passage_id, bm25(passages_fts) AS s
                FROM passages_fts
                JOIN passages p ON p.rowid = passages_fts.rowid
                JOIN documents d ON d.document_id = p.document_id
                WHERE passages_fts MATCH ? AND p.indexed = 1 AND {where}
                ORDER BY s LIMIT ?""",
            [match, *params, k],
        )
        # FTS5 bm25() is lower-is-better: negate so that higher = better everywhere.
        return [Hit(r["passage_id"], -r["s"], i + 1, {"bm25": i + 1}, {"bm25": -r["s"]}) for i, r in enumerate(rows)]


class DenseRetriever:
    name = "dense"

    def __init__(self, index: VectorIndex, embedder: Embedder):
        self.index = index
        self.embedder = embedder

    def retrieve(self, query: str, principal: Principal, k: int, filters: SearchFilters | None = None) -> list[Hit]:
        vector = self.embedder.embed_queries([query])[0]
        hits = self.index.search(vector, acl.qdrant_filter(principal, filters), k)
        return [Hit(pid, s, i + 1, {"dense": i + 1}, {"dense": s}) for i, (pid, s) in enumerate(hits)]


def rrf_fuse(runs: dict[str, list[Hit]], k: int, rrf_k: int = RRF_K) -> list[Hit]:
    """Reciprocal Rank Fusion: score = sum over retrievers of 1 / (rrf_k + rank). Uses ranks only, so the
    different score scales of BM25 and cosine similarity do not matter."""
    fused: dict[str, Hit] = {}
    for name, hits in runs.items():
        for h in hits:
            f = fused.setdefault(h.passage_id, Hit(h.passage_id, 0.0, 0, {n: None for n in runs}, {n: None for n in runs}))
            f.score += 1.0 / (rrf_k + h.rank)
            f.retriever_ranks[name] = h.rank
            f.retriever_scores[name] = h.score
    ranked = sorted(fused.values(), key=lambda h: (-h.score, h.passage_id))[:k]
    for i, h in enumerate(ranked):
        h.rank = i + 1
    return ranked
