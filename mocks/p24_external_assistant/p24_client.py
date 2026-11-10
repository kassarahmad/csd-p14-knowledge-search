"""Mock of puzzle piece P24 (information assistant for external users) consuming P14.

Contract used (docs/INTEGRATION.md): POST /v1/search with P24's API key, which P14 maps to access level
`public`. Behaviour: answer ONLY from returned passages (extractive summary + citations); escalate to a
human operator when P14 sets insufficient_evidence or returns nothing. Independent of the P14 code base:
it talks HTTP only.

Usage:
    python mocks/p24_external_assistant/p24_client.py "Quanto costano le copie per l'accesso agli atti?"
Environment: P14_URL (default http://127.0.0.1:8000), P14_KEY_P24.
"""

from __future__ import annotations

import json
import os
import sys

import httpx


def answer(question: str, http, api_key: str) -> dict:
    """`http` is any client with .post(url, json=, headers=) returning a response (httpx.Client, TestClient)."""
    r = http.post("/v1/search", json={"query": question, "top_k": 5}, headers={"X-API-Key": api_key})
    if r.status_code != 200:
        return {"status": "escalated", "reason": f"P14 error {r.status_code}", "question": question}
    body = r.json()
    # Defensive check of the contract: P24 must only ever receive public content.
    if any(d["access_level"] != "public" for d in body["results"]):
        return {"status": "escalated", "reason": "contract violation: non-public content received", "question": question}
    if body["insufficient_evidence"] or not body["results"] or not body.get("summary"):
        return {"status": "escalated", "reason": "insufficient evidence in the knowledge base", "question": question,
                "p14_request_id": body["request_id"]}
    cited = {p["passage_id"]: p["citation"] for d in body["results"] for p in d["passages"]}
    return {
        "status": "answered",
        "answer": " ".join(s["text"] for s in body["summary"]["sentences"]),
        "citations": [
            {"passage_id": s["passage_id"], "title": cited[s["passage_id"]]["title"], "section": cited[s["passage_id"]]["section"],
             "page": cited[s["passage_id"]]["page"]}
            for s in body["summary"]["sentences"]
        ],
        "p14_request_id": body["request_id"],
        "p14_versions": body["versions"],
    }


def main() -> int:
    question = " ".join(sys.argv[1:]) or "Quanto costano le copie per l'accesso agli atti?"
    with httpx.Client(base_url=os.environ.get("P14_URL", "http://127.0.0.1:8000"), timeout=30) as http:
        print(json.dumps(answer(question, http, os.environ.get("P14_KEY_P24", "demo-p24-public")), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
