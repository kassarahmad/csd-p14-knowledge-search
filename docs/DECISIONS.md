# Architectural decision log

## ADR-001 - Select P14 (PROVISIONAL) - 2026-11-10
Context: 26 pieces; student experience in Python/FastAPI, SQL, Docker, LLM, RAG, Qdrant.
Decision: work on P14 pending professor confirmation (Q1). Fallbacks ranked: P24, P17, P11; P05 as course-aligned alternative.
Consequences: if P14 is taken, docs and structure are reused for the fallback where possible.

## ADR-002 - Local, low-cost stack - 2026-11-10
Decision: Python + FastAPI + Qdrant (Docker) + open-source embedding/reranker models + SQLite; no paid APIs by default.
Rationale: reproducibility, zero cost, runs on the student laptop (RTX 5070 8 GB).

## ADR-003 - Case-study corpus - DECIDED 2026-11-10
Options considered: (A) documents of a real Italian public body; (B) open English technical documentation; (C) fully synthetic company corpus.
Decision (student's choice, from MASTER_PROMPT Phase 3): fictional public organization "Ente Demo" =
- D1a: 32 REAL Italian official acts (Normattiva HTML/TXT, Gazzetta Ufficiale PDF), public, art. 5 L. 633/1941;
- D1b: 25 SYNTHETIC LLM-generated internal documents (PDF/DOCX/TXT) with public/internal/restricted access levels and offices;
- D2: BEIR SciFact as sanity benchmark (CC BY 4.0 / ODC-By 1.0).
Query language: Italian, plus about 10% English queries (cross-lingual) -> multilingual embedding model, chosen by benchmark on the tuning set (ADR-005).
Scope of input types: documents (HTML, TXT, PDF, DOCX) from two source connectors (`d1a` public legislation, `d1b` internal repository). Website/intranet, shared mailboxes are out of scope (privacy, no real organization); internal FAQs are covered by synthetic FAQ documents.
"Reduce time-to-information": measured only through proxies (latency, rank of the first relevant passage, MRR); no user study - declared as a limitation.
Rationale: real legal text gives realistic vocabulary mismatch and size; synthetic layer gives real ACL, heterogeneous formats and internal knowledge; mixes the strengths of A and C. Why not B: weak organizational character, no access levels.
Consequences: FTS5 has no Italian stemmer (B0 handicap, declared in ADR-004); synthetic data and LLM-drafted qrels must be reviewed by the student; EUR-Lex PDFs were excluded because the site blocks automated download (HTTP 202 challenge).

## ADR-004 - BM25 in SQLite FTS5 - 2026-11-10
Context: the sheet requires semantic/keyword indexing; the BM25 index needs a home. The architecture rule is one FastAPI service + Qdrant + SQLite, no microservices. The ACL filter must be applied inside every retriever.
Options:
- (a) SQLite FTS5 - built into Python's sqlite3, persistent, BM25 ranking via `bm25()`, ACL as a SQL WHERE clause on the same database as metadata.
- (b) Qdrant sparse vectors (BM25-style with IDF modifier) - one store for both retrievers, but BM25 behaviour depends on how sparse vectors are computed client-side; harder to explain as a "classic" baseline.
- (c) In-memory `rank_bm25` - simplest code, but not persistent and filters must be applied in Python.
- (d) Elasticsearch/OpenSearch - strong BM25, but an extra heavy service (rejected by the architecture rule).
Decision: (a) SQLite FTS5.
Consequences: no new service; baseline B0 is a standard, well-documented BM25. Limitations to declare: `bm25()` returns lower-is-better scores (sign handled in code); k1/b parameters are fixed in FTS5; the built-in `porter` stemmer is English-only, so Italian text uses `unicode61` without stemming (relevant for ADR-003). Fusion (RRF) uses ranks, so the different score scales of FTS5 and Qdrant do not matter.