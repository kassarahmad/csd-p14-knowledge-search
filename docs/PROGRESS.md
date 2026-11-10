# Progress

Last update: 2026-11-10

## Done
- Kickoff: course requirements verified verbatim (COURSE_REQUIREMENTS.md); design drafts reviewed and revised.
- Phase 3: corpus decided (ADR-003) - D1a 32 real Italian acts, D1b 25 synthetic LLM-generated documents, D2 SciFact; DATA.md.
- Phase 4: skeleton (pyproject, Qdrant compose, FastAPI, JSON logging).
- Phase 5: MVP - safe parser, chunker with persistent ids, FTS5 + Qdrant, ACL inside retrieval, RRF, citations, evidence,
  insufficient_evidence, extractive summary, all endpoints, approval gate, query/shadow logs, contract freeze, ingestion of D1.
- Phase 6: 110 LLM-drafted queries (test frozen before tuning), qrels, ADR-005 model choice, threshold calibration,
  full evaluation with randomization tests, ACL leakage, latency, D2; error analysis; EVALUATION.md generated from results.
- Phase 7: real contract examples, P24 and P12 mock consumers with tests, INTEGRATION.md aligned with code.
- Phase 8: Streamlit demo with principal selector and feedback; UI test.
- Phase 9: Mermaid diagrams, REPORT.md, REPRODUCIBILITY.md, DEFENSE_NOTES.md (Italian), ADR-006..009.

- Phase 10: two clean end-to-end runs (scripts/reproduce.py --clean), all 13 steps exit 0, identical results;
  eval/check_doc_numbers.py: 0 problems; docs/DELIVERABLES_CHECKLIST.md written; real examples regenerated
  (scripts/make_examples.py).

- Session 2026-11-10 (b): requirements audit (all 8 common deliverables present; gaps listed in docs/GUIDA_STUDENTE.md 1.2);
  fixed stale statements in README and ARCHITECTURE; added OPEN_QUESTIONS Q14 (AI-assistance policy);
  eval/review_worksheet.py + tests (83 passed); docs/GUIDA_STUDENTE.md (implementation walkthrough + review procedure);
  final technical report (Claude Doc) https://claude.ai/artifact/XpeZSQnpwB2naJ8E6p84fN and final presentation (15 slides)
  https://claude.ai/artifact/XZVpZprLdHvoKh64o7u429, built from eval/results only. Draft report and proposal deck left unchanged.

## In progress
- Nothing: MVP and evaluation complete. No stretch goal started.

## Blocked / waiting for the professor
- Q1 assignment of P14; Q7/Q13 acceptability of public + synthetic corpus; Q11 personal data in GU issues; Q14 AI-assistance policy;
  Q12 acceptability of LLM-drafted relevance judgments (OPEN_QUESTIONS.md).

## Next (student)
1. Review ALL LLM-generated material with eval/review/review_worksheet.csv (docs/GUIDA_STUDENTE.md section 3): queries and targets, out-of-scope labels (Q065 doubtful), error-analysis
   categories, synthetic documents (checklist in ANNOTATION_PROTOCOL.md section 5).
2. If test queries change: re-freeze (eval/freeze_test.py), re-run scripts/reproduce.py, re-render the results.
3. Send OPEN_QUESTIONS to the professor (now Q1-Q14).
4. After the review: complete the bracketed AI-use paragraph in report section 11; rehearse the deck with the speaker notes.
5. Stretch goals, only after review: reranker S3, /related, CloudEvents, MCP wrapper, local LLM summary.
