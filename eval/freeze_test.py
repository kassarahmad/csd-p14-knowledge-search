"""Freeze (or verify) the held-out test split: SHA-256 of the canonical JSON of the test queries.

Usage:
    python eval/freeze_test.py           # write eval/queries/test_freeze.json
    python eval/freeze_test.py --verify  # exit 1 if the test split changed since it was frozen
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUERIES = ROOT / "eval" / "queries" / "d1_queries.jsonl"
FREEZE = ROOT / "eval" / "queries" / "test_freeze.json"


def test_hash() -> tuple[str, int]:
    queries = [json.loads(line) for line in QUERIES.read_text(encoding="utf-8").splitlines() if line.strip()]
    test = sorted((q for q in queries if q["split"] == "test"), key=lambda q: q["qid"])
    canonical = json.dumps(test, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest(), len(test)


def verify() -> bool:
    frozen = json.loads(FREEZE.read_text(encoding="utf-8"))
    return frozen["sha256"] == test_hash()[0]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    digest, n = test_hash()
    if args.verify:
        ok = verify()
        print(("OK" if ok else "CHANGED") + f": {n} test queries, sha256={digest[:16]}")
        return 0 if ok else 1
    FREEZE.write_text(json.dumps({"sha256": digest, "test_queries": n, "rule": "frozen before any tuning"}, indent=2) + "\n",
                      encoding="utf-8", newline="\n")
    print(f"frozen {n} test queries, sha256={digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
