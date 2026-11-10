"""Shared evaluation logic: run queries through the retrieval systems and score them against qrels."""

from __future__ import annotations

import ctypes
import json
import os
import platform
import statistics
from dataclasses import dataclass, field
from pathlib import Path

from p14_search.evaluation.metrics import correct_source_at, mrr_at, ndcg_at, precision_at, recall_at
from p14_search.models import AccessLevel
from p14_search.retrieval.service import SearchService
from p14_search.security.principals import Principal

K = 10


def principals_by_name(config_path: Path) -> dict[str, Principal]:
    """Principals from config/principals.json, by name (evaluation runs in-process, no API keys needed)."""
    items = json.loads(Path(config_path).read_text(encoding="utf-8"))["principals"]
    return {i["name"]: Principal(i["name"], i["role"], AccessLevel(i["level"]), tuple(i["offices"])) for i in items}


@dataclass
class QueryRun:
    qid: str
    system: str
    ranked: list[str]
    insufficient_evidence: bool
    top_bm25: float | None
    top_dense: float | None
    metrics: dict = field(default_factory=dict)


def run_queries(search: SearchService, queries: list[dict], principals: dict[str, Principal], systems: tuple[str, ...],
                k: int = K) -> dict[str, dict[str, QueryRun]]:
    """{system: {qid: QueryRun}}. The insufficient-evidence flag uses the thresholds in search.settings."""
    out: dict[str, dict[str, QueryRun]] = {s: {} for s in systems}
    for q in queries:
        rankings = search.rank_all(q["query"], principals[q["principal"]], k, systems)
        for s, r in rankings.items():
            out[s][q["qid"]] = QueryRun(q["qid"], s, [h.passage_id for h in r.hits], r.insufficient_evidence, r.top_bm25, r.top_dense)
    return out


def score(run: QueryRun, grades: dict[str, int], in_scope: bool) -> dict:
    m: dict = {"insufficient_evidence": run.insufficient_evidence}
    if in_scope:
        r = run.ranked
        m.update(
            {
                "recall@1": recall_at(r, grades, 1), "recall@5": recall_at(r, grades, 5), "recall@10": recall_at(r, grades, 10),
                "precision@1": precision_at(r, grades, 1), "precision@5": precision_at(r, grades, 5),
                "precision@10": precision_at(r, grades, 10),
                "mrr@10": mrr_at(r, grades, 10), "ndcg@10": ndcg_at(r, grades, 10),
                "correct_source@3": correct_source_at(r, grades, 3),
            }
        )
    else:
        m["abstained"] = run.insufficient_evidence
    return m


def mean(values) -> float | None:
    vals = [v for v in values if v is not None]
    return round(statistics.fmean(vals), 4) if vals else None


IN_SCOPE_METRICS = ("recall@1", "recall@5", "recall@10", "precision@1", "precision@5", "precision@10", "mrr@10", "ndcg@10",
                    "correct_source@3")


def aggregate(runs: dict[str, QueryRun], queries: list[dict]) -> dict:
    ins = [q for q in queries if q["type"] != "out_of_scope"]
    oos = [q for q in queries if q["type"] == "out_of_scope"]
    agg = {m: mean(runs[q["qid"]].metrics[m] for q in ins) for m in IN_SCOPE_METRICS}
    agg["n_in_scope"] = len(ins)
    agg["n_out_of_scope"] = len(oos)
    agg["abstention_correctness"] = mean(1.0 if runs[q["qid"]].metrics["abstained"] else 0.0 for q in oos)
    agg["false_abstention_rate"] = mean(1.0 if runs[q["qid"]].insufficient_evidence else 0.0 for q in ins)
    return agg


def hardware() -> dict:
    info = {"os": platform.platform(), "cpu": platform.processor(), "cpu_count": os.cpu_count(), "python": platform.python_version()}
    try:
        class MemoryStatus(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong), ("ullTotalPhys", ctypes.c_ulonglong),
                        ("ullAvailPhys", ctypes.c_ulonglong), ("ullTotalPageFile", ctypes.c_ulonglong),
                        ("ullAvailPageFile", ctypes.c_ulonglong), ("ullTotalVirtual", ctypes.c_ulonglong),
                        ("ullAvailVirtual", ctypes.c_ulonglong), ("sullAvailExtendedVirtual", ctypes.c_ulonglong)]

        stat = MemoryStatus()
        stat.dwLength = ctypes.sizeof(MemoryStatus)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
        info["ram_gb"] = round(stat.ullTotalPhys / 1024**3, 1)
    except Exception:
        pass
    try:
        import torch

        info["gpu"] = torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
        info["torch"] = torch.__version__
    except Exception:
        pass
    return info
