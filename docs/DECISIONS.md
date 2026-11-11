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
Decision (student's choice): fictional public organization "Ente Demo" =
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

## ADR-005 - Embedding model: intfloat/multilingual-e5-small - 2026-11-10
Context: Italian corpus, ~10% English queries, 8 GB GPU -> small multilingual model. Two candidates, both 384-dimensional:
intfloat/multilingual-e5-small (MIT licence, needs "query:"/"passage:" prefixes) and ibm-granite/granite-embedding-107m-multilingual (Apache-2.0).
Method: `eval/build_dense_index.py` embeds the same 10,689 passages with each model (one Qdrant collection per model);
`eval/compare_models.py` runs S1 (dense) and S2 (hybrid) on the TUNING split only (40 queries, 34 in scope); the
held-out test split was frozen before this step. Rule fixed in advance: highest S2 nDCG@10, tie -> smaller dimension.
Result (eval/results/model_comparison.json): S2 nDCG@10 0.7324 (e5-small) vs 0.6928 (Granite); S2 Recall@10 0.9167 vs 0.7794;
S1 nDCG@10 0.6450 vs 0.6036.
Decision: intfloat/multilingual-e5-small (EMBEDDING_MODEL default).
Consequences: only 40 tuning queries - the difference is indicative, not statistically tested; Granite stays available
(its collection can be rebuilt with one command) for future comparison.

## ADR-006 - PDF text extraction: pdfium first, pypdf fallback - 2026-11-10
Context: real Gazzetta Ufficiale PDFs use heterogeneous fonts. pypdf alone produced glyph names ("/C76") on a 2004 issue and substitution-like garbage ("Eresidente") on a 2005 issue.
Decision: pypdfium2 (pdfium, Chrome's PDF engine) as primary extractor; per page, if the text looks garbled (control characters or very few function words), pypdf with glyph-name repair is tried and kept only if clearly better.
Consequences: robust and fast extraction on 6 of 7 GU PDFs; the 2004 issue remains low quality (merged words). pdfium is native code: accepted because it is heavily fuzzed; documented in the parser's safety notes. About 1.4% of D1a passages are still non-prose (tables, lists, some shifted-font pages) - see DATA.md.

## ADR-007 - Human approval gate before indexing - 2026-11-10
Context: human oversight is a cross-cutting requirement; documents carry access levels that must be right before anyone can find them.
Decision: POST /v1/documents only parses and chunks (status pending); only POST /v1/documents/{id}/approve by an officer of that office (or admin) writes to FTS5 and Qdrant. A new version stays pending while the previous approved version remains searchable.
Consequences: wrong access levels cannot leak before review; approval is logged (approval_log). In this prototype approvals of the corpus are SIMULATED by scripts/ingest_corpus.py and logged as such.

## ADR-008 - Evaluation design: LLM-drafted queries, snippet-anchored graded qrels - 2026-11-10
Context: no real users or annotators are available; judgments must survive re-chunking.
Decision: an LLM drafts queries and, for each, the target document/section plus a VERBATIM answer snippet; eval/build_qrels.py derives passage-level grades (2 = contains the snippet, 1 = same section) on the current index. Test split frozen by hash before any tuning. Everything labelled llm_generated and listed for student review.
Consequences: reproducible, chunker-independent qrels; known biases (single LLM annotator, incomplete judgments) declared in ANNOTATION_PROTOCOL.md and visible in the error analysis (category C).

## ADR-009 - Qdrant addressed as 127.0.0.1 - 2026-11-10
Context: on Windows "localhost" resolved to ::1 and the Docker Desktop port forward hung connections from Python (the first ingestion run blocked).
Decision: default QDRANT_URL=http://127.0.0.1:6333.

