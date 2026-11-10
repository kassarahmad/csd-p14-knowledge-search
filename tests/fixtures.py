"""Builders for small test documents (created in memory, nothing downloaded)."""

from __future__ import annotations

import io
import zipfile

from docx import Document
from fpdf import FPDF


def make_txt(text: str) -> bytes:
    return text.encode("utf-8")


def make_html(body: str) -> bytes:
    return f"<!DOCTYPE html><html><head><title>t</title><script>alert(1)</script></head><body>{body}</body></html>".encode()


def make_docx(paragraphs: list[tuple[str, str]]) -> bytes:
    """paragraphs: list of (style, text) with style 'h' (heading) or 'p'."""
    doc = Document()
    for style, text in paragraphs:
        doc.add_heading(text, level=2) if style == "h" else doc.add_paragraph(text)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def make_pdf(pages: list[str]) -> bytes:
    pdf = FPDF()
    for text in pages:
        pdf.add_page()
        pdf.set_font("Helvetica", size=11)
        pdf.multi_cell(pdf.epw, 6, text, new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())


def rewrite_docx(data: bytes, replace: dict[str, bytes] | None = None, add: dict[str, bytes] | None = None) -> bytes:
    src = zipfile.ZipFile(io.BytesIO(data))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as out:
        for item in src.infolist():
            out.writestr(item, (replace or {}).get(item.filename, src.read(item.filename)))
        for name, content in (add or {}).items():
            out.writestr(name, content)
    return buf.getvalue()
