# P14 - Intelligent Search Across Organizational Knowledge

Complex Systems Design - UNICAM - AI Puzzle framework v5.0, piece P14 (assignment provisional, see docs/OPEN_QUESTIONS.md Q1).

A local search service for a fictional public organization, **Ente Demo**. It finds information by meaning (dense
embeddings) and by keyword (BM25), fuses the two rankings (RRF) and always returns the precise source of every passage:
document, version, section/page and character offsets. Access levels are enforced inside retrieval. When the evidence
is weak it says so (`insufficient_evidence`) instead of guessing. Any summary is extractive: sentences copied from
the sources, each with its `passage_id`.

The corpus combines **32 real Italian official acts** (Normattiva, Gazzetta Ufficiale) with **25 synthetic, LLM-generated
internal documents** (labelled as such everywhere). Details: docs/DATA.md.

## Stack
Python 3.11 - FastAPI - Pydantic - SQLite FTS5 (BM25) - Qdrant 1.19.2 (Docker) - sentence-transformers
(`intfloat/multilingual-e5-small`, ADR-005) - pypdfium2/pypdf, python-docx, BeautifulSoup - pytest - Streamlit.
No paid services, no cloud: everything runs locally (tested on Windows 11, RTX 5070 Laptop GPU 8 GB, 31.1 GB RAM as measured by the evaluation script).

## Setup (Windows 11, from the repository root)
```powershell
python -m pip install --user uv
python -m uv python install 3.11
python -m uv venv --python 3.11 .venv
python -m uv pip install --python .venv\Scripts\python.exe -e ".[dev,data,ui]"   # torch from the CUDA 12.8 index (pyproject [tool.uv])
copy .env.example .env                                    # demo API keys + calibrated thresholds
docker compose up -d                                      # Qdrant v1.19.2 on 127.0.0.1:6333
.venv\Scripts\python.exe -m pytest                        # unit, API, ACL-leakage and contract tests (no Docker/model needed)
```
Without uv: create a Python 3.11 venv, `pip install torch --index-url https://download.pytorch.org/whl/cu128`, then `pip install -e ".[dev,data,ui]"`.
Without an NVIDIA GPU set `EMBEDDING_DEVICE=cpu` in `.env` (slower).

## Build the corpus and the index
```powershell
.venv\Scripts\python.exe scripts\fetch_corpus.py      # D1a real acts + D2 SciFact (downloads, ~35 MB)
.venv\Scripts\python.exe scripts\generate_d1b.py      # D1b synthetic documents (PDF/DOCX/TXT)
.venv\Scripts\python.exe scripts\ingest_corpus.py     # ingest + SIMULATED owner approval -> SQLite + Qdrant
.venv\Scripts\python.exe scripts\corpus_stats.py      # eval/results/corpus_stats.json
```

## Run
```powershell
.venv\Scripts\python.exe -m uvicorn p14_search.main:app --port 8000     # API, docs at http://127.0.0.1:8000/docs
.venv\Scripts\streamlit.exe run frontend\app.py                          # demo UI (choose the principal to see the ACL)
.venv\Scripts\python.exe mocks\p24_external_assistant\p24_client.py "Quanto costano le copie per l'accesso agli atti?"
.venv\Scripts\python.exe mocks\p12_document_generation\p12_client.py "lavoro agile disconnessione"
```
Example request:
```powershell
curl.exe -s -X POST http://127.0.0.1:8000/v1/search -H "X-API-Key: demo-employee" -H "Content-Type: application/json" -d "{\"query\": \"Quanti giorni al mese posso lavorare da casa?\"}"
```

## Evaluate
Full sequence, commands and runtimes: docs/REPRODUCIBILITY.md. Results: docs/EVALUATION.md (every number comes from a file in eval/results/).

## Documentation
| File | Content |
|---|---|
| docs/REPORT.md | Technical report (start here) |
| docs/COURSE_REQUIREMENTS.md | Requirements verified in the course document |
| docs/PROJECT_PROPOSAL.md | 7-section project sheet, MVP vs stretch scope |
| docs/ARCHITECTURE.md, docs/diagrams/ | Architecture, ACL model, identifiers, Mermaid diagrams |
| docs/INTEGRATION.md, contracts/ | API contract, JSON Schemas, OpenAPI, real examples, connections |
| docs/DATA.md | Data sources, licences, schema, quality, privacy |
| docs/ANNOTATION_PROTOCOL.md | How queries and relevance judgments were made (LLM-drafted) |
| docs/EVALUATION.md | Methodology and results vs targets |
| docs/SECURITY_OVERSIGHT.md | Security, traceability, human oversight, shadow mode |
| docs/DECISIONS.md | Architectural decision log (ADR-001..009) |
| docs/REPRODUCIBILITY.md | From clean clone to results |
| docs/DEFENSE_NOTES.md | Notes for the oral defence (Italian) |
| docs/DELIVERABLES_CHECKLIST.md | The 8 common deliverables -> where they are |
| docs/PROGRESS.md, docs/OPEN_QUESTIONS.md | State of work, questions for the professor |
