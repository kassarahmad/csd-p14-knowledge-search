"""Priorities of the student's review worksheet (eval/review_worksheet.py)."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "eval"))

from review_worksheet import review  # noqa: E402


def query(**kw):
    q = {"qid": "Q900", "split": "test", "type": "keyword", "lang": "it", "targets": [{}, {}]}
    q.update(kw)
    return q


def test_failure_and_out_of_scope_are_priority_1():
    assert review(query(), {}, {"Q900": ["no_correct_source_in_top3"]})[0] == 1
    assert review(query(type="out_of_scope", targets=[]), {}, {})[0] == 1


def test_paraphrase_solved_by_bm25_is_priority_1():
    metrics = {("Q900", "B0"): {"ndcg@10": "0.95"}}
    priority, reasons, _ = review(query(type="paraphrase"), metrics, {})
    assert priority == 1 and "BM25" in reasons[0]


def test_english_or_single_target_is_priority_2_and_plain_query_is_3():
    assert review(query(lang="en"), {}, {})[0] == 2
    assert review(query(targets=[{}]), {}, {})[0] == 2
    assert review(query(), {}, {}) == (3, [], {"s2": {}, "b0": {}})
