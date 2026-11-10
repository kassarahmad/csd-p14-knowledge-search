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

## In progress
- Nothing: MVP and evaluation complete. No stretch goal started.

## Blocked / waiting for the professor
- Q1 assignment of P14; Q7/Q13 acceptability of public + synthetic corpus; Q11 personal data in GU issues;
  Q12 acceptability of LLM-drafted relevance judgments (OPEN_QUESTIONS.md).

## Next (student)
1. Review ALL LLM-generated material: queries and targets, out-of-scope labels (Q065 doubtful), error-analysis
   categories, synthetic documents (checklist in ANNOTATION_PROTOCOL.md section 5).
2. If test queries change: re-freeze (eval/freeze_test.py), re-run scripts/reproduce.py, re-render the results.
3. Send OPEN_QUESTIONS to the professor.
4. Stretch goals, only after review: reranker S3, /related, CloudEvents, MCP wrapper, local LLM summary.
