"""Render result tables from eval/results/*.json into the docs, between markers:
    <!-- RESULTS:<NAME>:START --> ... <!-- RESULTS:<NAME>:END -->
so that no number in the documentation is typed by hand.

Usage:
    python eval/render_results.py      (after eval/run_eval.py)
"""

from __future__ import annotations

import json
import re
import sys

from common import RESULTS, ROOT

DOCS = [ROOT / "docs" / "EVALUATION.md", ROOT / "docs" / "REPORT.md", ROOT / "docs" / "REPRODUCIBILITY.md"]
SYSTEMS = ("B0", "S1", "S2")


def f(v, nd=3):
    return "n/a" if v is None else f"{v:.{nd}f}"


def table(header, rows):
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def blocks() -> dict[str, str]:
    r = json.loads((RESULTS / "eval_latest.json").read_text(encoding="utf-8"))
    cal = json.loads((RESULTS / "calibration.json").read_text(encoding="utf-8"))
    mc = json.loads((RESULTS / "model_comparison.json").read_text(encoding="utf-8"))
    o = r["overall"]
    src = f"Source: `eval/results/eval_{r['generated_at']}.json` (copy: `eval_latest.json`), test split SHA-256 `{r['test_split_sha256'][:16]}...`."

    main = table(
        ["Metric (D1 test, 60 in-scope / 10 out-of-scope)", "B0 BM25", "S1 dense", "S2 hybrid"],
        [[m, *(f(o[s][m]) for s in SYSTEMS)] for m in
         ("recall@1", "recall@5", "recall@10", "precision@1", "precision@5", "precision@10", "mrr@10", "ndcg@10", "correct_source@3",
          "abstention_correctness", "false_abstention_rate")],
    )
    lat = r["latency_api"]
    latency = table(["Configuration (POST /v1/search, in-process API)", "n", "p50 ms", "p95 ms", "max ms"],
                    [[k, v["n"], f(v["p50_ms"], 1), f(v["p95_ms"], 1), f(v["max_ms"], 1)] for k, v in lat.items()])
    hw = r["hardware"]
    hardware = (f"Hardware: {hw.get('gpu')}, CPU {hw.get('cpu')} ({hw.get('cpu_count')} logical), RAM {hw.get('ram_gb')} GB, "
                f"{hw.get('os')}, Python {hw.get('python')}, torch {hw.get('torch')}. Versions: {r['versions']}.")

    t = r["targets"]
    targets = table(
        ["Target (OUR proposal, not official)", "Measured", "Met?"],
        [
            ["T1 S2 >= B0 on nDCG@10 and Recall@10", f"S2 {f(t['T1_S2_ge_B0_ndcg10_and_recall10']['S2'][0])} / {f(t['T1_S2_ge_B0_ndcg10_and_recall10']['S2'][1])} vs B0 {f(t['T1_S2_ge_B0_ndcg10_and_recall10']['B0'][0])} / {f(t['T1_S2_ge_B0_ndcg10_and_recall10']['B0'][1])}", "yes" if t["T1_S2_ge_B0_ndcg10_and_recall10"]["met"] else "**no**"],
            ["T2 correct-source rate >= 0.80 (S2)", f(t["T2_correct_source_rate_ge_0.80"]["value"]), "yes" if t["T2_correct_source_rate_ge_0.80"]["met"] else "**no**"],
            ["T3 abstention correctness >= 0.70 (S2)", f(t["T3_abstention_correctness_ge_0.70"]["value"]), "yes" if t["T3_abstention_correctness_ge_0.70"]["met"] else "**no**"],
            ["T4 latency p95 < 1.5 s without reranker (S2)", f"{f(t['T4_latency_p95_lt_1500ms_no_reranker']['value_ms'], 1)} ms", "yes" if t["T4_latency_p95_lt_1500ms_no_reranker"]["met"] else "**no**"],
            ["T4 latency p95 < 3 s with reranker", "not measured", "n/a - reranker (S3) is a stretch goal, not implemented"],
            ["T5 ACL leakage = 0", f"{t['T5_acl_leakage_eq_0']['value']} leaks / {r['acl_leakage']['passages_checked']} passages checked ({r['acl_leakage']['principals']} principals x {r['acl_leakage']['queries']} queries x 3 systems)", "yes" if t["T5_acl_leakage_eq_0"]["met"] else "**no**"],
        ],
    )

    def group(name):
        rows = []
        for g, d in r[name].items():
            rows.append([g, d["S2"]["n_in_scope"], d["S2"]["n_out_of_scope"],
                         *(f(d[s]["ndcg@10"]) for s in SYSTEMS), *(f(d[s]["correct_source@3"]) for s in SYSTEMS),
                         *(f(d[s]["abstention_correctness"]) for s in SYSTEMS)])
        return table([name, "in", "oos", "nDCG@10 B0", "S1", "S2", "corr.src B0", "S1", "S2", "abst. B0", "S1", "S2"], rows)

    st = r["randomization_tests"]
    stats = table(["Comparison (60 in-scope test queries)", "mean diff", "bootstrap 95% CI", "p (two-sided)"],
                  [[k.replace("_vs_", " vs ").replace("_", " "), f(v["mean_difference"], 4), f"[{f(v['ci95'][0], 4)}, {f(v['ci95'][1], 4)}]", f(v["p_value"], 4)]
                   for k, v in st.items()])
    stats += f"\n\nPaired sign-flip randomization test, {next(iter(st.values()))['iterations']} iterations, seed {next(iter(st.values()))['seed']}. Reported as evidence, NOT used as a success criterion."

    d2 = r.get("d2_scifact")
    d2t = "D2 not run." if not d2 else table(["D2 SciFact (300 test queries, document level)", *SYSTEMS],
                                            [[m, *(f(d2["overall"][s][m]) for s in SYSTEMS)] for m in ("ndcg@10", "recall@10", "mrr@10")])

    calib = (f"Calibrated on the tuning split (`eval/results/calibration.json`, embedding {cal['embedding_model']}): "
             f"IE_MIN_DENSE = {cal['ie_min_dense']} (tuning balanced accuracy {f(cal['dense']['balanced_accuracy'])}), "
             f"IE_MIN_BM25 = {cal['ie_min_bm25']} (tuning balanced accuracy {f(cal['bm25']['balanced_accuracy'])}). "
             f"Observed top-dense ranges on tuning: in-scope {cal['signal_ranges']['dense']['in']}, out-of-scope {cal['signal_ranges']['dense']['out']}.")
    models = table(["Model (tuning split, 40 queries)", "S1 nDCG@10", "S2 nDCG@10", "S2 Recall@10"],
                   [[m, f(v["S1"]["ndcg@10"]), f(v["S2"]["ndcg@10"]), f(v["S2"]["recall@10"])] for m, v in mc["models"].items()])

    summary = table(["", "B0 BM25", "S1 dense", "S2 hybrid"],
                    [[m, *(f(o[s][m]) for s in SYSTEMS)] for m in ("ndcg@10", "recall@10", "mrr@10", "correct_source@3", "abstention_correctness")])
    repro_path = RESULTS / "reproduce_latest.json"
    if repro_path.exists():
        rp = json.loads(repro_path.read_text(encoding="utf-8"))
        repro = (f"Run started {rp['started']} (clean={rp['clean']}), total {f(rp['total_seconds'], 1)} s, ok={rp['ok']}. "
                 "Source: `eval/results/reproduce_latest.json`.\n\n"
                 + table(["Step", "Exit code", "Seconds"], [[s["step"], s["exit_code"], f(s["seconds"], 1)] for s in rp["steps"]]))
    else:
        repro = "Not run yet."
    return {
        "REPRO": repro,
        "MAIN": src + "\n\n" + main,
        "TARGETS": targets,
        "LATENCY": latency + "\n\n" + hardware,
        "BYTYPE": group("by_type") + "\n\n" + group("by_lang") + "\n\n" + group("by_target_source"),
        "STATS": stats,
        "D2": d2t,
        "CALIBRATION": calib,
        "MODELS": models,
        "SUMMARY": src + "\n\n" + summary + "\n\n" + targets,
    }


def main() -> int:
    b = blocks()
    for doc in DOCS:
        if not doc.exists():
            continue
        text = doc.read_text(encoding="utf-8")
        for name, content in b.items():
            text = re.sub(rf"(<!-- RESULTS:{name}:START -->).*?(<!-- RESULTS:{name}:END -->)",
                          lambda m: f"{m.group(1)}\n{content}\n{m.group(2)}", text, flags=re.S)
        doc.write_text(text, encoding="utf-8", newline="\n")
        print("rendered", doc.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
