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
Shadow-mode protocol (simulated): EVALUATION.md "Shadow-mode validation".
