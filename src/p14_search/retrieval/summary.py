"""Extractive summary: sentences copied verbatim from the top passages, each linked to its passage_id.
Nothing is generated, so the summary cannot contain statements absent from the sources."""

from __future__ import annotations

import math
import re

from p14_search.models import Summary, SummarySentence
from p14_search.retrieval.retrievers import STOPWORDS

_SENT_SPLIT = re.compile(r"(?<=[.;!?])\s+(?=[A-ZÀ-Ü0-9(])")
MAX_SENTENCES = 3
TOP_PASSAGES = 3


def _terms(text: str) -> set[str]:
    return {t for t in re.findall(r"\w+", text.lower()) if t not in STOPWORDS and len(t) > 2}


def extractive_summary(query: str, passages: list[tuple[str, str]]) -> Summary | None:
    """passages: (passage_id, text) in rank order."""
    q = _terms(query)
    if not q:
        return None
    candidates = []
    for rank, (pid, text) in enumerate(passages[:TOP_PASSAGES]):
        for pos, sent in enumerate(_SENT_SPLIT.split(text)):
            sent = sent.strip()
            terms = _terms(sent)
            if len(sent) < 30 or not terms:
                continue
            overlap = len(q & terms)
            if overlap:
                # Query-term overlap, normalised by sentence length, mildly favouring higher-ranked passages.
                score = overlap / math.sqrt(len(terms)) / (1 + 0.2 * rank)
                candidates.append((score, rank, pos, pid, sent))
    if not candidates:
        return None
    best = sorted(candidates, key=lambda c: -c[0])[:MAX_SENTENCES]
    best.sort(key=lambda c: (c[1], c[2]))  # present in source order
    return Summary(sentences=[SummarySentence(text=s, passage_id=pid) for _, _, _, pid, s in best])
