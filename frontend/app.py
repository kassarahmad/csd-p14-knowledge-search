"""P14 demo UI (Streamlit). Talks to the P14 API over HTTP like any other consumer.

Run:  streamlit run frontend/app.py   (with the API running: uvicorn p14_search.main:app --port 8000)
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import requests
import streamlit as st
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
ENV = {**dotenv_values(ROOT / ".env"), **os.environ}
PRINCIPALS = json.loads((ROOT / "config" / "principals.json").read_text(encoding="utf-8"))["principals"]
LEVEL_BADGE = {"public": "🟢 public", "internal": "🟡 internal", "restricted": "🔴 restricted"}

st.set_page_config(page_title="P14 Knowledge Search", page_icon="🔎", layout="wide")

with st.sidebar:
    st.header("Settings")
    api_url = st.text_input("P14 API", ENV.get("P14_URL", "http://127.0.0.1:8000"))
    names = [p["name"] for p in PRINCIPALS]
    name = st.selectbox("Principal (who is searching)", names, index=names.index("employee"),
                        help="Each principal sees only the access levels it is allowed to: change it to see the ACL at work.")
    principal = next(p for p in PRINCIPALS if p["name"] == name)
    st.caption(f"level: **{principal['level']}** · offices: {', '.join(principal['offices']) or '—'}")
    api_key = ENV.get(principal["api_key_env"], "")
    top_k = st.slider("Passages", 3, 20, 8)
    try:
        health = requests.get(f"{api_url}/v1/health", timeout=3).json()
        if health["status"] == "ok":
            st.success(f"API {health['status']}")
        else:
            st.warning(f"API {health['status']}: {health['components']}")
    except requests.RequestException:
        st.error("API not reachable")

st.title("🔎 P14 - Search across organizational knowledge")
st.caption("Ente Demo (fictional organization). Real Italian legislation + SYNTHETIC internal documents. Every result cites its source.")

query = st.text_input("Ask a question", placeholder="Es. Quanti giorni al mese posso lavorare da casa?")
if st.button("Search", type="primary") and query.strip():
    r = requests.post(f"{api_url}/v1/search", json={"query": query, "top_k": top_k}, headers={"X-API-Key": api_key}, timeout=60)
    if r.status_code != 200:
        st.error(f"{r.status_code}: {r.json().get('title')} - {r.json().get('detail')}")
    else:
        st.session_state["last"] = r.json()

body = st.session_state.get("last")
if body:
    if body["insufficient_evidence"]:
        st.warning("⚠️ **Insufficient evidence**: the knowledge base does not seem to answer this question. "
                   "The results below are weak matches - verify them or ask the responsible office.")
    elif body.get("summary"):
        st.subheader("Extractive summary")
        st.caption("Sentences copied verbatim from the sources (nothing generated). Each one cites its passage.")
        for s in body["summary"]["sentences"]:
            st.markdown(f"> {s['text']}  \n`{s['passage_id']}`")

    st.subheader(f"Documents ({len(body['results'])})")
    for d in body["results"]:
        flags = " · ⚠️ SYNTHETIC (LLM-generated)" if d["synthetic"] else ""
        with st.expander(f"#{d['best_rank']} {d['title']} — {LEVEL_BADGE[d['access_level']]}{flags}", expanded=d["best_rank"] <= 2):
            st.caption(f"`{d['document_id']}` · office: {d['metadata']['office']} · type: {d['metadata']['type']} · owner: {d['owner']}"
                       + (f" · [source]({d['metadata']['source_url']})" if (d["metadata"].get("source_url") or "").startswith("http") else ""))
            for p in d["passages"]:
                c, e = p["citation"], p["evidence"]
                where = " · ".join(x for x in (c["section"], f"page {c['page']}" if c["page"] else None, f"chars {c['char_start']}-{c['char_end']}") if x)
                st.markdown(f"**Rank {e['rank']}** · {where}")
                st.write(p["text"])
                st.caption(f"evidence: score {e['score']:.4f} · BM25 rank {e['retriever_ranks'].get('bm25')} · dense rank "
                           f"{e['retriever_ranks'].get('dense')} · version `{c['document_version'][:12]}` · passage `{p['passage_id']}`")
                cols = st.columns(3)
                for col, (label, judgement) in zip(cols, (("👍 useful", "useful"), ("👎 not useful", "not_useful"), ("❌ wrong source", "wrong_source"))):
                    if col.button(label, key=f"{judgement}-{p['passage_id']}"):
                        fb = requests.post(f"{api_url}/v1/feedback", headers={"X-API-Key": api_key}, timeout=10,
                                           json={"request_id": body["request_id"], "passage_id": p["passage_id"], "judgement": judgement})
                        st.toast("Feedback stored" if fb.status_code == 201 else f"Feedback error {fb.status_code}")
                st.divider()
    with st.expander("Traceability"):
        st.json({"request_id": body["request_id"], "system": body["system"], "versions": body["versions"]})
