# P14 - Intelligent Search Across Organizational Knowledge

Complex Systems Design - UNICAM - AI Puzzle framework v5.0 (piece P14, provisional).

Semantic + keyword search over authorised organizational documents, returning ranked documents,
the passages that answer the query, precise source references and metadata, with an optional summary
built only from retrieved content.

## Status
Design phase. See `docs/PROGRESS.md`.

## Planned stack (see docs/DECISIONS.md)
Python 3.11 - FastAPI - Pydantic - Qdrant (Docker) - sentence-transformers - BM25 baseline - optional cross-encoder reranker - SQLite - pytest - Docker Compose - Streamlit demo UI.

## Setup (Windows 11, PowerShell)
Requirements: Docker Desktop, an NVIDIA GPU is optional (CPU works, slower).
```powershell
python -m pip install --user uv              # package/venv manager
python -m uv python install 3.11
python -m uv venv --python 3.11 .venv
python -m uv pip install --python .venv\Scripts\python.exe -e ".[dev,data,ui]"   # torch from the CUDA 12.8 index (pyproject [tool.uv])
copy .env.example .env
docker compose up -d                         # Qdrant v1.19.2 on :6333
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m uvicorn p14_search.main:app --port 8000
```
Without uv: create a 3.11 venv, then `pip install torch --index-url https://download.pytorch.org/whl/cu128` and `pip install -e ".[dev,data,ui]"`.

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