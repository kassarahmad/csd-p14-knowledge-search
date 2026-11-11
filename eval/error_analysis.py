"""Collect evaluation failures for manual error analysis -> eval/results/failures_<ts>.json

A failure (for the shown system S2, and for B0 when needed to reach --min failures) is:
- in-scope query with correct_source@3 = 0 or MRR@10 = 0 (answer passage not in top 10), or falsely flagged
  insufficient_evidence;
- out-of-scope query NOT flagged insufficient_evidence.
For each failure the top-3 returned passages are listed. Categories are assigned by hand in docs/EVALUATION.md.

Usage:
    python eval/error_analysis.py [--min 15]
"""

from __future__ import annotations

import argparse
import json
import sys

from common import CALIBRATION, RESULTS, load_qrels, queries, search_service, timestamp, write_json

from p14_search.config import get_settings
from p14_search.evaluation.runner import principals_by_name, run_queries, score


def failures_for(system: str, runs, test, qrels) -> list[dict]:
    out = []
    for q in test:
        r = runs[system][q["qid"]]
        m = score(r, qrels[q["qid"]], q["type"] != "out_of_scope")
        reasons = []
        if q["type"] == "out_of_scope":
            if not r.insufficient_evidence:
                reasons.append("out_of_scope_not_flagged")
        else:
            if m["correct_source@3"] == 0:
                reasons.append("no_correct_source_in_top3")
            if m["mrr@10"] == 0:
                reasons.append("answer_passage_not_in_top10")
            if r.insufficient_evidence:
                reasons.append("false_insufficient_evidence")
        if reasons:
            out.append({"qid": q["qid"], "system": system, "query": q["query"], "type": q["type"], "lang": q["lang"],
                        "reasons": reasons, "targets": q["targets"], "top_dense": r.top_dense, "top_bm25": r.top_bm25,
                        "ranked": r.ranked[:3]})
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--min", type=int, default=15)
    args = parser.parse_args()
    cal = json.loads(CALIBRATION.read_text(encoding="utf-8"))
    settings = get_settings().model_copy(update={"ie_min_dense": cal["ie_min_dense"], "ie_min_bm25": cal["ie_min_bm25"]})
    search = search_service(settings=settings)
    test = queries("test")
    runs = run_queries(search, test, principals_by_name(settings.principals_path), ("B0", "S2"))
    qrels = load_qrels()
    fails = failures_for("S2", runs, test, qrels)
    if len(fails) < args.min:
        fails += failures_for("B0", runs, test, qrels)
    for f in fails:
        rows = {r["passage_id"]: r for r in search.store.query(
            f"SELECT passage_id, document_id, section, page, substr(text, 1, 220) AS text FROM passages WHERE passage_id IN ({','.join('?' * len(f['ranked']))})",
            f["ranked"])} if f["ranked"] else {}
        f["top3"] = [dict(rows[p]) | {"grade": qrels[f["qid"]].get(p, 0)} for p in f["ranked"] if p in rows]
        del f["ranked"]
    path = RESULTS / f"failures_{timestamp()}.json"
    write_json(path, {"n": len(fails), "failures": fails})
    write_json(RESULTS / "failures_latest.json", {"n": len(fails), "failures": fails})
    print(f"{len(fails)} failures -> {path.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
