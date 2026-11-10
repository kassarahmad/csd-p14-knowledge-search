"""Ingestion with human approval: documents are parsed and chunked on ingest, but become searchable only
when an owner (officer of that office, or admin) approves them. Only approval writes to the indexes."""

from __future__ import annotations

import base64
import binascii
import logging

from p14_search.indexing.embedder import Embedder
from p14_search.indexing.store import Store, now_iso
from p14_search.indexing.vector_index import VectorIndex
from p14_search.ingestion.chunker import chunk, document_id, document_version
from p14_search.ingestion.parser import ParseError, parse
from p14_search.models import IngestDocument, IngestResult
from p14_search.security.principals import Principal
from p14_search.versions import CHUNKER_VERSION

log = logging.getLogger("p14.ingestion")


class NotAllowed(PermissionError):
    pass


class NotFound(LookupError):
    pass


def embedding_text(title: str, section: str | None, text: str) -> str:
    """Context added to each passage before embedding (title and section help short passages)."""
    return "\n".join(x for x in (title, section, text) if x)


class IngestionService:
    def __init__(self, store: Store, index: VectorIndex, embedder: Embedder, max_bytes: int):
        self.store = store
        self.index = index
        self.embedder = embedder
        self.max_bytes = max_bytes

    def ingest(self, doc: IngestDocument, principal: Principal) -> IngestResult:
        if not principal.can_manage(doc.metadata.office):
            raise NotAllowed(f"principal may not ingest documents of office '{doc.metadata.office}'")
        try:
            data = base64.b64decode(doc.file.content_base64, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ParseError(f"content_base64 is not valid base64: {exc}") from exc
        blocks = parse(data, doc.file.media_type, self.max_bytes)
        did, ver = document_id(doc.source_id, doc.external_id), document_version(data)

        existing = self.store.query(
            "SELECT status FROM document_versions WHERE document_id = ? AND document_version = ?", (did, ver)
        )
        if existing:
            n = self.store.query("SELECT COUNT(*) AS n FROM passages WHERE document_id = ? AND document_version = ?", (did, ver))[0]["n"]
            status = "approved" if existing[0]["status"] == "approved" else "pending"
            return IngestResult(document_id=did, document_version=ver, status=status, passages=n, unchanged=True)

        text, chunks = chunk(blocks, did, ver)
        m = doc.metadata
        ts = now_iso()
        with self.store.transaction() as conn:
            conn.execute(
                """INSERT INTO documents (document_id, source_id, external_id, title, office, type, author, date, project,
                       source_url, access_level, owner, source_piece, validated_by, synthetic, llm_generated, status,
                       current_version, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?, 'pending', ?, ?, ?)
                   ON CONFLICT(document_id) DO UPDATE SET title=excluded.title, office=excluded.office, type=excluded.type,
                       author=excluded.author, date=excluded.date, project=excluded.project, source_url=excluded.source_url,
                       access_level=excluded.access_level, owner=excluded.owner, source_piece=excluded.source_piece,
                       validated_by=excluded.validated_by, synthetic=excluded.synthetic, llm_generated=excluded.llm_generated,
                       status='pending', current_version=excluded.current_version, updated_at=excluded.updated_at""",
                (did, doc.source_id, doc.external_id, doc.title, m.office, m.type, m.author, m.date, m.project, m.source_url,
                 doc.access_level.value, doc.owner, doc.source_piece, doc.validated_by, int(doc.synthetic),
                 int(doc.llm_generated), ver, ts, ts),
            )
            conn.execute(
                "INSERT INTO document_versions VALUES (?,?,?,?,?,?, 'pending', ?)",
                (did, ver, doc.file.media_type, len(data), CHUNKER_VERSION, len(text), ts),
            )
            conn.executemany(
                """INSERT INTO passages (passage_id, document_id, document_version, ordinal, text, section, page,
                       char_start, char_end, indexed, active) VALUES (?,?,?,?,?,?,?,?,?,0,1)""",
                [(c.passage_id, did, ver, c.ordinal, c.text, c.section, c.page, c.char_start, c.char_end) for c in chunks],
            )
        log.info("ingested", extra={"document_id": did, "document_version": ver[:12], "passages": len(chunks), "by": principal.pseudonym})
        return IngestResult(document_id=did, document_version=ver, status="pending", passages=len(chunks))

    def approve(self, did: str, principal: Principal, note: str | None = None) -> IngestResult:
        rows = self.store.query("SELECT * FROM documents WHERE document_id = ?", (did,))
        if not rows:
            raise NotFound(did)
        doc = rows[0]
        if not principal.can_manage(doc["office"]):
            raise NotAllowed(f"principal may not approve documents of office '{doc['office']}'")
        ver = doc["current_version"]
        passages = self.store.query(
            "SELECT rowid, passage_id, text, section FROM passages WHERE document_id = ? AND document_version = ? ORDER BY ordinal",
            (did, ver),
        )
        if doc["status"] == "approved":
            return IngestResult(document_id=did, document_version=ver, status="approved", passages=len(passages), unchanged=True)

        # 1) dense index first: if SQLite then fails, stray vectors are ignored because search only returns
        #    passages marked indexed=1 in SQLite.
        vectors = self.embedder.embed_passages([embedding_text(doc["title"], p["section"], p["text"]) for p in passages])
        payload = {k: doc[k] for k in ("document_id", "access_level", "office", "type", "source_id")}
        self.index.upsert([{"passage_id": p["passage_id"], **payload} for p in passages], vectors)
        old = self.store.query(
            "SELECT rowid, passage_id FROM passages WHERE document_id = ? AND document_version != ? AND indexed = 1", (did, ver)
        )
        self.index.delete([o["passage_id"] for o in old])

        # 2) BM25 index and state, atomically.
        with self.store.transaction() as conn:
            for o in old:
                conn.execute("DELETE FROM passages_fts WHERE rowid = ?", (o["rowid"],))
            conn.execute("UPDATE passages SET indexed = 0, active = 0 WHERE document_id = ? AND document_version != ?", (did, ver))
            conn.execute("UPDATE document_versions SET status = 'superseded' WHERE document_id = ? AND document_version != ?", (did, ver))
            conn.executemany(
                "INSERT INTO passages_fts(rowid, section, text) VALUES (?,?,?)",
                [(p["rowid"], p["section"] or "", p["text"]) for p in passages],
            )
            conn.execute("UPDATE passages SET indexed = 1 WHERE document_id = ? AND document_version = ?", (did, ver))
            conn.execute("UPDATE document_versions SET status = 'approved' WHERE document_id = ? AND document_version = ?", (did, ver))
            conn.execute("UPDATE documents SET status = 'approved', updated_at = ? WHERE document_id = ?", (now_iso(), did))
            conn.execute(
                "INSERT INTO approval_log(document_id, document_version, approved_by, note, ts) VALUES (?,?,?,?,?)",
                (did, ver, principal.pseudonym, note, now_iso()),
            )
        self.store.refresh_snapshot_id()
        log.info("approved", extra={"document_id": did, "passages": len(passages), "by": principal.pseudonym, "note": note})
        return IngestResult(document_id=did, document_version=ver, status="approved", passages=len(passages))
