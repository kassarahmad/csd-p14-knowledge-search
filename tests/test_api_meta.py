from fastapi.testclient import TestClient

from p14_search.api.app import create_app
from p14_search.config import Settings


def test_health_and_version(client):
    health = client.get("/v1/health")
    assert health.status_code == 200
    assert health.json() == {"status": "ok", "components": {"sqlite": "ok", "qdrant": "ok"}}
    assert health.headers["X-Request-ID"]

    version = client.get("/v1/version").json()
    assert version["pipeline_version"] == "0.1.0"
    assert version["chunker_version"]
    assert version["embedding_model"] == "test/hashing-256"


def test_health_without_services_is_degraded():
    client = TestClient(create_app(Settings(_env_file=None), init_services=False))
    assert client.get("/v1/health").json()["status"] == "degraded"
    r = client.get("/v1/version")
    assert r.status_code == 503 and r.headers["content-type"] == "application/problem+json"
