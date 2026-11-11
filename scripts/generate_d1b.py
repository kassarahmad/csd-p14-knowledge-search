"""Render the D1b SYNTHETIC internal documents of the fictional 'Ente Demo'.

Sources: data/d1b_source/*.md (front matter + simple Markdown), written with an LLM
(synthetic, llm_generated). Output: data/raw/d1b/<id>.<pdf|docx|txt> and
data/raw/d1b/generation_record.json (metadata + SHA-256 of each rendered file).

Usage:
    python scripts/generate_d1b.py
Requires the optional "data" extra (fpdf2) and python-docx.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import io
import json
import sys
import zipfile
from pathlib import Path

import yaml
from docx import Document
from fpdf import FPDF

ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "data" / "d1b_source"
OUT_DIR = ROOT / "data" / "raw" / "d1b"
BANNER = "DOCUMENTO SINTETICO - Ente Demo è un'organizzazione fittizia (progetto universitario P14)."
FIXED_DATE = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)  # reproducible PDF metadata
REQUIRED = {"id", "title", "type", "office", "access_level", "owner", "date", "format"}


def read_source(path: Path) -> tuple[dict, list[tuple[str, str]]]:
    """Return (front matter, blocks). A block is (kind, text) with kind in h1/h2/li/p."""
    raw = path.read_text(encoding="utf-8")
    _, front, body = raw.split("---", 2)
    meta = yaml.safe_load(front)
    missing = REQUIRED - meta.keys()
    if missing:
        raise ValueError(f"{path.name}: missing front matter keys {sorted(missing)}")
    blocks = []
    for line in body.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("## "):
            blocks.append(("h2", line[3:]))
        elif line.startswith("# "):
            blocks.append(("h1", line[2:]))
        elif line.startswith("- "):
            blocks.append(("li", line[2:]))
        else:
            blocks.append(("p", line))
    return meta, blocks


def render_txt(meta: dict, blocks: list[tuple[str, str]], target: Path) -> None:
    out = [BANNER, ""]
    for kind, text in blocks:
        if kind in ("h1", "h2"):
            out += ["", text]
        elif kind == "li":
            out.append(f"- {text}")
        else:
            out.append(text)
    target.write_text("\n".join(out).strip() + "\n", encoding="utf-8")


def render_docx(meta: dict, blocks: list[tuple[str, str]], target: Path) -> None:
    doc = Document()
    props = doc.core_properties
    props.title = meta["title"]
    props.author = "Ente Demo (synthetic)"
    props.comments = "synthetic=true; llm_generated=true"
    props.created = props.modified = FIXED_DATE.replace(tzinfo=None)
    doc.add_paragraph(BANNER)
    for kind, text in blocks:
        if kind == "h1":
            doc.add_heading(text, level=1)
        elif kind == "h2":
            doc.add_heading(text, level=2)
        elif kind == "li":
            doc.add_paragraph(text, style="List Bullet")
        else:
            doc.add_paragraph(text)
    buf = io.BytesIO()
    doc.save(buf)
    # A .docx is a zip whose entries carry the current time: rewrite them with a fixed timestamp so that the same
    # source always gives the same bytes (and therefore the same document_version and passage ids).
    src = zipfile.ZipFile(buf)
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as out:
        for item in src.infolist():
            info = zipfile.ZipInfo(item.filename, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            out.writestr(info, src.read(item.filename))


def render_pdf(meta: dict, blocks: list[tuple[str, str]], target: Path) -> None:
    pdf = FPDF(format="A4")
    pdf.set_title(meta["title"])
    pdf.set_author("Ente Demo (synthetic)")
    pdf.set_subject("synthetic=true; llm_generated=true")
    pdf.set_creation_date(FIXED_DATE)
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()
    width = pdf.epw
    pdf.set_font("Helvetica", "I", 8)
    pdf.multi_cell(width, 4, BANNER, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)
    for kind, text in blocks:
        if kind == "h1":
            pdf.set_font("Helvetica", "B", 14)
            pdf.multi_cell(width, 7, text, new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)
        elif kind == "h2":
            pdf.ln(2)
            pdf.set_font("Helvetica", "B", 11)
            pdf.multi_cell(width, 6, text, new_x="LMARGIN", new_y="NEXT")
        elif kind == "li":
            pdf.set_font("Helvetica", "", 10)
            pdf.multi_cell(width, 5, f"- {text}", new_x="LMARGIN", new_y="NEXT")
        else:
            pdf.set_font("Helvetica", "", 10)
            pdf.multi_cell(width, 5, text, new_x="LMARGIN", new_y="NEXT")
            pdf.ln(1)
    pdf.output(str(target))


RENDERERS = {"txt": render_txt, "docx": render_docx, "pdf": render_pdf}


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    records = []
    for path in sorted(SRC_DIR.glob("*.md")):
        meta, blocks = read_source(path)
        target = OUT_DIR / f"{meta['id']}.{meta['format']}"
        RENDERERS[meta["format"]](meta, blocks, target)
        data = target.read_bytes()
        records.append(
            {
                **{k: str(v) for k, v in meta.items()},
                "source_file": str(path.relative_to(ROOT)).replace("\\", "/"),
                "path": str(target.relative_to(ROOT)).replace("\\", "/"),
                "synthetic": True,
                "llm_generated": True,
                "sha256": hashlib.sha256(data).hexdigest(),
                "bytes": len(data),
            }
        )
        print(f"ok  {meta['access_level']:<10} {meta['office']:<8} {target.name}")
    (OUT_DIR / "generation_record.json").write_text(
        json.dumps({"documents": records}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"{len(records)} synthetic documents -> {OUT_DIR.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
