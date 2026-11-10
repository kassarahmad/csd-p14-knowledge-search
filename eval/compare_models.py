"""ADR-005: compare candidate multilingual embedding models on the TUNING split only (S1 dense and S2 hybrid).

Prerequisite: python eval/build_dense_index.py --model <m> for each candidate.
Usage:
    python eval/compare_models.py  -> eval/results/model_comparison.json
"""

from __future__ import annotations

import sys
import time

from common import RESULTS, load_qrels, queries, search_service, timestamp, write_json

from p14_search.config import get_settings
from p14_search.evaluation.runner import aggregate, hardware, principals_by_name, run_queries, score

CANDIDATES = ["intfloat/multilingual-e5-small", "ibm-granite/granite-embedding-107m-multilingual"]


def main() -> int:
    tuning = queries("tuning")
    qrels = load_qrels()
    principals = principals_by_name(get_settings().principals_path)
    report = {"split": "tuning", "n_queries": len(tuning), "hardware": hardware(), "models": {}}
    for model in CANDIDATES:
        search = search_service(model)
        search.rank_all("riscaldamento", principals["employee"], 10, ("S1",))  # warm-up (model load, CUDA init)
        t0 = time.perf_counter()
        runs = run_queries(search, tuning, principals, ("S1", "S2"))
        elapsed = time.perf_counter() - t0
        result = {"seconds_for_all_queries": round(elapsed, 2), "embedding_dim": search.dense.embedder.dim}
        for system, by_qid in runs.items():
            for q in tuning:
                by_qid[q["qid"]].metrics = score(by_qid[q["qid"]], qrels[q["qid"]], q["type"] != "out_of_scope")
            result[system] = aggregate(by_qid, tuning)
        report["models"][model] = result
        print(model, {s: {m: result[s][m] for m in ("ndcg@10", "recall@10", "mrr@10")} for s in ("S1", "S2")})
    best = max(CANDIDATES, key=lambda m: (report["models"][m]["S2"]["ndcg@10"], -report["models"][m]["embedding_dim"]))
    report["selected_by_rule"] = best
    report["rule"] = "highest S2 nDCG@10 on the tuning split; tie -> smaller embedding dimension"
    write_json(RESULTS / f"model_comparison_{timestamp()}.json", report)
    write_json(RESULTS / "model_comparison.json", report)
    print("selected:", best)
    return 0


if __name__ == "__main__":
    sys.exit(main())
