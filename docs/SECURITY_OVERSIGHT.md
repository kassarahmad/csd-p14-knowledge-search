# Security, traceability, human oversight (deliverable 8)

## Security
Input validation (Pydantic); file type/size limits; safe parsing (no macros, no external entity resolution); permission-aware retrieval: ACL filter applied **inside** both retrievers (Qdrant payload filter, FTS5 WHERE) before results leave the service; API key per consumer; data minimisation; secrets in .env; prompt-injection mitigation (retrieved text treated as data). Access control model: ARCHITECTURE.md.

## Human oversight
The P14 sheet has no explicit human-oversight bullet, but the framework's cross-cutting requirements apply to all projects. Where a person intervenes:
1. Content owner/admin approves ingestion and the `access_level` of each document.
2. The user sees citations and decides; P14 takes no action.
3. `insufficient_evidence: true` instead of guessing.
4. Any summary is marked (`generated`) and linked to its `passage_id`s; MVP summary is extractive.
5. User feedback is stored as the operator's final decision.

## Traceability
Every response carries a version block; every query is stored in `query_log` (see ARCHITECTURE.md) with pseudonymised principal, inputs, outputs, evidence and feedback. Scores are called `evidence`, not confidence. Retention period: to be defined (proposal: deleted after the evaluation phase).

## Validation before automation
Shadow-mode protocol (simulated): EVALUATION.md "Validation before automation (shadow mode)".

## Implementation status and evidence
| Control | Where | Evidence |
|---|---|---|
| API key per consumer, keys only in .env, SHA-256 + constant-time compare | security/principals.py | tests/test_api.py (401) |
| ACL inside both retrievers + re-check at hydration; 404 for invisible documents | security/acl.py, retrieval/service.py | tests/test_acl_leakage.py; evaluation: 0 leaks (EVALUATION.md, T5) |
| Safe parsing: magic numbers, size limit, macro/XXE/zip-bomb DOCX, encrypted PDF rejected | ingestion/parser.py | tests/test_parser_chunker.py |
| Owner approval before indexing (human oversight) | ingestion/service.py, ADR-007 | tests/test_api.py; approval_log (corpus approvals SIMULATED) |
| Version block in every response; query_log with pseudonymised principal; feedback | retrieval/service.py, indexing/store.py | tests/test_api.py |
| insufficient_evidence with calibrated thresholds | config + eval/calibrate_threshold.py | EVALUATION.md (T3) |
| Shadow mode (display + shadow system, shadow_log) | retrieval/service.py | tests/test_api.py; docs/diagrams/07-sequence-shadow.mmd |
| RFC 9457 errors without internal details | api/app.py | tests/test_api.py, tests/test_contract.py |
| Prompt-injection | Not applicable in the MVP: no LLM consumes retrieved text inside P14. Consumers (P12/P24) must treat passages as data. | - |
| Retention | Not implemented: proposal = delete query_log/shadow_log/feedback at the end of the evaluation phase. | - |
