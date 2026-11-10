"""SQLite store: documents, versions, passages, FTS5 (BM25) index, logs. One file, no extra service (ADR-004)."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import sqlite3
import threading
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    document_id     TEXT PRIMARY KEY,
    source_id       TEXT NOT NULL,
    external_id     TEXT NOT NULL,
    title           TEXT NOT NULL,
    office          TEXT NOT NULL,
    type            TEXT NOT NULL,
    author          TEXT,
    date            TEXT,
    project         TEXT,
    source_url      TEXT,
    access_level    TEXT NOT NULL CHECK (access_level IN ('public','internal','restricted')),
    owner           TEXT NOT NULL,
    source_piece    TEXT NOT NULL,
    validated_by    TEXT,
    synthetic       INTEGER NOT NULL DEFAULT 0,
    llm_generated   INTEGER NOT NULL DEFAULT 0,
    status          TEXT NOT NULL CHECK (status IN ('pending','approved')),
    current_version TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS document_versions (
    document_id      TEXT NOT NULL REFERENCES documents(document_id),
    document_version TEXT NOT NULL,
    media_type       TEXT NOT NULL,
    bytes            INTEGER NOT NULL,
    chunker_version  TEXT NOT NULL,
    text_chars       INTEGER NOT NULL,
    status           TEXT NOT NULL CHECK (status IN ('pending','approved','superseded')),
    ingested_at      TEXT NOT NULL,
    PRIMARY KEY (document_id, document_version)
);
CREATE TABLE IF NOT EXISTS passages (
    rowid            INTEGER PRIMARY KEY,
    passage_id       TEXT NOT NULL UNIQUE,
    document_id      TEXT NOT NULL REFERENCES documents(document_id),
    document_version TEXT NOT NULL,
    ordinal          INTEGER NOT NULL,
    text             TEXT NOT NULL,
    section          TEXT,
    page             INTEGER,
    char_start       INTEGER NOT NULL,
    char_end         INTEGER NOT NULL,
    indexed          INTEGER NOT NULL DEFAULT 0,  -- 1 = searchable (approved, current version)
    active           INTEGER NOT NULL DEFAULT 1   -- 0 = superseded version, still resolvable
);
CREATE INDEX IF NOT EXISTS ix_passages_doc ON passages(document_id, document_version);
CREATE VIRTUAL TABLE IF NOT EXISTS passages_fts USING fts5(
    section, text, tokenize = 'unicode61 remove_diacritics 2'
);
CREATE TABLE IF NOT EXISTS approval_log (
    id          INTEGER PRIMARY KEY,
    document_id TEXT NOT NULL,
    document_version TEXT NOT NULL,
    approved_by TEXT NOT NULL,
    note        TEXT,
    ts          TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS query_log (
    request_id           TEXT PRIMARY KEY,
    ts                   TEXT NOT NULL,
    principal_hash       TEXT NOT NULL,
    query                TEXT NOT NULL,
    filters_json         TEXT,
    system               TEXT NOT NULL,
    versions_json        TEXT NOT NULL,
    results_json         TEXT NOT NULL,
    insufficient_evidence INTEGER NOT NULL,
    latency_ms           REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS shadow_log (
    request_id      TEXT PRIMARY KEY,
    ts              TEXT NOT NULL,
    shown_system    TEXT NOT NULL,
    shadow_system   TEXT NOT NULL,
    shown_json      TEXT NOT NULL,
    shadow_json     TEXT NOT NULL,
    overlap_at_k    REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS feedback (
    id             INTEGER PRIMARY KEY,
    ts             TEXT NOT NULL,
    request_id     TEXT NOT NULL,
    passage_id     TEXT NOT NULL,
    judgement      TEXT NOT NULL,
    comment        TEXT,
    principal_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


class Store:
    """Thin wrapper around one SQLite connection (serialised by a lock; FastAPI runs sync routes in threads)."""

    def __init__(self, path: Path | str):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        if str(path) != ":memory:":
            self.conn.execute("PRAGMA journal_mode = WAL")
        self.conn.executescript(SCHEMA)
        self.lock = threading.RLock()

    # --- generic helpers ---------------------------------------------------------------------
    def query(self, sql: str, params: tuple | dict = ()) -> list[sqlite3.Row]:
        with self.lock:
            return self.conn.execute(sql, params).fetchall()

    def execute(self, sql: str, params: tuple | dict = ()) -> sqlite3.Cursor:
        with self.lock:
            return self.conn.execute(sql, params)

    def transaction(self):
        return _Tx(self)

    # --- meta / snapshot ---------------------------------------------------------------------
    def get_meta(self, key: str) -> str | None:
        rows = self.query("SELECT value FROM meta WHERE key = ?", (key,))
        return rows[0]["value"] if rows else None

    def set_meta(self, key: str, value: str) -> None:
        self.execute("INSERT INTO meta(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value", (key, value))

    def refresh_snapshot_id(self) -> str:
        """Content hash of the searchable index: changes whenever a passage becomes (un)searchable."""
        h = hashlib.sha256()
        for row in self.query("SELECT passage_id FROM passages WHERE indexed = 1 ORDER BY passage_id"):
            h.update(row["passage_id"].encode())
        snapshot = "idx-" + h.hexdigest()[:16]
        self.set_meta("index_snapshot_id", snapshot)
        return snapshot

    # --- logs --------------------------------------------------------------------------------
    def log_query(self, **row) -> None:
        self.execute(
            "INSERT INTO query_log VALUES (:request_id, :ts, :principal_hash, :query, :filters_json, :system,"
            " :versions_json, :results_json, :insufficient_evidence, :latency_ms)",
            {"ts": now_iso(), **row},
        )

    def log_shadow(self, **row) -> None:
        self.execute(
            "INSERT INTO shadow_log VALUES (:request_id, :ts, :shown_system, :shadow_system, :shown_json,"
            " :shadow_json, :overlap_at_k)",
            {"ts": now_iso(), **row},
        )

    def add_feedback(self, request_id: str, passage_id: str, judgement: str, comment: str | None, principal_hash: str) -> int:
        cur = self.execute(
            "INSERT INTO feedback(ts, request_id, passage_id, judgement, comment, principal_hash) VALUES (?,?,?,?,?,?)",
            (now_iso(), request_id, passage_id, judgement, comment, principal_hash),
        )
        return int(cur.lastrowid)


class _Tx:
    def __init__(self, store: Store):
        self.store = store

    def __enter__(self) -> sqlite3.Connection:
        self.store.lock.acquire()
        self.store.conn.execute("BEGIN")
        return self.store.conn

    def __exit__(self, exc_type, exc, tb) -> None:
        try:
            self.store.conn.execute("ROLLBACK" if exc_type else "COMMIT")
        finally:
            self.store.lock.release()


def dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"), default=str)
