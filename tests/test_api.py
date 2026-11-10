import base64

from conftest import ingest_payload
from fixtures import make_txt

ADMIN = {"X-API-Key": "key-admin"}
EMPLOYEE = {"X-API-Key": "key-internal"}


def search(client, query, key="key-admin", **extra):
    return client.post("/v1/search", json={"query": query, **extra}, headers={"X-API-Key": key})


def test_requests_without_valid_key_get_401_problem(loaded):
    for headers in ({}, {"X-API-Key": "wrong"}):
        r = loaded.post("/v1/search", json={"query": "orari"}, headers=headers)
        assert r.status_code == 401
        assert r.headers["content-type"] == "application/problem+json"
        assert r.json()["status"] == 401


def test_search_returns_passages_with_citations_evidence_and_versions(loaded):
    r = search(loaded, "lavoro agile giornate al mese", "key-internal")
    assert r.status_code == 200
    body = r.json()
    assert body["system"] == "S2" and body["versions"]["index_snapshot_id"].startswith("idx-")
    top = body["results"][0]
    assert top["document_id"] == "test:int-agile"
    p = top["passages"][0]
    assert p["passage_id"].startswith("p_")
    assert p["citation"]["document_version"] == top["document_version"]
    assert set(p["evidence"]["retriever_ranks"]) == {"bm25", "dense"}
    assert "confidence" not in str(body)
    assert body["insufficient_evidence"] is False
    summary = body["summary"]
    assert summary["generated"] is False
    assert all(s["passage_id"] in {q["passage_id"] for d in body["results"] for q in d["passages"]} for s in summary["sentences"])


def test_query_and_shadow_runs_are_logged(loaded, services):
    r = search(loaded, "budget formazione", "key-hr")
    rid = r.json()["request_id"]
    assert r.headers["X-Request-ID"] == rid
    log = services.store.query("SELECT * FROM query_log WHERE request_id = ?", (rid,))
    assert log and log[0]["system"] == "S2" and log[0]["principal_hash"] != "hr-officer"
    shadow = services.store.query("SELECT * FROM shadow_log WHERE request_id = ?", (rid,))
    assert shadow and shadow[0]["shadow_system"] == "B0"


def test_ingest_requires_manager_and_document_is_hidden_until_approved(client):
    payload = ingest_payload("new-doc", "internal", "hr", "Circolare", "Parola sentinella: epsilonnuovo. Orario estivo.")
    assert client.post("/v1/documents", json=payload, headers=EMPLOYEE).status_code == 403
    assert client.post("/v1/documents", json=payload, headers={"X-API-Key": "key-it"}).status_code == 403  # wrong office
    r = client.post("/v1/documents", json=payload, headers={"X-API-Key": "key-hr"})
    assert r.status_code == 202 and r.json()["status"] == "pending"

    assert search(client, "epsilonnuovo").json()["results"] == []  # pending: not searchable, even for admin
    assert client.get("/v1/documents/test:new-doc", headers=EMPLOYEE).status_code == 404
    assert client.get("/v1/documents/test:new-doc", headers={"X-API-Key": "key-hr"}).json()["status"] == "pending"

    assert client.post("/v1/documents/test:new-doc/approve", headers=EMPLOYEE).status_code == 403
    r = client.post("/v1/documents/test:new-doc/approve", json={"note": "ok"}, headers={"X-API-Key": "key-hr"})
    assert r.status_code == 200 and r.json()["status"] == "approved"
    hits = search(client, "epsilonnuovo", "key-internal").json()["results"]
    assert hits and hits[0]["document_id"] == "test:new-doc"


def test_reingest_same_content_is_unchanged(loaded):
    r = loaded.post("/v1/documents", json=ingest_payload("pub-faq", "public", "legal", "FAQ pubblica",
                    "Lo sportello pubblico apre alle nove. Parola sentinella: alfapubblico. Orari e contatti."), headers=ADMIN)
    assert r.status_code == 202 and r.json()["unchanged"] is True and r.json()["status"] == "approved"


def test_new_version_supersedes_old_but_old_passage_stays_resolvable(loaded):
    old = search(loaded, "alfapubblico", "key-public").json()["results"][0]["passages"][0]
    payload = ingest_payload("pub-faq", "public", "legal", "FAQ pubblica", "Nuova versione: lo sportello apre alle otto. Parola: zetanuova.")
    assert loaded.post("/v1/documents", json=payload, headers=ADMIN).json()["status"] == "pending"
    # until approval the old version is still the searchable one
    assert search(loaded, "alfapubblico", "key-public").json()["results"]
    loaded.post("/v1/documents/test:pub-faq/approve", headers=ADMIN)
    returned = [p for d in search(loaded, "alfapubblico", "key-public").json()["results"] for p in d["passages"]]
    assert all(p["citation"]["document_version"] != old["citation"]["document_version"] for p in returned)
    assert search(loaded, "alfapubblico", "key-public", system="x").status_code == 422  # unknown fields rejected
    assert search(loaded, "zetanuova", "key-public").json()["results"][0]["document_id"] == "test:pub-faq"
    r = loaded.get(f"/v1/passages/{old['passage_id']}", headers={"X-API-Key": "key-public"})
    assert r.status_code == 200 and r.json()["active"] is False
    doc = loaded.get("/v1/documents/test:pub-faq", headers=ADMIN).json()
    assert len(doc["versions"]) == 2 and doc["current_version"] != old["citation"]["document_version"]


def test_document_and_passage_endpoints_follow_acl(loaded):
    restricted = search(loaded, "gammahr", "key-hr").json()["results"][0]
    pid = restricted["passages"][0]["passage_id"]
    assert loaded.get(f"/v1/passages/{pid}", headers={"X-API-Key": "key-hr"}).status_code == 200
    for key in ("key-public", "key-internal", "key-it"):
        assert loaded.get(f"/v1/passages/{pid}", headers={"X-API-Key": key}).status_code == 404
        assert loaded.get("/v1/documents/test:res-budget", headers={"X-API-Key": key}).status_code == 404


def test_invalid_files_return_problem_details(client):
    payload = ingest_payload("bad", "public", "legal", "Bad", "x")
    payload["file"]["media_type"] = "application/pdf"  # declared PDF, content is text
    r = client.post("/v1/documents", json=payload, headers=ADMIN)
    assert r.status_code == 415 and r.headers["content-type"] == "application/problem+json"
    payload["file"] = {"filename": "a.txt", "media_type": "text/plain", "content_base64": "%%%not-base64"}
    assert client.post("/v1/documents", json=payload, headers=ADMIN).status_code == 422
    payload["file"]["content_base64"] = base64.b64encode(make_txt("ok")).decode()
    payload["access_level"] = "top-secret"
    assert client.post("/v1/documents", json=payload, headers=ADMIN).status_code == 422


def test_feedback(loaded, services):
    body = search(loaded, "lavoro agile", "key-internal").json()
    pid = body["results"][0]["passages"][0]["passage_id"]
    r = loaded.post("/v1/feedback", json={"request_id": body["request_id"], "passage_id": pid, "judgement": "useful"}, headers=EMPLOYEE)
    assert r.status_code == 201
    assert services.store.query("SELECT judgement FROM feedback")[0]["judgement"] == "useful"
    r = loaded.post("/v1/feedback", json={"request_id": "unknown", "passage_id": pid, "judgement": "useful"}, headers=EMPLOYEE)
    assert r.status_code == 404


def test_insufficient_evidence_threshold_from_config(loaded, services):
    services.settings.ie_min_dense = 0.99  # unreachable with the hashing embedder
    body = search(loaded, "lavoro agile").json()
    assert body["insufficient_evidence"] is True and body["summary"] is None
    services.settings.ie_min_dense = 0.0
    services.settings.display_system = "B0"  # BM25 returns nothing for a query with no matching term
    body = search(loaded, "xyzzy").json()
    assert body["system"] == "B0" and body["results"] == [] and body["insufficient_evidence"] is True
