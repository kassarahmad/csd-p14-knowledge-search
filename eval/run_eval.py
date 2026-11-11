"""Main evaluation (deliverable 4) on the frozen D1 TEST split, plus the D2 sanity benchmark.

Computes, for B0 (BM25), S1 (dense) and S2 (hybrid RRF): Recall/Precision@1/5/10, MRR@10, nDCG@10,
correct-source@3, abstention correctness, false-abstention rate; per query type and language; ACL leakage
for every principal; end-to-end API latency p50/p95; a paired randomization test S2 vs B0 (reported, not a
target). Thresholds for insufficient_evidence come from eval/results/calibration.json (tuning split only).

Usage:
    python eval/run_eval.py [--skip-d2]
Outputs: eval/results/eval_<timestamp>.json, eval_<timestamp>_per_query.csv, and eval_latest.json (copy).
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time

from common import CALIBRATION, RESULTS, ROOT, load_qrels, queries, search_service, timestamp, write_json
from dotenv import dotenv_values
from fastapi.testclient import TestClient
from freeze_test import test_hash, verify

from p14_search.api.app import create_app
from p14_search.config import get_settings
from p14_search.evaluation.metrics import paired_randomization_test, percentile
from p14_search.evaluation.runner import aggregate, hardware, mean, principals_by_name, run_queries, score
from p14_search.services import build_services

SYSTEMS = ("B0", "S1", "S2")
TARGETS = {"T2_correct_source_min": 0.80, "T3_abstention_min": 0.70, "T4_p95_ms_no_reranker": 1500}


def visible(level_of_principal: str, offices: tuple[str, ...], access_level: str, office: str) -> bool:
    """Independent re-statement of the ACL rules (oracle for the leakage check; deliberately not imported)."""
    if access_level == "public":
        return True
    if access_level == "internal":
        return level_of_principal in ("internal", "restricted")
    return level_of_principal == "restricted" and ("*" in offices or office in offices)


def acl_leakage(search, test, principals) -> dict:
    docs = {r["passage_id"]: (r["access_level"], r["office"]) for r in search.store.query(
        "SELECT p.passage_id, d.access_level, d.office FROM passages p JOIN documents d ON d.document_id = p.document_id")}
    checks = leaks = 0
    for p in principals.values():
        for q in test:
            for s, r in search.rank_all(q["query"], p, 10, SYSTEMS).items():
                for h in r.hits:
                    checks += 1
                    if not visible(p.level.value, p.offices, *docs[h.passage_id]):
                        leaks += 1
    return {"principals": len(principals), "queries": len(test), "systems": len(SYSTEMS), "passages_checked": checks, "leaks": leaks}


def api_latency(settings, test, principals_cfg) -> dict:
    env = {**dotenv_values(ROOT / ".env"), **os.environ}
    key_of = {p["name"]: env.get(p["api_key_env"]) for p in principals_cfg}
    services = build_services(settings)
    client = TestClient(create_app(settings, services=services))
    out = {}
    configs = [(s, None) for s in SYSTEMS] + [("S2", "B0")]
    for display, shadow in configs:
        settings.display_system, settings.shadow_system = display, shadow
        for q in test[:3]:  # warm-up
            client.post("/v1/search", json={"query": q["query"]}, headers={"X-API-Key": key_of[q["principal"]]})
        times = []
        for q in test:
            t0 = time.perf_counter()
            r = client.post("/v1/search", json={"query": q["query"]},
                            headers={"X-API-Key": key_of[q["principal"]], "X-Request-ID": f"eval-{q['qid']}-{display}-{time.time_ns()}"})
            times.append((time.perf_counter() - t0) * 1000)
            assert r.status_code == 200, r.text
        name = display + (f"+shadow_{shadow}" if shadow else "")
        out[name] = {"n": len(times), "p50_ms": round(percentile(times, 50), 1), "p95_ms": round(percentile(times, 95), 1),
                     "max_ms": round(max(times), 1)}
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-d2", action="store_true")
    args = parser.parse_args()
    if not verify():
        raise SystemExit("test split changed since it was frozen (eval/freeze_test.py --verify)")
    if not CALIBRATION.exists():
        raise SystemExit("run eval/calibrate_threshold.py first (thresholds are calibrated on the tuning split)")
    cal = json.loads(CALIBRATION.read_text(encoding="utf-8"))
    settings = get_settings().model_copy(update={"ie_min_dense": cal["ie_min_dense"], "ie_min_bm25": cal["ie_min_bm25"]})
    search = search_service(settings=settings)
    principals = principals_by_name(settings.principals_path)
    principals_cfg = json.loads(settings.principals_path.read_text(encoding="utf-8"))["principals"]
    test = queries("test")
    qrels = load_qrels()

    runs = run_queries(search, test, principals, SYSTEMS)
    for by_qid in runs.values():
        for q in test:
            by_qid[q["qid"]].metrics = score(by_qid[q["qid"]], qrels[q["qid"]], q["type"] != "out_of_scope")

    overall = {s: aggregate(runs[s], test) for s in SYSTEMS}
    by_type = {t: {s: aggregate(runs[s], [q for q in test if q["type"] == t]) for s in SYSTEMS}
               for t in sorted({q["type"] for q in test})}
    by_lang = {lang: {s: aggregate(runs[s], [q for q in test if q["lang"] == lang]) for s in SYSTEMS}
               for lang in sorted({q["lang"] for q in test})}
    by_source = {src: {s: aggregate(runs[s], [q for q in test if q["type"] != "out_of_scope"
                                              and q["targets"][0]["document_id"].startswith(src)]) for s in SYSTEMS}
                 for src in ("d1a:", "d1b:")}
    ins = [q for q in test if q["type"] != "out_of_scope"]
    stats = {
        f"{a}_vs_{b}_{m}": paired_randomization_test([runs[a][q["qid"]].metrics[m] for q in ins], [runs[b][q["qid"]].metrics[m] for q in ins])
        for a, b in (("S2", "B0"), ("S2", "S1"), ("S1", "B0")) for m in ("ndcg@10", "recall@10")
    }
    leakage = acl_leakage(search, test, principals)
    latency = api_latency(settings.model_copy(), test, principals_cfg)

    s2, b0 = overall["S2"], overall["B0"]
    targets = {
        "T1_S2_ge_B0_ndcg10_and_recall10": {"S2": [s2["ndcg@10"], s2["recall@10"]], "B0": [b0["ndcg@10"], b0["recall@10"]],
                                           "met": s2["ndcg@10"] >= b0["ndcg@10"] and s2["recall@10"] >= b0["recall@10"]},
        "T2_correct_source_rate_ge_0.80": {"value": s2["correct_source@3"], "met": s2["correct_source@3"] >= TARGETS["T2_correct_source_min"]},
        "T3_abstention_correctness_ge_0.70": {"value": s2["abstention_correctness"],
                                              "met": (s2["abstention_correctness"] or 0) >= TARGETS["T3_abstention_min"]},
        "T4_latency_p95_lt_1500ms_no_reranker": {"value_ms": latency["S2"]["p95_ms"], "met": latency["S2"]["p95_ms"] < TARGETS["T4_p95_ms_no_reranker"]},
        "T4_latency_p95_lt_3000ms_with_reranker": {"value_ms": None, "met": None, "note": "reranker (S3) not implemented (stretch goal)"},
        "T5_acl_leakage_eq_0": {"value": leakage["leaks"], "met": leakage["leaks"] == 0},
    }
    d2 = None
    if not args.skip_d2:
        from d2_scifact import evaluate as d2_evaluate

        d2 = d2_evaluate(settings)

    ts = timestamp()
    report = {
        "generated_at": ts,
        "test_split_sha256": test_hash()[0],
        "calibration": {"ie_min_dense": cal["ie_min_dense"], "ie_min_bm25": cal["ie_min_bm25"], "source": "eval/results/calibration.json"},
        "versions": search.versions().model_dump(),
        "hardware": hardware(),
        "n_test_queries": len(test),
        "overall": overall,
        "by_type": by_type,
        "by_lang": by_lang,
        "by_target_source": by_source,
        "randomization_tests": stats,
        "acl_leakage": leakage,
        "latency_api": latency,
        "targets": targets,
        "d2_scifact": d2,
    }
    write_json(RESULTS / f"eval_{ts}.json", report)
    write_json(RESULTS / "eval_latest.json", report)
    with open(RESULTS / f"eval_{ts}_per_query.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        cols = ["recall@10", "precision@10", "mrr@10", "ndcg@10", "correct_source@3"]
        w.writerow(["qid", "type", "lang", "system", "insufficient_evidence", *cols, "top_dense", "top_bm25", "top3_passages"])
        for q in test:
            for s in SYSTEMS:
                r = runs[s][q["qid"]]
                w.writerow([q["qid"], q["type"], q["lang"], s, r.insufficient_evidence, *[r.metrics.get(c) for c in cols],
                            r.top_dense and round(r.top_dense, 4), r.top_bm25 and round(r.top_bm25, 4), " ".join(r.ranked[:3])])
    print(json.dumps({s: {m: overall[s][m] for m in ("ndcg@10", "recall@10", "mrr@10", "correct_source@3", "abstention_correctness")}
                      for s in SYSTEMS}, indent=1))
    print(json.dumps({k: v["met"] for k, v in targets.items()}, indent=1))
    print("latency:", latency, "\nleakage:", leakage)
    if d2:
        print("D2:", json.dumps(d2["overall"], indent=1))
    print(f"-> eval/results/eval_{ts}.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
