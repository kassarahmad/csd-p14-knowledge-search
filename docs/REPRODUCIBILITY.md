# Reproducibility - from a clean clone to the results

Tested on Windows 11 with Docker Desktop, an NVIDIA RTX 5070 Laptop GPU and Python 3.11 (exact hardware recorded in
every `eval/results/eval_*.json`). No paid service, no API key from third parties. Internet is needed once for:
the Python packages, the two embedding models from Hugging Face, the Normattiva / Gazzetta Ufficiale documents and
the SciFact zip.

## 1. Environment
```powershell
git clone <repository> csd-p14-knowledge-search
cd csd-p14-knowledge-search
python -m pip install --user uv
python -m uv python install 3.11
python -m uv venv --python 3.11 .venv
python -m uv pip install --python .venv\Scripts\python.exe -e ".[dev,data,ui]"
copy .env.example .env
docker compose up -d
```
CPU only: set `EMBEDDING_DEVICE=cpu` in `.env`.

## 2. One command for everything
```powershell
.venv\Scripts\python.exe scripts\reproduce.py --clean
.venv\Scripts\python.exe eval\render_results.py     # refresh the timing table below
```
`--clean` deletes only generated data (SQLite files in `data/processed/`, Qdrant collections of this project); raw
downloads in `data/raw/` are kept and re-used (delete them to re-download). Steps (each is also a standalone command):

| Step | Command | Output |
|---|---|---|
| fetch_corpus | `python scripts/fetch_corpus.py` | data/raw/d1a/*, data/raw/d2/* + fetch records with SHA-256 |
| generate_d1b | `python scripts/generate_d1b.py` | data/raw/d1b/* (synthetic) + generation_record.json |
| ingest_corpus | `python scripts/ingest_corpus.py` | data/processed/p14.sqlite + Qdrant collection (simulated owner approval) |
| corpus_stats | `python scripts/corpus_stats.py` | eval/results/corpus_stats.json |
| build_qrels | `python eval/build_qrels.py` | eval/qrels/d1_qrels.json (fails if a snippet is not found) |
| verify_test_freeze | `python eval/freeze_test.py --verify` | fails if the test split changed |
| build_dense_index_granite | `python eval/build_dense_index.py --model ibm-granite/granite-embedding-107m-multilingual` | second Qdrant collection (ADR-005) |
| compare_models | `python eval/compare_models.py` | eval/results/model_comparison.json (tuning only) |
| calibrate_threshold | `python eval/calibrate_threshold.py` | eval/results/calibration.json (tuning only) |
| pytest | `python -m pytest` | eval/results/pytest_latest.txt |
| run_eval | `python eval/run_eval.py` | eval/results/eval_<ts>.json, _per_query.csv, eval_latest.json (includes D2) |
| error_analysis | `python eval/error_analysis.py` | eval/results/failures_latest.json |
| render_results | `python eval/render_results.py` | tables in EVALUATION.md, REPORT.md, this file |

After `calibrate_threshold`, copy `ie_min_dense` / `ie_min_bm25` from `eval/results/calibration.json` into `.env`
(`IE_MIN_DENSE`, `IE_MIN_BM25`) so that the API uses the calibrated thresholds; the evaluation reads them from the file.

## 3. Measured runtimes (last run of scripts/reproduce.py)
<!-- RESULTS:REPRO:START -->
Run started 2026-11-10T12:46:08 (clean=True), total 447.4 s, ok=True. Source: `eval/results/reproduce_latest.json`.

| Step | Exit code | Seconds |
|---|---|---|
| fetch_corpus | 0 | 0.1 |
| generate_d1b | 0 | 0.7 |
| ingest_corpus | 0 | 46.9 |
| corpus_stats | 0 | 0.6 |
| build_qrels | 0 | 0.7 |
| verify_test_freeze | 0 | 0.1 |
| build_dense_index_granite | 0 | 20.4 |
| compare_models | 0 | 15.5 |
| calibrate_threshold | 0 | 10.7 |
| pytest | 0 | 6.6 |
| run_eval | 0 | 331.7 |
| error_analysis | 0 | 11.8 |
| render_results | 0 | 0.7 |
<!-- RESULTS:REPRO:END -->

## 4. Determinism and expected differences
- Passage ids, qrels and retrieval rankings are deterministic for the same files, models and chunker version.
  Verified: two consecutive `reproduce.py --clean` runs gave the same `index_snapshot_id` and identical metrics,
  randomization tests and D2 results (only latency differed). A first run had shown tiny S2 differences because the
  synthetic DOCX files embedded the current time in their zip entries (new bytes -> new versions -> new ids -> different
  tie-breaks in RRF); `generate_d1b.py` now writes fixed zip timestamps.
- Normattiva serves the text **in force on the download date**: re-downloading later can change D1a (the SHA-256 in
  `fetch_record.json` shows it). Then `build_qrels.py` reports missing snippets instead of silently changing results.
- Latency depends on the machine and its load; GPU kernels can introduce tiny floating-point differences.
- Re-running the evaluation appends rows to `query_log` (requests tagged `eval-...`).
