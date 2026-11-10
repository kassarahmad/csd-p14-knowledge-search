# Project proposal - P14 (DRAFT)

Follows the shared 7-section template of the AI Puzzle framework (see COURSE_REQUIREMENTS.md).

## 1. Project
A local, reproducible search service that retrieves organizational knowledge by meaning (dense embeddings) and by keyword (BM25), fuses and optionally reranks results, and returns documents, passages and verifiable citations through a documented REST API. Access levels are enforced inside retrieval. The service never acts on its own: it returns evidence, and a person decides what to do with it.

## 2. Input data sources
- Case-study corpus (ADR-003, docs/DATA.md): fictional public organization "Ente Demo" = 32 real Italian official acts (D1a, public) + 25 synthetic, LLM-generated internal documents (D1b, public/internal/restricted). Formats: HTML, TXT, PDF, DOCX. Two source connectors (d1a, d1b).
- Out of scope: website/intranet crawling and shared mailboxes (no real organization, privacy); internal FAQs are covered by synthetic FAQ documents.
- Metadata per document: author/owner, date, office, type, project, access level.
- User queries: free text in Italian, about 10% in English (cross-lingual).

## 3. Objectives
Reduce time-to-information; tolerate vocabulary mismatch; link related sources; make provenance always verifiable; respect access levels.
"Reduce time-to-information" is measured only through proxies (latency, MRR, rank of the first relevant passage); no user study (declared limitation).

## 4. Expected output
Machine-readable JSON (contracts/schemas) with: ranked documents, passages with persistent ids, scores and ranks as `evidence` (not calibrated probabilities), citation (document id, document version, title, page/section, char offsets), metadata, version block (pipeline, chunker, embedding model, reranker, index snapshot), an explicit `insufficient_evidence` flag, and an optional **extractive** summary in which every sentence carries the `passage_id` it was taken from.

## 5. Required components
Ingestion with owner approval of access level + safe parsing - chunking - embedding - Qdrant (dense) + SQLite FTS5 (BM25, ADR-004) - hybrid fusion (RRF) - optional cross-encoder reranker - permission filter applied inside both retrievers - citation builder - API - query log, feedback and versioning - shadow runner - evaluation harness - demo UI.

Human oversight (where a person intervenes):
1. The content owner/admin approves each document's ingestion and its `access_level`; nothing becomes searchable without this explicit assignment.
2. The user always sees the citations and decides whether to trust a result; P14 takes no action.
3. When evidence is weak the service returns `insufficient_evidence: true` instead of guessing.
4. Any summary is marked `generated` and linked to the `passage_id`s it uses.
5. User feedback (useful / not useful / wrong source) is stored; it is the "operator's final decision" required by the traceability criterion and feeds error analysis.

## 6. Connections
- Provides: P24 External assistant, P12 Generation (primary, implemented as mock consumers); P15, P25 (documented).
- Receives: P11 (structured documents), P15 (meeting records), P25 (validated knowledge cards), all through the `IngestDocument` format.
- Mechanism: REST/OpenAPI (primary); CloudEvents `p14.document.indexed` (optional); MCP tool wrapper (stretch goal).
- Details per connection: docs/INTEGRATION.md.

## 7. Success criteria (OUR proposed targets, not official)
Operational definitions, targets and the shadow-mode validation protocol are in docs/EVALUATION.md. They are fixed before the held-out test set is run.

## 8. Scope: MVP vs stretch goals
| Item | MVP | Stretch |
|---|---|---|
| Ingestion (owner-approved, safe parsing, chunking) | x | |
| BM25 (FTS5) + dense (Qdrant) + RRF fusion | x | |
| Cross-encoder reranker (S3) | | x |
| ACL filter inside retrieval + leakage test | x | |
| Persistent ids (document_id, document_version, passage_id) | x | |
| Version block in every response, query_log, feedback | x | |
| `insufficient_evidence` flag (threshold calibrated on tuning set) | x | |
| Extractive summary with passage ids | x | |
| Shadow runner + offline comparison | x | |
| Evaluation harness (B0, S1, S2) + randomization test | x | |
| JSON Schemas + OpenAPI + conformance test, examples (deliverable 6) | x | |
| Mock consumers P24 and P12 | x | |
| Streamlit demo UI | x | |
| Tombstones (410 Gone) for deleted documents, /v2 deprecation policy | documented only | implemented |
| CloudEvents `p14.document.indexed` | | x |
| `GET /v1/documents/{id}/related` ("connect related sources") | | x |
| Local LLM summary (e.g. via Ollama), marked `generated` | | x |
| MCP tool wrapper | | x |
