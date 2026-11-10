"""Mock of puzzle piece P12 (assisted document generation) consuming P14.

Contract used (docs/INTEGRATION.md): POST /v1/search to retrieve trusted passages, then
GET /v1/passages/{passage_id} to re-resolve every cited passage before it goes into a draft.
Behaviour: builds a DRAFT in which every statement is copied from a passage and cites its passage_id, so a
reviewer can verify each sentence; the draft is never final. Independent of the P14 code base (HTTP only).

Usage:
    python mocks/p12_document_generation/p12_client.py "lavoro agile disconnessione"
Environment: P14_URL (default http://127.0.0.1:8000), P14_KEY_P12.
"""

from __future__ import annotations

import os
import sys

import httpx


def build_draft(topic: str, http, api_key: str, max_points: int = 4) -> dict:
    headers = {"X-API-Key": api_key}
    r = http.post("/v1/search", json={"query": topic, "top_k": 8}, headers=headers)
    r.raise_for_status()
    body = r.json()
    if body["insufficient_evidence"] or not body["results"]:
        return {"status": "no_sources", "topic": topic, "draft": None, "p14_request_id": body["request_id"]}
    points = []
    for doc in body["results"]:
        p = doc["passages"][0]
        # Re-resolve the passage by id: the citation must be verifiable later, even after re-indexing.
        resolved = http.get(f"/v1/passages/{p['passage_id']}", headers=headers)
        if resolved.status_code != 200:
            continue
        info = resolved.json()
        sentence = info["text"].split(". ")[0].strip().rstrip(".") + "."
        where = ", ".join(x for x in (info["citation"]["section"], f"p. {info['citation']['page']}" if info["citation"]["page"] else None) if x)
        points.append({"text": sentence, "passage_id": info["passage_id"], "source": f"{info['citation']['title']} ({where})"})
        if len(points) == max_points:
            break
    lines = [f"# DRAFT - {topic}", "", "Status: draft generated from P14 sources; requires human review before use.", ""]
    lines += [f"- {pt['text']} [{pt['passage_id']}]" for pt in points]
    lines += ["", "## Sources"] + [f"- [{pt['passage_id']}] {pt['source']}" for pt in points]
    return {"status": "draft", "topic": topic, "draft": "\n".join(lines), "points": points, "p14_request_id": body["request_id"]}


def main() -> int:
    topic = " ".join(sys.argv[1:]) or "lavoro agile disconnessione"
    with httpx.Client(base_url=os.environ.get("P14_URL", "http://127.0.0.1:8000"), timeout=30) as http:
        result = build_draft(topic, http, os.environ.get("P14_KEY_P12", "demo-p12-generation"))
    print(result["draft"] or f"No sources found for: {topic}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
