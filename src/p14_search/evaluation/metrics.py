"""IR metrics over graded passage-level qrels (definitions: docs/EVALUATION.md).

Binary relevance for Recall/Precision/MRR = grade 2 ("answers the query"); nDCG uses graded gains
(2^grade - 1); correct-source@3 counts any passage with grade >= 1 (right document AND right section).
"""

from __future__ import annotations

import math

import numpy as np


def recall_at(ranked: list[str], grades: dict[str, int], k: int) -> float | None:
    relevant = {p for p, g in grades.items() if g >= 2}
    if not relevant:
        return None
    return len(relevant & set(ranked[:k])) / len(relevant)


def precision_at(ranked: list[str], grades: dict[str, int], k: int) -> float:
    return sum(1 for p in ranked[:k] if grades.get(p, 0) >= 2) / k


def mrr_at(ranked: list[str], grades: dict[str, int], k: int = 10) -> float:
    for i, p in enumerate(ranked[:k]):
        if grades.get(p, 0) >= 2:
            return 1.0 / (i + 1)
    return 0.0


def ndcg_at(ranked: list[str], grades: dict[str, int], k: int = 10) -> float | None:
    def dcg(gs):
        return sum((2**g - 1) / math.log2(i + 2) for i, g in enumerate(gs))

    ideal = dcg(sorted(grades.values(), reverse=True)[:k])
    if ideal == 0:
        return None
    return dcg([grades.get(p, 0) for p in ranked[:k]]) / ideal


def correct_source_at(ranked: list[str], grades: dict[str, int], k: int = 3) -> float:
    return 1.0 if any(grades.get(p, 0) >= 1 for p in ranked[:k]) else 0.0


def percentile(values: list[float], q: float) -> float:
    return float(np.percentile(np.asarray(values, dtype=float), q)) if values else float("nan")


def paired_randomization_test(a: list[float], b: list[float], iterations: int = 10000, seed: int = 14) -> dict:
    """Two-sided paired sign-flip randomization test on mean(a - b), plus a bootstrap 95% CI of the mean
    difference. Reported as statistical evidence, not used as a success criterion."""
    diff = np.asarray(a, dtype=float) - np.asarray(b, dtype=float)
    n = len(diff)
    observed = float(diff.mean()) if n else 0.0
    rng = np.random.default_rng(seed)
    signs = rng.choice([-1.0, 1.0], size=(iterations, n))
    null = (signs * diff).mean(axis=1)
    p_value = float((np.sum(np.abs(null) >= abs(observed) - 1e-12) + 1) / (iterations + 1))
    boots = diff[rng.integers(0, n, size=(iterations, n))].mean(axis=1) if n else np.zeros(1)
    return {
        "n": n,
        "mean_difference": round(observed, 4),
        "ci95": [round(float(np.percentile(boots, 2.5)), 4), round(float(np.percentile(boots, 97.5)), 4)],
        "p_value": round(p_value, 4),
        "iterations": iterations,
        "seed": seed,
    }
