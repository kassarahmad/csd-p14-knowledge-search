"""Download the D1a corpus (real Italian official acts) listed in data/d1a_manifest.json.

Sources:
- Normattiva (www.normattiva.it): consolidated text, "esporta atto completo" HTML export.
- Gazzetta Ufficiale (www.gazzettaufficiale.it): PDF of the issue in which the act was published.

Official acts of the State are excluded from copyright (art. 5, L. 633/1941). See docs/DATA.md.

Usage:
    python scripts/fetch_corpus.py            # download missing files only
    python scripts/fetch_corpus.py --force    # re-download everything

Output: data/raw/d1a/<id>.<html|txt|pdf> and data/raw/d1a/fetch_record.json
(source URLs, SHA-256, fetch date). Uses only the Python standard library.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import http.cookiejar
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data" / "d1a_manifest.json"
OUT_DIR = ROOT / "data" / "raw" / "d1a"
NORMATTIVA = "https://www.normattiva.it"
USER_AGENT = "p14-knowledge-search/0.1 (university project, UNICAM; polite crawler)"
DELAY_S = 1.5


def make_opener() -> urllib.request.OpenerDirector:
    # Normattiva keeps the selected act in the session: a fresh cookie jar per act.
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    opener.addheaders = [("User-Agent", USER_AGENT)]
    return opener


def get(opener: urllib.request.OpenerDirector, url: str) -> bytes:
    with opener.open(url, timeout=120) as resp:
        return resp.read()


def html_to_text(page: str) -> str:
    """Plain-text rendition of a Normattiva export, keeping article headings on their own lines."""
    m = re.search(r'<div class="container ContentHtmlExp">(.*)', page, flags=re.S)
    body = m.group(1) if m else page
    body = re.sub(r"<(script|style)\b.*?</\1>", "", body, flags=re.S | re.I)
    body = re.sub(r"<br\s*/?>", "\n", body, flags=re.I)
    body = re.sub(r"</(p|div|h\d|li|tr)>", "\n", body, flags=re.I)
    body = re.sub(r"<h\d[^>]*>", "\n\n", body, flags=re.I)
    text = html.unescape(re.sub(r"<[^>]+>", "", body))
    lines = [re.sub(r"[ \t\xa0]+", " ", ln).strip() for ln in text.splitlines()]
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text + "\n"


def fetch_act(act: dict, force: bool) -> dict:
    target = OUT_DIR / f"{act['id']}.{act['format']}"
    record = {**act, "path": str(target.relative_to(ROOT)).replace("\\", "/")}
    if target.exists() and not force:
        record["skipped"] = True
        return record

    opener = make_opener()
    urn_url = f"{NORMATTIVA}/uri-res/N2Ls?{act['urn']}"
    page = get(opener, urn_url).decode("utf-8", errors="replace")
    title = re.search(r"<title>\s*(.*?)\s*-\s*Normattiva", page, flags=re.S)
    if not title:
        raise RuntimeError(f"{act['id']}: URN did not resolve to an act page")
    record["title"] = html.unescape(re.sub(r"\s+", " ", title.group(1)))
    record["urn_url"] = urn_url

    if act["format"] == "pdf":
        gu = re.search(r'href="(https://www\.gazzettaufficiale\.it/eli/gu/[^"]+/pdf)"', page)
        if not gu:
            raise RuntimeError(f"{act['id']}: no Gazzetta Ufficiale PDF link found")
        time.sleep(DELAY_S)
        data = get(opener, gu.group(1))
        if not data.startswith(b"%PDF"):
            raise RuntimeError(f"{act['id']}: Gazzetta Ufficiale did not return a PDF")
        record["source_url"] = gu.group(1)
        record["source"] = "Gazzetta Ufficiale della Repubblica Italiana (issue as published)"
    else:
        exp = re.search(r'href="(/esporta/attoCompleto\?[^"]+)"', page)
        if not exp:
            raise RuntimeError(f"{act['id']}: no 'esporta atto completo' link found")
        export_url = NORMATTIVA + html.unescape(exp.group(1))
        time.sleep(DELAY_S)
        raw = get(opener, export_url)
        record["source_url"] = export_url
        record["source"] = "Normattiva (consolidated text in force on the fetch date)"
        if act["format"] == "txt":
            data = html_to_text(raw.decode("utf-8", errors="replace")).encode("utf-8")
            record["derived"] = "plain text produced by scripts/fetch_corpus.py:html_to_text from the HTML export"
        else:
            data = raw

    target.write_bytes(data)
    record["sha256"] = hashlib.sha256(data).hexdigest()
    record["bytes"] = len(data)
    record["fetched_at"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    return record


D2_URL = "https://public.ukp.informatik.tu-darmstadt.de/thakur/BEIR/datasets/scifact.zip"
D2_DIR = ROOT / "data" / "raw" / "d2"


def fetch_d2(force: bool) -> None:
    """D2 sanity benchmark: BEIR SciFact (claims CC BY 4.0, abstracts ODC-By 1.0)."""
    import zipfile

    zip_path = D2_DIR / "scifact.zip"
    D2_DIR.mkdir(parents=True, exist_ok=True)
    if not zip_path.exists() or force:
        zip_path.write_bytes(get(make_opener(), D2_URL))
    digest = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.namelist():  # refuse path traversal before extracting
            dest = (D2_DIR / member).resolve()
            if not str(dest).startswith(str(D2_DIR.resolve())):
                raise RuntimeError(f"unsafe path in zip: {member}")
        zf.extractall(D2_DIR)
    (D2_DIR / "fetch_record.json").write_text(
        json.dumps({"url": D2_URL, "sha256": digest, "licence": "claims CC BY 4.0; abstracts ODC-By 1.0"}, indent=2),
        encoding="utf-8",
    )
    print(f"ok   d2 scifact  sha256={digest[:12]}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--force", action="store_true", help="re-download existing files")
    parser.add_argument("--skip-d2", action="store_true", help="do not download the D2 benchmark")
    args = parser.parse_args()

    if not args.skip_d2:
        fetch_d2(args.force)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    record_path = OUT_DIR / "fetch_record.json"
    previous = {}
    if record_path.exists():
        previous = {r["id"]: r for r in json.loads(record_path.read_text(encoding="utf-8"))["acts"]}

    acts = json.loads(MANIFEST.read_text(encoding="utf-8"))["acts"]
    records, failures = [], []
    for act in acts:
        try:
            rec = fetch_act(act, args.force)
        except Exception as exc:  # report and continue with the other acts
            failures.append(f"{act['id']}: {exc}")
            print(f"FAIL {act['id']}: {exc}", file=sys.stderr)
            continue
        if rec.pop("skipped", False):
            rec = previous.get(act["id"], rec)
            print(f"skip {act['id']} (exists)")
        else:
            print(f"ok   {act['id']}  {rec['bytes']:>9} B  {rec['title'][:70]}")
            time.sleep(DELAY_S)
        records.append(rec)

    record_path.write_text(
        json.dumps({"acts": records, "failures": failures}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"{len(records)} acts recorded, {len(failures)} failures -> {record_path.relative_to(ROOT)}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
