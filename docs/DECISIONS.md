# Architectural decision log

## ADR-001 - Select P14 (PROVISIONAL) - 2026-11-10
Context: 26 pieces; student experience in Python/FastAPI, SQL, Docker, LLM, RAG, Qdrant.
Decision: work on P14 pending professor confirmation (Q1). Fallbacks ranked: P24, P17, P11; P05 as course-aligned alternative.
Consequences: if P14 is taken, docs and structure are reused for the fallback where possible.

## ADR-002 - Local, low-cost stack - 2026-11-10
Decision: Python + FastAPI + Qdrant (Docker) + open-source embedding/reranker models + SQLite; no paid APIs by default.
Rationale: reproducibility, zero cost, runs on the student laptop (RTX 5070 8 GB).

## ADR-003 - Case-study corpus - OPEN
Options to evaluate: public regulations/procedures of a public body; open technical manuals; synthetic "company" corpus. Criteria: licence, heterogeneity of formats, metadata richness, ability to write realistic queries.
Also to be fixed here: scope of input types and number of source connectors, query language (drives the embedding model), how "reduce time-to-information" is measured, D2 sanity-check benchmark.

## ADR-004 - BM25 in SQLite FTS5 - 2026-11-10
Context: the sheet requires semantic/keyword indexing; the BM25 index needs a home. The architecture rule is one FastAPI service + Qdrant + SQLite, no microservices. The ACL filter must be applied inside every retriever.
Options:
- (a) SQLite FTS5 - built into Python's sqlite3, persistent, BM25 ranking via `bm25()`, ACL as a SQL WHERE clause on the same database as metadata.
- (b) Qdrant sparse vectors (BM25-style with IDF modifier) - one store for both retrievers, but BM25 behaviour depends on how sparse vectors are computed client-side; harder to explain as a "classic" baseline.
- (c) In-memory `rank_bm25` - simplest code, but not persistent and filters must be applied in Python.
- (d) Elasticsearch/OpenSearch - strong BM25, but an extra heavy service (rejected by the architecture rule).
Decision: (a) SQLite FTS5.
Consequences: no new service; baseline B0 is a standard, well-documented BM25. Limitations to declare: `bm25()` returns lower-is-better scores (sign handled in code); k1/b parameters are fixed in FTS5; the built-in `porter` stemmer is English-only, so Italian text uses `unicode61` without stemming (relevant for ADR-003). Fusion (RRF) uses ranks, so the different score scales of FTS5 and Qdrant do not matter.