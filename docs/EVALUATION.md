# Evaluation methodology

No results yet. Every number here must be produced by a re-runnable script in eval/.

## Research questions
- RQ1: Does hybrid retrieval (dense + BM25) outperform a BM25-only baseline on our question set?
- RQ2: Does a cross-encoder reranker improve early precision enough to justify its latency? (stretch)
- RQ3: How does performance vary by query type (keyword-like, paraphrased, multi-hop/conceptual, out-of-scope)?
- Further RQs (e.g. cross-lingual queries): TO BE DECIDED with ADR-003.

## Systems compared
B0 BM25 only (baseline, SQLite FTS5) - S1 dense only - S2 hybrid (RRF fusion) - S3 hybrid + reranker (stretch).

## Operational definitions
- Relevance judgments (qrels) at **passage level**, graded 0 (not relevant) / 1 (partially) / 2 (answers the query). Document-level relevance is derived: a document is relevant if it contains at least one passage graded >= 1.
- **Correct-source rate**: share of in-scope queries for which at least one passage in the top 3 belongs to a document judged relevant **and** its citation (document, page/section) points to the right location.
- **Source quality**: manual 3-level rubric (0/1/2) applied to the top-5 passages on a sample of queries; the rubric is written down before annotation.
- **Abstention correctness**: share of out-of-scope queries for which `insufficient_evidence = true`.
- **ACL leakage**: number of returned passages whose access level exceeds the requesting principal's level, over all queries and principals.
- **Latency**: p50/p95 of POST /v1/search measured end-to-end on the student laptop; hardware and settings reported with the numbers.

## Metrics
Recall@K, Precision@K (K = 1, 5, 10), MRR@10, nDCG@10, correct-source rate, source quality, latency p50/p95, abstention correctness, ACL leakage.

## Datasets
- D1 (case study): our corpus (ADR-003) + hand-written queries with passage-level qrels. At least 100 queries, of which at least 60 in a held-out test set; the rest is the tuning set (used e.g. to calibrate the `insufficient_evidence` threshold). Test queries are written and frozen before any tuning. Labelling protocol documented; single-annotator bias declared as a limitation.
- D2 (optional sanity check): a small public benchmark with existing qrels. Choice and licence: TO BE DECIDED with ADR-003.
Synthetic or LLM-generated queries, if used, are labelled as such and never used alone.

## Acceptance targets - OUR proposed targets, NOT official course requirements
Fixed before the held-out test set is run (framework rule: baseline, metrics and acceptance conditions defined before declaring success).

| # | Target | Measured on |
|---|---|---|
| T1 | S2 >= B0 on nDCG@10 and on Recall@10 | D1 test set |
| T2 | Correct-source rate >= 0.80 | D1 test set, in-scope queries |
| T3 | Abstention correctness >= 0.70 | D1 test set, out-of-scope queries |
| T4 | Latency p95 < 1.5 s without reranker; < 3 s with reranker | POST /v1/search, laptop |
| T5 | ACL leakage = 0 (hard constraint) | all test queries x all principals |

Statistical reporting (executed and reported, **not** a success target): a paired randomization test on per-query nDCG@10 and Recall@10 between S2 and B0, with p-values and effect sizes. Per-query-type breakdown reported for RQ3.

## Shadow-mode validation (validation before automation)
The framework asks to test the system "by comparing its proposals with the real process without changing it". We have no real organization, so this is a **simulation**, declared as such (see OPEN_QUESTIONS Q7):
1. The stand-in for the "real process" is the keyword search an organization already has, represented by B0.
2. For each query in a shadow session, the shadow runner executes B0 and the candidate system (S2); only B0's results are shown to the user. Both result lists are stored in `shadow_log` with the version block.
3. User feedback is collected on the shown results; the candidate output does not change what the user sees or does.
4. Offline, the two lists are compared on the same queries (overlap, rank of first relevant passage, judged relevance on a sample).
Result of this phase: evidence on whether S2 would have helped, before it replaces B0 in the UI.

## Results
(empty)
