# P14 - Intelligent Search Across Organizational Knowledge

Complex Systems Design - UNICAM - AI Puzzle framework v5.0 (piece P14, provisional).

Semantic + keyword search over authorised organizational documents, returning ranked documents,
the passages that answer the query, precise source references and metadata, with an optional summary
built only from retrieved content.

## Status
Design phase. See `docs/PROGRESS.md`.

## Planned stack (see docs/DECISIONS.md)
Python 3.11 - FastAPI - Pydantic - Qdrant (Docker) - sentence-transformers - BM25 baseline - optional cross-encoder reranker - SQLite - pytest - Docker Compose - Streamlit demo UI.

## Setup
To be written once the MVP exists (Phase 3).

## Documentation
| File | Content |
|---|---|
| docs/COURSE_REQUIREMENTS.md | Requirements verified in the course document |
| docs/PROJECT_PROPOSAL.md | Problem, scope, inputs/outputs, success criteria |
| docs/ARCHITECTURE.md | Architecture and diagrams |
| docs/INTEGRATION.md | API contract and puzzle connections |
| docs/DATA.md | Data sources, schema, licence, privacy |
| docs/EVALUATION.md | Methodology and (real) results |
| docs/SECURITY_OVERSIGHT.md | Security, traceability, human oversight |
| docs/ROADMAP.md | Internal plan |
| docs/DECISIONS.md | Architectural decision log |
| docs/PROGRESS.md | Current state |
| docs/OPEN_QUESTIONS.md | Items awaiting confirmation |