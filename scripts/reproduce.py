"""Run the whole pipeline end to end and record the duration and exit code of every step.

Usage (Qdrant must be running: docker compose up -d):
    python scripts/reproduce.py            # reuse existing indexes where possible
    python scripts/reproduce.py --clean    # delete GENERATED data first (SQLite files in data/processed,
                                           # Qdrant collections p14_passages__* and d2_scifact__*); raw downloads are kept
Output: eval/results/reproduce_<timestamp>.json and reproduce_latest.json; pytest output in eval/results/pytest_latest.txt.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
STEPS = [
    ("fetch_corpus", [PY, "scripts/fetch_corpus.py"], 900),
    ("generate_d1b", [PY, "scripts/generate_d1b.py"], 300),
    ("ingest_corpus", [PY, "scripts/ingest_corpus.py"], 1800),
    ("corpus_stats", [PY, "scripts/corpus_stats.py"], 300),
    ("build_qrels", [PY, "eval/build_qrels.py"], 300),
    ("verify_test_freeze", [PY, "eval/freeze_test.py", "--verify"], 60),
    ("build_dense_index_granite", [PY, "eval/build_dense_index.py", "--model", "ibm-granite/granite-embedding-107m-multilingual"], 1200),
    ("compare_models", [PY, "eval/compare_models.py"], 1200),
    ("calibrate_threshold", [PY, "eval/calibrate_threshold.py"], 900),
    ("pytest", [PY, "-m", "pytest", "-q"], 900),
    ("run_eval", [PY, "eval/run_eval.py"], 3600),
    ("error_analysis", [PY, "eval/error_analysis.py"], 900),
    ("render_results", [PY, "eval/render_results.py"], 120),
]


def clean() -> list[str]:
    from qdrant_client import QdrantClient

    from p14_search.config import get_settings

    removed = []
    for f in (ROOT / "data" / "processed").glob("*.sqlite*"):
        f.unlink()
        removed.append(str(f.relative_to(ROOT)))
    client = QdrantClient(url=get_settings().qdrant_url, timeout=60)
    for c in client.get_collections().collections:
        if c.name.startswith(("p14_passages__", "d2_scifact__")):
            client.delete_collection(c.name)
            removed.append(f"qdrant:{c.name}")
    return removed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--clean", action="store_true")
    args = parser.parse_args()
    started = dt.datetime.now()
    record = {"started": started.isoformat(timespec="seconds"), "clean": args.clean, "steps": []}
    if args.clean:
        record["removed"] = clean()
        print("removed:", record["removed"])
    env = {**__import__("os").environ, "PYTHONIOENCODING": "utf-8", "HF_HUB_DISABLE_SYMLINKS_WARNING": "1"}
    ok = True
    for name, cmd, timeout in STEPS:
        t0 = time.perf_counter()
        try:
            proc = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
            code, out = proc.returncode, proc.stdout + proc.stderr
        except subprocess.TimeoutExpired:
            code, out = "timeout", ""
        secs = round(time.perf_counter() - t0, 1)
        if name == "pytest":
            (ROOT / "eval" / "results" / "pytest_latest.txt").write_text(proc.stdout, encoding="utf-8", newline="\n")
        tail = [ln for ln in out.splitlines() if ln.strip() and not ln.startswith('{"ts"') and "warn" not in ln.lower()][-3:]
        record["steps"].append({"step": name, "exit_code": code, "seconds": secs, "tail": tail})
        print(f"{name:<28} exit={code!s:<8} {secs:>8.1f}s  {tail[-1] if tail else ''}")
        if code != 0:
            ok = False
            break
    record["total_seconds"] = round((dt.datetime.now() - started).total_seconds(), 1)
    record["ok"] = ok
    out_dir = ROOT / "eval" / "results"
    stamp = started.strftime("%Y%m%d-%H%M%S")
    for path in (out_dir / f"reproduce_{stamp}.json", out_dir / "reproduce_latest.json"):
        path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print("total", record["total_seconds"], "s ->", f"eval/results/reproduce_{stamp}.json")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
