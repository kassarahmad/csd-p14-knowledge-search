"""Chunking into passages with persistent identifiers.

Ids:
- document_id      = "<source_id>:<external_id>" (stable, independent of content)
- document_version = SHA-256 of the original file bytes
- passage_id       = "p_" + SHA-256(document_id | document_version | chunker_version | char_start)[:32]
So unchanged content re-ingested with the same chunker keeps the same ids.

Rules (CHUNKER_VERSION): a passage never crosses a section or a page boundary; blocks are packed up to
TARGET_CHARS; longer blocks are split on sentence boundaries with OVERLAP_CHARS of overlap.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from p14_search.ingestion.parser import Block
from p14_search.versions import CHUNKER_VERSION

TARGET_CHARS = 1000
OVERLAP_CHARS = 150
SEPARATOR = "\n\n"
_SENTENCE_END = re.compile(r"(?<=[.;:!?])\s+")


@dataclass
class Chunk:
    passage_id: str
    ordinal: int
    text: str
    section: str | None
    page: int | None
    char_start: int
    char_end: int


def document_id(source_id: str, external_id: str) -> str:
    return f"{source_id}:{external_id}"


def document_version(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def passage_id(doc_id: str, doc_version: str, char_start: int, chunker_version: str = CHUNKER_VERSION) -> str:
    raw = f"{doc_id}|{doc_version}|{chunker_version}|{char_start}".encode()
    return "p_" + hashlib.sha256(raw).hexdigest()[:32]


def full_text(blocks: list[Block]) -> tuple[str, list[int]]:
    """Concatenate blocks; returns the text and the start offset of each block (citation offsets)."""
    starts, parts, pos = [], [], 0
    for b in blocks:
        starts.append(pos)
        parts.append(b.text)
        pos += len(b.text) + len(SEPARATOR)
    return SEPARATOR.join(parts), starts


def _split_long(text: str, start: int) -> list[tuple[int, int]]:
    """Windows of ~TARGET_CHARS over one long block, cut at sentence ends, with overlap. Offsets relative to the doc."""
    spans = []
    pos = 0
    n = len(text)
    while pos < n:
        end = min(pos + TARGET_CHARS, n)
        if end < n:
            cut = [m.end() for m in _SENTENCE_END.finditer(text, pos + TARGET_CHARS // 2, end)]
            if cut:
                end = cut[-1]
            else:
                space = text.rfind(" ", pos + TARGET_CHARS // 2, end)
                end = space if space > pos else end
        spans.append((start + pos, start + end))
        if end >= n:
            break
        nxt = max(end - OVERLAP_CHARS, pos + 1)
        space = text.find(" ", nxt, end)
        pos = space + 1 if space != -1 else nxt
    return spans


def chunk(blocks: list[Block], doc_id: str, doc_version: str) -> tuple[str, list[Chunk]]:
    text, starts = full_text(blocks)
    spans: list[tuple[int, int, Block]] = []
    group: list[int] = []

    def flush_group():
        if group:
            first, last = group[0], group[-1]
            spans.append((starts[first], starts[last] + len(blocks[last].text), blocks[first]))
            group.clear()

    for i, b in enumerate(blocks):
        if len(b.text) > TARGET_CHARS:
            flush_group()
            for s, e in _split_long(b.text, starts[i]):
                spans.append((s, e, b))
            continue
        if group:
            g0 = blocks[group[0]]
            size = starts[i] + len(b.text) - starts[group[0]]
            if b.section != g0.section or b.page != g0.page or size > TARGET_CHARS:
                flush_group()
        group.append(i)
    flush_group()

    chunks = [
        Chunk(
            passage_id=passage_id(doc_id, doc_version, s),
            ordinal=n,
            text=text[s:e].strip(),
            section=b.section,
            page=b.page,
            char_start=s,
            char_end=e,
        )
        for n, (s, e, b) in enumerate(spans)
    ]
    return text, [c for c in chunks if c.text]
