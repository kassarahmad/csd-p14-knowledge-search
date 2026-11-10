"""ACL leakage test (target T5: leakage = 0).

For every principal, every system and a set of queries designed to hit every access level, no returned
passage may come from a document the principal is not allowed to see. The expected visibility is written
out explicitly here (an oracle independent of p14_search.security.acl).
Checked twice: on the raw retriever output (proves the filter is applied INSIDE retrieval) and on the API.
"""

import pytest

from conftest import CORPUS, PRINCIPALS

VISIBLE = {
    "key-public": {"pub-faq"},
    "key-internal": {"pub-faq", "int-agile"},
    "key-hr": {"pub-faq", "int-agile", "res-budget"},
    "key-it": {"pub-faq", "int-agile", "res-incident"},
    "key-admin": {"pub-faq", "int-agile", "res-budget", "res-incident"},
}
QUERIES = ["alfapubblico", "betainterno", "gammahr", "deltait", "riservata formazione budget sala crisi",
           "lavoro agile", "orari sportello", "incidenti informatici riservati stanza"]
SYSTEMS = ("B0", "S1", "S2")


def test_oracle_covers_all_principals():
    assert set(VISIBLE) == set(PRINCIPALS)


@pytest.mark.parametrize("key", list(PRINCIPALS))
def test_no_leakage_inside_retrievers(loaded, services, key):
    principal = PRINCIPALS[key]
    doc_of = {r["passage_id"]: r["document_id"].split(":")[1] for r in services.store.query("SELECT passage_id, document_id FROM passages")}
    leaks = []
    for q in QUERIES:
        rankings = services.search.rank_all(q, principal, 50, SYSTEMS)
        for system, ranking in rankings.items():
            leaks += [(q, system, doc_of[h.passage_id]) for h in ranking.hits if doc_of[h.passage_id] not in VISIBLE[key]]
    assert leaks == []


@pytest.mark.parametrize("key", list(PRINCIPALS))
def test_no_leakage_through_api(loaded, key):
    seen = set()
    for q in QUERIES:
        body = loaded.post("/v1/search", json={"query": q, "top_k": 50}, headers={"X-API-Key": key}).json()
        seen |= {d["document_id"].split(":")[1] for d in body["results"]}
    assert seen <= VISIBLE[key]
    assert seen == VISIBLE[key], "every visible document should be reachable by its sentinel query"


def test_corpus_has_every_access_level():
    assert {c[1] for c in CORPUS} == {"public", "internal", "restricted"}
