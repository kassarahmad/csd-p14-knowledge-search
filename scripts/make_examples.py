"""Produce the REAL contract examples (deliverable 6) by calling the running API.

Usage (API running: uvicorn p14_search.main:app --port 8000):
    python scripts/make_examples.py
Writes contracts/examples/{IngestDocument,IngestResult,SearchResponse,Problem}.real.json
"""

from __future__ import annotations

import base64
import json
import os
import sys
from pathlib import Path

import httpx
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "contracts" / "examples"
QUERY = "Quanti giorni al mese posso lavorare da casa?"


def save(name: str, data: dict) -> None:
    (OUT / f"{name}.real.json").write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print("wrote", f"contracts/examples/{name}.real.json")


def main() -> int:
    env = {**dotenv_values(ROOT / ".env"), **os.environ}
    OUT.mkdir(parents=True, exist_ok=True)
    gen = {d["id"]: d for d in json.loads((ROOT / "data/raw/d1b/generation_record.json").read_text(encoding="utf-8"))["documents"]}
    d = gen["faq-lavoro-agile"]
    ingest = {
        "source_id": "d1b", "external_id": d["id"], "title": d["title"],
        "file": {"filename": Path(d["path"]).name, "media_type": "text/plain",
                 "content_base64": base64.b64encode((ROOT / d["path"]).read_bytes()).decode()},
        "metadata": {"office": d["office"], "type": d["type"], "author": "Ente Demo (synthetic)", "date": d["date"],
                     "source_url": d["source_file"]},
        "access_level": d["access_level"], "owner": d["owner"], "source_piece": "P14", "synthetic": True, "llm_generated": True,
    }
    with httpx.Client(base_url=env.get("P14_URL", "http://127.0.0.1:8000"), timeout=60) as c:
        r = c.post("/v1/documents", json=ingest, headers={"X-API-Key": env["P14_KEY_HR"]})
        r.raise_for_status()
        save("IngestDocument", ingest)
        save("IngestResult", r.json())
        r = c.post("/v1/search", json={"query": QUERY, "top_k": 5}, headers={"X-API-Key": env["P14_KEY_EMPLOYEE"]})
        r.raise_for_status()
        save("SearchResponse", r.json())
        r = c.get("/v1/documents/d1b:budget-formazione-2026", headers={"X-API-Key": env["P14_KEY_EMPLOYEE"]})
        assert r.status_code == 404
        save("Problem", r.json())
    return 0


if __name__ == "__main__":
    sys.exit(main())
