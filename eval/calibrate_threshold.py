"""Calibrate the insufficient_evidence thresholds on the TUNING split only.

Signals: top dense cosine similarity (S1/S2) and top BM25 score (B0). For each signal the threshold maximises
balanced accuracy = (share of out-of-scope queries flagged + share of in-scope queries NOT flagged) / 2; ties
go to the lower threshold (fewer false abstentions). Thresholds are midpoints between observed values.

Usage:
    python eval/calibrate_threshold.py  -> eval/results/calibration.json (read by run_eval.py; copy into .env for the API)
"""

from __future__ import annotations

import sys

from common import CALIBRATION, RESULTS, queries, search_service, timestamp, write_json

from p14_search.config import get_settings
from p14_search.evaluation.runner import principals_by_name


def best_threshold(in_scope: list[float], out_scope: list[float]) -> dict:
    values = sorted(set(in_scope + out_scope))
    candidates = [0.0] + [(a + b) / 2 for a, b in zip(values, values[1:])] + [values[-1] + 1e-6]
    best = None
    for th in candidates:
        flagged_oos = sum(v < th for v in out_scope) / len(out_scope)
        answered_in = sum(v >= th for v in in_scope) / len(in_scope)
        bacc = (flagged_oos + answered_in) / 2
        if best is None or bacc > best["balanced_accuracy"] + 1e-12:
            best = {"threshold": round(th, 6), "balanced_accuracy": round(bacc, 4), "oos_flagged": round(flagged_oos, 4),
                    "in_scope_answered": round(answered_in, 4)}
    return best


def main() -> int:
    settings = get_settings().model_copy(update={"ie_min_dense": 0.0, "ie_min_bm25": 0.0})
    search = search_service(settings=settings)
    principals = principals_by_name(settings.principals_path)
    tuning = queries("tuning")
    signals = {"dense": {"in": [], "out": []}, "bm25": {"in": [], "out": []}}
    per_query = []
    for q in tuning:
        r = search.rank_all(q["query"], principals[q["principal"]], 10, ("S2",))["S2"]
        side = "out" if q["type"] == "out_of_scope" else "in"
        signals["dense"][side].append(r.top_dense or 0.0)
        signals["bm25"][side].append(r.top_bm25 or 0.0)
        per_query.append({"qid": q["qid"], "type": q["type"], "top_dense": r.top_dense, "top_bm25": r.top_bm25})
    dense = best_threshold(signals["dense"]["in"], signals["dense"]["out"])
    bm25 = best_threshold(signals["bm25"]["in"], signals["bm25"]["out"])
    report = {
        "split": "tuning",
        "embedding_model": search.dense.embedder.name,
        "ie_min_dense": dense["threshold"],
        "ie_min_bm25": bm25["threshold"],
        "dense": dense,
        "bm25": bm25,
        "signal_ranges": {k: {side: [round(min(v), 4), round(max(v), 4)] for side, v in s.items()} for k, s in signals.items()},
        "per_query": per_query,
    }
    write_json(RESULTS / f"calibration_{timestamp()}.json", report)
    write_json(CALIBRATION, report)
    print(f"IE_MIN_DENSE={dense['threshold']}  {dense}")
    print(f"IE_MIN_BM25={bm25['threshold']}  {bm25}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
