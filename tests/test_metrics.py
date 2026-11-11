import math

import pytest

from p14_search.evaluation.metrics import (
    correct_source_at,
    mrr_at,
    ndcg_at,
    paired_randomization_test,
    precision_at,
    recall_at,
)

GRADES = {"a": 2, "b": 1, "c": 2}


def test_binary_metrics_use_grade_two():
    ranked = ["x", "a", "b", "y", "c"]
    assert recall_at(ranked, GRADES, 2) == 0.5
    assert recall_at(ranked, GRADES, 5) == 1.0
    assert precision_at(ranked, GRADES, 5) == pytest.approx(2 / 5)
    assert mrr_at(ranked, GRADES) == 0.5
    assert recall_at(ranked, {}, 5) is None  # out-of-scope query: undefined, not zero


def test_ndcg_perfect_and_partial():
    assert ndcg_at(["a", "c", "b"], GRADES) == pytest.approx(1.0)
    worse = ndcg_at(["b", "a", "c"], GRADES)
    ideal = 3 / math.log2(2) + 3 / math.log2(3) + 1 / math.log2(4)
    assert worse == pytest.approx((1 + 3 / math.log2(3) + 3 / math.log2(4)) / ideal)
    assert ndcg_at(["a"], {}) is None


def test_correct_source_counts_grade_one():
    assert correct_source_at(["x", "y", "b"], GRADES) == 1.0
    assert correct_source_at(["x", "y", "z", "a"], GRADES) == 0.0


def test_randomization_test_detects_clear_difference_and_not_noise():
    better = [0.9] * 30
    worse = [0.1] * 30
    assert paired_randomization_test(better, worse, iterations=2000)["p_value"] < 0.01
    same = paired_randomization_test([0.5, 0.6] * 15, [0.6, 0.5] * 15, iterations=2000)
    assert same["p_value"] > 0.5 and same["mean_difference"] == 0.0
