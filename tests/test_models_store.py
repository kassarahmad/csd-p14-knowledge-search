import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from p14_search.contracts import CONTRACT_MODELS, schema_for
from p14_search.indexing.store import Store
from p14_search.models import IngestDocument

ROOT = Path(__file__).resolve().parents[1]


def _ingest_payload(**over):
    payload = {
        "source_id": "d1b",
        "external_id": "doc-1",
        "title": "Test",
        "file": {"filename": "a.txt", "media_type": "text/plain", "content_base64": "Y2lhbw=="},
        "metadata": {"office": "hr", "type": "faq"},
        "access_level": "internal",
        "owner": "Responsabile Ufficio Personale",
    }
    payload.update(over)
    return payload


def test_ingest_document_requires_access_level_and_owner():
    IngestDocument.model_validate(_ingest_payload())
    for missing in ("access_level", "owner"):
        bad = _ingest_payload()
        del bad[missing]
        with pytest.raises(ValidationError):
            IngestDocument.model_validate(bad)
    with pytest.raises(ValidationError):
        IngestDocument.model_validate(_ingest_payload(access_level="secret"))
    with pytest.raises(ValidationError):  # unknown fields are rejected
        IngestDocument.model_validate(_ingest_payload(extra_field=1))


@pytest.mark.parametrize("name", list(CONTRACT_MODELS))
def test_frozen_schema_matches_code(name):
    frozen = json.loads((ROOT / "contracts" / "schemas" / f"{name}.json").read_text(encoding="utf-8"))
    assert frozen == schema_for(name), f"{name} drifted from contracts/schemas - re-freeze only if intended"


def test_store_schema_and_fts5():
    store = Store(":memory:")
    tables = {r["name"] for r in store.query("SELECT name FROM sqlite_master WHERE type IN ('table')")}
    assert {"documents", "document_versions", "passages", "passages_fts", "query_log", "shadow_log", "feedback"} <= tables
    store.execute("INSERT INTO passages_fts(rowid, section, text) VALUES (1, 'Art. 18', 'Il lavoro agile è una modalità')")
    hits = store.query("SELECT rowid, bm25(passages_fts) AS s FROM passages_fts WHERE passages_fts MATCH ?", ('"modalita"',))
    assert [h["rowid"] for h in hits] == [1]  # remove_diacritics: 'modalita' matches 'modalità'
