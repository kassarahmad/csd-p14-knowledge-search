"""Ingest and approve the whole D1 corpus (D1a real acts + D1b synthetic documents).

Approval is a SIMULATED owner action: the script acts as the officer of each document's office and
records the note "simulated owner approval (scripts/ingest_corpus.py)" in approval_log.

Prerequisites: python scripts/fetch_corpus.py; python scripts/generate_d1b.py; docker compose up -d
Usage:
    python scripts/ingest_corpus.py            # idempotent: unchanged documents are skipped
"""

from __future__ import annotations

import base64
import json
import re
import sys
import time
from pathlib import Path

from p14_search.config import get_settings
from p14_search.models import AccessLevel, IngestDocument
from p14_search.security.principals import Principal
from p14_search.services import build_services

ROOT = Path(__file__).resolve().parents[1]
MEDIA = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "html": "text/html",
    "txt": "text/plain",
}
OFFICE_OWNER = {
    "hr": "Responsabile Ufficio Personale",
    "safety": "Responsabile del Servizio di Prevenzione e Protezione (RSPP)",
    "privacy": "Responsabile della protezione dei dati (DPO)",
    "it": "Responsabile per la transizione al digitale",
    "legal": "Responsabile Ufficio Affari Generali e Legali",
}
APPROVAL_NOTE = "simulated owner approval (scripts/ingest_corpus.py)"


def file_payload(path: Path) -> dict:
    ext = path.suffix[1:]
    return {"filename": path.name, "media_type": MEDIA[ext], "content_base64": base64.b64encode(path.read_bytes()).decode()}


def d1a_documents() -> list[IngestDocument]:
    record = json.loads((ROOT / "data/raw/d1a/fetch_record.json").read_text(encoding="utf-8"))
    docs = []
    for act in record["acts"]:
        topic = re.search(r"\((.*)\)", act["short"]).group(1)
        date = re.search(r"(\d{4}-\d{2}-\d{2})", act["urn"]).group(1)
        docs.append(
            IngestDocument(
                source_id="d1a",
                external_id=act["id"],
                title=f"{act['title']} - {topic}",
                file=file_payload(ROOT / act["path"]),
                metadata={"office": act["office"], "type": "legislation", "author": "Repubblica Italiana", "date": date,
                          "source_url": act["source_url"]},
                access_level=AccessLevel.public,
                owner=OFFICE_OWNER[act["office"]],
                source_piece="P14",
            )
        )
    return docs


def d1b_documents() -> list[IngestDocument]:
    record = json.loads((ROOT / "data/raw/d1b/generation_record.json").read_text(encoding="utf-8"))
    return [
        IngestDocument(
            source_id="d1b",
            external_id=d["id"],
            title=d["title"],
            file=file_payload(ROOT / d["path"]),
            metadata={"office": d["office"], "type": d["type"], "author": "Ente Demo (synthetic)", "date": d["date"],
                      "source_url": d["source_file"]},
            access_level=AccessLevel(d["access_level"]),
            owner=d["owner"],
            source_piece="P14",
            synthetic=True,
            llm_generated=True,
        )
        for d in record["documents"]
    ]


def main() -> int:
    settings = get_settings()
    t0 = time.perf_counter()
    services = build_services(settings)
    print(f"services ready in {time.perf_counter() - t0:.1f}s (embedding model: {services.embedder.name})")
    docs = d1a_documents() + d1b_documents()
    stats = {"ingested": 0, "unchanged": 0, "approved": 0, "passages": 0}
    for doc in docs:
        owner = Principal(f"simulated-owner-{doc.metadata.office}", "officer", AccessLevel.restricted, (doc.metadata.office,))
        res = services.ingestion.ingest(doc, owner)
        stats["unchanged" if res.unchanged else "ingested"] += 1
        if res.status != "approved":
            t = time.perf_counter()
            res = services.ingestion.approve(res.document_id, owner, APPROVAL_NOTE)
            stats["approved"] += 1
            print(f"approved {res.document_id:<48} {res.passages:>5} passages  {time.perf_counter() - t:5.1f}s")
        stats["passages"] += res.passages
    print(f"done: {stats} in {time.perf_counter() - t0:.1f}s; Qdrant points: {services.index.count()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
