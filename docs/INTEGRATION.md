# Integration contract (deliverables 5, 6, 7)

## Primary mechanism and contract files
REST/OpenAPI, synchronous JSON over HTTP.
- `contracts/schemas/*.json` - JSON Schemas (draft 2020-12) of every exchanged object, generated from the Pydantic models in `src/p14_search/models.py` and frozen.
- `contracts/openapi/p14-search.yaml` - OpenAPI 3 document generated from the FastAPI app and frozen.
- `contracts/examples/` - one REAL input (`IngestDocument.real.json`) and one REAL output (`SearchResponse.real.json`) produced by the running system (deliverable 6).
- Freeze/refresh: `python scripts/export_contracts.py --openapi`. `tests/test_contract.py` fails if the code drifts from the frozen files, if a real API response does not validate, or if an example does not validate.

## Endpoints (v1, implemented)
| Method and path | Purpose | Success | Who |
|---|---|---|---|
| POST /v1/search | Ranked documents, passages, citations, evidence, summary, versions | 200 | any principal |
| POST /v1/documents | Ingest an `IngestDocument`; stays **pending** (not searchable) | 202 | officer of that office, admin |
| POST /v1/documents/{document_id}/approve | Owner approval: index the current version | 200 | officer of that office, admin |
| GET /v1/documents/{document_id} | Metadata, status, versions | 200 | ACL (pending: only who may approve) |
| GET /v1/passages/{passage_id} | Resolve a cited passage, also from superseded versions (`active=false`) | 200 | ACL |
| POST /v1/feedback | Store the user's judgement on a passage | 201 | any principal |
| GET /v1/health | sqlite/qdrant status (`ok`/`degraded`) | 200 | public |
| GET /v1/version | Version block | 200 | public |

Stretch (not implemented): GET /v1/documents/{id}/related, CloudEvents `p14.document.indexed`, MCP tool wrapper.

## Authentication and principals
Header `X-API-Key`. Keys live in `.env` only; `config/principals.json` maps each principal to a level and offices:
| Principal | Level | Offices (restricted visible) | Role |
|---|---|---|---|
| p24-external-assistant | public | - | consumer |
| p12-document-generation | internal | - | consumer |
| employee | internal | - | employee |
| hr-officer, it-officer, legal-officer, dpo, rspp | restricted | own office | officer (may ingest/approve own office) |
| admin | restricted | all | admin |
Unknown or missing key -> 401. Documents or passages the principal may not see -> 404 (no existence leak).

## Version block (in every SearchResponse and in GET /v1/version)
`pipeline_version`, `chunker_version`, `embedding_model`, `reranker_model` (null: no reranker), `index_snapshot_id` (hash of the set of searchable passages; changes at every approval).

## Search response (formal schema: contracts/schemas/SearchResponse.json)
`request_id` (also in the `X-Request-ID` header), `query`, `system` (B0/S1/S2 shown), `results[]` ranked by best passage: `document_id`, `document_version`, `title`, `access_level`, `metadata`, `owner`, `synthetic`, `llm_generated`, `best_rank`, `passages[]` {`passage_id`, `text`, `citation` {document_id, document_version, title, section, page, char_start, char_end, source_url}, `evidence` {score, rank, retriever_ranks, retriever_scores}}; `insufficient_evidence`; `summary` {method: extractive, generated: false, sentences[] {text, passage_id}} or null; `versions`.
`evidence` scores are not calibrated probabilities and are never called "confidence".

## Inbound format: IngestDocument (contracts/schemas/IngestDocument.json)
Shared by every producer (admin upload, P11, P15, P25): `source_id`, `external_id`, `title`, `file` {filename, media_type in PDF/DOCX/HTML/TXT, content_base64}, `metadata` {office, type, author, date, project, source_url}, `access_level`, `owner`, `source_piece` (e.g. "P11"), `validated_by` (P25), `synthetic`, `llm_generated`. Unknown fields are rejected. `access_level` and `owner` are mandatory (human-oversight point).

## Persistent identifiers
- `document_id` = `<source_id>:<external_id>` - stable, independent of content.
- `document_version` = SHA-256 of the file bytes.
- `passage_id` = `p_` + SHA-256(document_id | document_version | chunker_version | char_start)[:32].
Re-ingesting unchanged content returns `unchanged: true` and the same ids. A new version stays pending; the old one remains searchable until the new one is approved, then it becomes `superseded` but its passages are still resolvable with `GET /v1/passages/{id}` (`active: false`). A new `chunker_version` changes passage ids (announced in the version block).

## Errors (RFC 9457 `application/problem+json`: type, title, status, detail, instance)
| Code | When |
|---|---|
| 401 | Missing or unknown X-API-Key |
| 403 | Ingest/approve outside the principal's offices |
| 404 | Unknown id, or not visible to the principal |
| 410 | Deleted document (tombstone) - **documented, not implemented in the MVP** |
| 413 / 415 | File too large / unsupported or mismatching media type, macro-enabled DOCX, encrypted PDF |
| 422 | Invalid request (validation), invalid base64, corrupted file, unsafe XML |
| 503 | Services not initialised or vector index unreachable |
| 500 | Unexpected error (no internal details in the body) |

## Versioning and deprecation policy (documented; not implemented in the MVP)
Additive changes stay in /v1. A breaking change creates /v2; /v1 is kept for at least one further release and is announced with a `Deprecation` header. The frozen contract files are versioned in git.

## Connections (deliverable 7)
Frequency of all outbound exchanges: on demand, synchronous, one request per user question.

### P24 External assistant (outbound) - mock implemented: mocks/p24_external_assistant/p24_client.py
| Aspect | Contract |
|---|---|
| Data received by P14 | `SearchRequest` (query, top_k) with P24's key |
| Data provided by P14 | `SearchResponse` with **public** content only (P24's key maps to level public) |
| Expected behaviour of P24 | Answers only with the extractive summary sentences and their citations; escalates to a human operator when `insufficient_evidence` is true or no summary exists; refuses (escalates) if any non-public document is received (defensive check) |
| Errors | non-200 -> escalate |
| Test | tests/test_mocks.py (answers with citations, never sees restricted content, escalates) |

### P12 Document generation (outbound) - mock implemented: mocks/p12_document_generation/p12_client.py
| Aspect | Contract |
|---|---|
| Data received by P14 | `SearchRequest` (topic), then `GET /v1/passages/{id}` for each cited passage |
| Data provided by P14 | Passages with `passage_id`, citation and version |
| Expected behaviour of P12 | Builds a DRAFT where every statement is copied from a passage and ends with `[passage_id]`; re-resolves each id before citing it; the draft states it requires human review |
| Errors | `insufficient_evidence` or no results -> "no_sources", no draft |
| Test | tests/test_mocks.py (every cited id resolves) |

### P11 Document reading (inbound) - documented
| Aspect | Contract |
|---|---|
| Data received | Structured documents + extracted metadata as `IngestDocument` (`source_piece: "P11"`) |
| Data provided | `IngestResult` {document_id, document_version, status: pending, passages} |
| Frequency | On demand or batch, one request per document |
| Expected behaviour | Document is parsed and chunked but becomes searchable only after owner approval |

### P15 Meeting memory (inbound) - documented
`IngestDocument` with `metadata.type = "meeting_minutes"` after each meeting; same approval rule; its access level is kept.

### P25 Expert knowledge (inbound, and outbound retrieval) - documented
Validated knowledge cards as `IngestDocument` with `owner` and `validated_by`; the owner appears in search results. The direction of this connection is an open question (OPEN_QUESTIONS Q10).
