"""The P24 and P12 mock consumers against an in-process P14 (deliverable 7: two connections)."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "mocks" / "p24_external_assistant"))
sys.path.insert(0, str(ROOT / "mocks" / "p12_document_generation"))

from p12_client import build_draft  # noqa: E402
from p24_client import answer  # noqa: E402


def test_p24_answers_from_public_passages_with_citations(loaded):
    res = answer("orari sportello pubblico alfapubblico", loaded, "key-public")
    assert res["status"] == "answered"
    assert res["citations"] and all(c["passage_id"].startswith("p_") for c in res["citations"])
    assert "alfapubblico" in res["answer"]


def test_p24_never_receives_restricted_content(loaded):
    res = answer("gammahr budget riservato formazione", loaded, "key-public")
    assert "48.000" not in str(res)


def test_p24_escalates_on_insufficient_evidence(loaded, services):
    services.settings.ie_min_dense = 0.99
    res = answer("orari sportello", loaded, "key-public")
    assert res["status"] == "escalated" and "insufficient evidence" in res["reason"]


def test_p12_draft_cites_resolvable_passages(loaded):
    res = build_draft("lavoro agile giornate disconnessione", loaded, "key-internal")
    assert res["status"] == "draft"
    assert res["draft"].startswith("# DRAFT") and "requires human review" in res["draft"]
    for point in res["points"]:
        assert f"[{point['passage_id']}]" in res["draft"]
        assert loaded.get(f"/v1/passages/{point['passage_id']}", headers={"X-API-Key": "key-internal"}).status_code == 200
