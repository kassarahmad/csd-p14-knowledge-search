"""Derive passage-level graded qrels from the annotated targets (docs/ANNOTATION_PROTOCOL.md section 2).

Usage:
    python eval/build_qrels.py   -> eval/qrels/d1_qrels.json
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from p14_search.config import get_settings
from p14_search.indexing.store import Store

ROOT = Path(__file__).resolve().parents[1]
QUERIES = ROOT / "eval" / "queries" / "d1_queries.jsonl"
OUT = ROOT / "eval" / "qrels" / "d1_qrels.json"


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("’", "'")).strip().lower()


def load_queries(path: Path = QUERIES) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def same_section(section: str, target: str) -> bool:
    """'Art. 18 - Lavoro agile' matches target 'Art. 18' but 'Art. 18-bis' does not."""
    return section == target or section.startswith((target + " ", target + "."))


def build(store: Store, queries: list[dict]) -> tuple[dict, list[str]]:
    passages = store.query("SELECT passage_id, document_id, section, page, text FROM passages WHERE indexed = 1")
    normed = [(p["passage_id"], p["document_id"], p["section"] or "", p["page"], norm(p["text"])) for p in passages]
    qrels, errors = {}, []
    for q in queries:
        grades: dict[str, int] = {}
        for t in q["targets"]:
            snippet = norm(t["snippet"])
            hits = [(pid, did, page) for pid, did, _, page, text in normed if snippet in text]
            if not hits:
                errors.append(f"{q['qid']}: snippet not found: {t['snippet'][:60]!r}")
            for pid, _, _ in hits:
                grades[pid] = 2
            # In a Gazzetta Ufficiale issue several acts have an 'Art. 1': for paginated documents, grade 1 is
            # limited to pages next to the snippet.
            pages = [page for _, did, page in hits if did == t["document_id"] and page is not None]
            for pid, did, section, page, _ in normed:
                if did != t["document_id"] or not t.get("section") or not same_section(section, t["section"]):
                    continue
                if pages and page is not None and not (min(pages) - 1 <= page <= max(pages) + 1):
                    continue
                grades.setdefault(pid, 1)
        qrels[q["qid"]] = grades
    return qrels, errors


def main() -> int:
    store = Store(get_settings().sqlite_path)
    queries = load_queries()
    qrels, errors = build(store, queries)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"index_snapshot_id": store.get_meta("index_snapshot_id"), "qrels": qrels}, indent=1) + "\n",
                   encoding="utf-8", newline="\n")
    in_scope = [q for q in queries if q["type"] != "out_of_scope"]
    print(f"{len(queries)} queries ({len(in_scope)} in scope); "
          f"mean relevant passages per in-scope query: {sum(len(qrels[q['qid']]) for q in in_scope) / max(len(in_scope), 1):.1f}")
    for e in errors:
        print("ERROR", e)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
