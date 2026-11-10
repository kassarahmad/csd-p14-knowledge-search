"""Collect evidence that the system runs on this machine -> docs/evidence/

- screenshots of the demo UI (Playwright driving the locally installed Microsoft Edge) and of the API docs;
- raw outputs of the API (health, version, searches with different principals), of the two mock consumers,
  of pytest and of the environment (GPU, Docker).
Read-only: no document is ingested and no feedback is sent.

Usage (API on :8000 and demo on :8501 running):
    python scripts/capture_evidence.py [--api http://127.0.0.1:8000] [--ui http://127.0.0.1:8501]
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path

import httpx
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "evidence"
PY = sys.executable


def run(cmd: list[str], timeout: int = 600) -> str:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, env=env)
    return f"$ {' '.join(cmd)}\n{p.stdout}{p.stderr}"


def write(name: str, text: str) -> None:
    (OUT / name).write_text(text, encoding="utf-8", newline="\n")
    print("wrote docs/evidence/" + name)


def api_evidence(api: str, keys: dict[str, str]) -> None:
    lines = [f"Captured {dt.datetime.now().isoformat(timespec='seconds')} against {api}", ""]
    with httpx.Client(base_url=api, timeout=60) as c:
        lines += ["GET /v1/health", json.dumps(c.get("/v1/health").json(), indent=2), ""]
        lines += ["GET /v1/version", json.dumps(c.get("/v1/version").json(), indent=2), ""]
        cases = [
            ("employee", "Quanti giorni al mese posso lavorare da casa?"),
            ("employee", "budget formazione 2026"),
            ("hr-officer", "budget formazione 2026"),
            ("p24-external-assistant", "budget formazione 2026"),
            ("employee", "Qual è il menu della mensa aziendale?"),
            ("employee", "Can I work remotely from another country?"),
        ]
        for principal, q in cases:
            r = c.post("/v1/search", json={"query": q, "top_k": 5}, headers={"X-API-Key": keys[principal]})
            b = r.json()
            lines.append(f"POST /v1/search  principal={principal}  query={q!r}  -> HTTP {r.status_code}, request_id={b['request_id']}")
            lines.append(f"  insufficient_evidence={b['insufficient_evidence']}  system={b['system']}  snapshot={b['versions']['index_snapshot_id']}")
            for d in b["results"]:
                p = d["passages"][0]
                cit = p["citation"]
                lines.append(f"  #{d['best_rank']} [{d['access_level']:<10}] {d['document_id']:<45} {cit['section'] or ''!s:.40}  page={cit['page']}  passage={p['passage_id']}")
            lines.append("")
        r = c.get("/v1/documents/d1b:budget-formazione-2026", headers={"X-API-Key": keys["employee"]})
        lines += ["GET /v1/documents/d1b:budget-formazione-2026 as employee", f"HTTP {r.status_code} {r.headers['content-type']}", json.dumps(r.json(), indent=2), ""]
        r = c.post("/v1/search", json={"query": "test"})
        lines += ["POST /v1/search without X-API-Key", f"HTTP {r.status_code} {r.headers['content-type']}", json.dumps(r.json(), indent=2)]
    write("api_session.txt", "\n".join(lines) + "\n")


def screenshots(api: str, ui: str) -> None:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="msedge", headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000}, device_scale_factor=1)

        def search(principal: str, query: str, shot: str) -> None:
            page.goto(ui, wait_until="networkidle")
            page.get_by_text("Ask a question").wait_for(timeout=60000)
            if principal != "employee":
                page.locator('[data-testid="stSelectbox"] input').first.click()
                page.get_by_role("option", name=principal, exact=True).click()
                page.wait_for_timeout(1500)
            box = page.get_by_label("Ask a question")
            box.fill(query)
            box.press("Enter")
            page.get_by_test_id("stBaseButton-primary").click()
            page.locator('[data-testid="stExpander"]').first.wait_for(timeout=60000)
            page.wait_for_timeout(1500)
            page.screenshot(path=str(OUT / shot), full_page=False)
            print("wrote docs/evidence/" + shot)

        search("employee", "Quanti giorni al mese posso lavorare da casa?", "ui_01_search_employee.png")
        search("employee", "budget formazione 2026", "ui_02_acl_employee.png")
        search("hr-officer", "budget formazione 2026", "ui_03_acl_hr_officer.png")
        search("employee", "Qual è il menu della mensa aziendale?", "ui_04_insufficient_evidence.png")
        search("employee", "Can I work remotely from another country?", "ui_05_english_query.png")
        page.goto(f"{api}/docs", wait_until="networkidle")
        page.wait_for_timeout(2000)
        page.screenshot(path=str(OUT / "api_docs_swagger.png"))
        print("wrote docs/evidence/api_docs_swagger.png")
        browser.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    parser.add_argument("--ui", default="http://127.0.0.1:8501")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    env = {**dotenv_values(ROOT / ".env"), **os.environ}
    cfg = json.loads((ROOT / "config" / "principals.json").read_text(encoding="utf-8"))["principals"]
    keys = {p["name"]: env[p["api_key_env"]] for p in cfg}
    api_evidence(args.api, keys)
    write("mocks.txt", run([PY, "mocks/p24_external_assistant/p24_client.py", "Quanto costano le copie per l'accesso agli atti?"])
          + "\n" + run([PY, "mocks/p24_external_assistant/p24_client.py", "Qual è il menu della mensa aziendale?"])
          + "\n" + run([PY, "mocks/p12_document_generation/p12_client.py", "lavoro agile disconnessione"]))
    write("pytest_verbose.txt", run([PY, "-m", "pytest", "-v", "-p", "no:cacheprovider"]))
    write("environment.txt", run(["nvidia-smi", "--query-gpu=name,driver_version,memory.total", "--format=csv"])
          + "\n" + run(["docker", "ps", "--format", "{{.Names}}  {{.Image}}  {{.Status}}  {{.Ports}}"])
          + "\n" + run([PY, "--version"]) + "\n" + run(["git", "log", "--oneline", "-15"]))
    screenshots(args.api, args.ui)
    return 0


if __name__ == "__main__":
    sys.exit(main())
