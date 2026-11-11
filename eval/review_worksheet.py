"""Build the student's review worksheet for the LLM-drafted question set -> eval/review/review_worksheet.csv

Offline: reads only committed files (queries, latest per-query results, latest failures); no Qdrant, no model.
Each query gets a priority and the reasons for it, plus empty columns for the reviewer's verdict.

Priority 1 = must check before submission:
  - S2 failure listed by eval/error_analysis.py (failures_latest.json);
  - out-of-scope query (confirm the corpus really does not answer it);
  - paraphrase query that BM25 already solves (nDCG@10 >= 0.9): lexical overlap breaks writing rule 1 of the protocol.
Priority 2 = English or conceptual query (translation quality, type label), or test query with a single target.
Priority 3 = everything else (tuning queries included: they shaped the thresholds and the model choice).

Usage:
    python eval/review_worksheet.py
The CSV is written with a UTF-8 BOM so that Excel shows accented letters correctly.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUERIES = ROOT / "eval" / "queries" / "d1_queries.jsonl"
RESULTS = ROOT / "eval" / "results"
OUT = ROOT / "eval" / "review" / "review_worksheet.csv"

# Queries whose labels were already questioned in docs/EVALUATION.md (error analysis, categories C, F, G).
KNOWN_DOUBTS = {
    "Q022": "error analysis C: equivalent answer elsewhere (CAD art. 3-bis) not in qrels",
    "Q028": "error analysis C: L. 90/2024 art. 24 gives the same rule, not in qrels",
    "Q047": "error analysis C: D.P.R. 445/2000 art. 53 also answers, not in qrels",
    "Q065": "error analysis F: labelled out of scope, but L. 104/1992 mentions asili nido",
    "Q015": "error analysis G: ambiguous (privacy access vs civic access)",
}


def per_query_metrics() -> dict[tuple[str, str], dict]:
    # The newest per-query CSV belongs to the newest run, the one copied to eval_latest.json.
    path = sorted(RESULTS.glob("eval_*_per_query.csv"))[-1]
    with path.open(encoding="utf-8") as f:
        return {(row["qid"], row["system"]): row for row in csv.DictReader(f)}


def s2_failures() -> dict[str, list[str]]:
    data = json.loads((RESULTS / "failures_latest.json").read_text(encoding="utf-8"))
    return {f["qid"]: f["reasons"] for f in data["failures"] if f["system"] == "S2"}


def review(q: dict, metrics: dict, failures: dict) -> tuple[int, list[str], dict]:
    reasons: list[str] = []
    s2 = metrics.get((q["qid"], "S2"), {})
    b0 = metrics.get((q["qid"], "B0"), {})
    if q["qid"] in failures:
        reasons.append("S2 failure: " + ", ".join(failures[q["qid"]]))
    if q["type"] == "out_of_scope":
        reasons.append("out of scope: search it and confirm the corpus does not answer")
    if q["type"] == "paraphrase" and b0 and float(b0["ndcg@10"]) >= 0.9:
        reasons.append("paraphrase solved by BM25: probably shares the document's words")
    if q["qid"] in KNOWN_DOUBTS:
        reasons.append(KNOWN_DOUBTS[q["qid"]])
    priority = 1 if reasons else 3
    if priority == 3:
        if q["lang"] == "en":
            reasons.append("English: check translation quality")
        if q["type"] == "conceptual":
            reasons.append("conceptual: check that it really needs two facts or reasoning")
        if q["split"] == "test" and q["type"] != "out_of_scope" and len(q["targets"]) == 1:
            reasons.append("single target: is another document also an answer?")
        if reasons:
            priority = 2
    return priority, reasons, {"s2": s2, "b0": b0}


def main() -> int:
    queries = [json.loads(line) for line in QUERIES.read_text(encoding="utf-8").splitlines() if line.strip()]
    metrics = per_query_metrics()
    failures = s2_failures()
    rows = []
    for q in queries:
        priority, reasons, m = review(q, metrics, failures)
        targets = " || ".join(f"{t['document_id']} | {t['section']} | {t['snippet']}" for t in q["targets"])
        rows.append({
            "priority": priority,
            "qid": q["qid"],
            "split": q["split"],
            "type": q["type"],
            "lang": q["lang"],
            "principal": q["principal"],
            "query": q["query"],
            "targets (document | section | snippet)": targets,
            "S2 ndcg@10": m["s2"].get("ndcg@10", ""),
            "S2 correct_source@3": m["s2"].get("correct_source@3", ""),
            "S2 insufficient_evidence": m["s2"].get("insufficient_evidence", ""),
            "B0 ndcg@10": m["b0"].get("ndcg@10", ""),
            "why check": "; ".join(reasons),
            "verdict (OK / FIX_QUERY / FIX_TARGET / FIX_TYPE / DROP)": "",
            "new value": "",
            "reviewer notes": "",
        })
    rows.sort(key=lambda r: (r["priority"], r["split"] != "test", r["qid"]))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    counts = {p: sum(r["priority"] == p for r in rows) for p in (1, 2, 3)}
    print(f"{OUT.relative_to(ROOT)}: {len(rows)} queries - priority 1: {counts[1]}, 2: {counts[2]}, 3: {counts[3]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
