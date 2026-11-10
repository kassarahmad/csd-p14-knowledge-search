# Annotation protocol - D1 question set and relevance judgments

**Status: LLM-DRAFTED.** All queries and target annotations in `eval/queries/d1_queries.jsonl` were drafted by an LLM (Claude) during this project and carry `"llm_generated": true`. They must be reviewed by the student before final submission (checklist at the end).

## 1. What is annotated
Each query record contains:
| Field | Meaning |
|---|---|
| `qid` | Stable id (`T..` tuning, `Q..` test). |
| `query` | Text a user of Ente Demo could type. |
| `lang` | `it` or `en` (English queries test cross-lingual retrieval over the Italian corpus). |
| `type` | `keyword` (uses the documents' own terms), `paraphrase` (everyday wording, little lexical overlap), `conceptual` (needs understanding or combines two facts), `out_of_scope` (the corpus does not answer it). |
| `principal` | API principal used to run the query in the evaluation (sees the target documents). |
| `split` | `tuning` or `test`. |
| `targets` | List of `{document_id, section, snippet}`: the document and section that answer the query and a short **verbatim** snippet of the answer copied from the parsed text. Empty for `out_of_scope`. |
| `llm_generated` | Always `true` for this set. |

## 2. From targets to passage-level graded qrels
`eval/build_qrels.py` derives graded qrels for the CURRENT index (so they survive re-chunking):
- **grade 2** - the passage contains the target snippet (after lower-casing and whitespace normalisation), in any document (duplicates of the same text are also relevant);
- **grade 1** - the passage belongs to a target document and its section starts with the target section, but does not contain the snippet (same article, partially relevant);
- **grade 0** - everything else (not judged = not relevant).
A query whose snippet matches no passage is reported as an error by the script (the annotation must be fixed, not ignored).

Document-level relevance (for the correct-source rate) = a document containing at least one passage with grade >= 1.

## 3. Writing rules (to limit bias)
1. Queries are written as a user would ask, not by copying sentences; `paraphrase` queries avoid the key nouns of the target text.
2. The test split was written and committed (frozen with a SHA-256 hash in `eval/queries/test_freeze.json`) BEFORE any tuning (threshold calibration, embedding-model choice).
3. About 15% of the queries are out of scope: plausible questions for a public body whose answer is not in the corpus.
4. About 10% are in English.
5. Restricted-document queries use a principal of the owning office.

## 4. Known limitations
- **Single annotator, and the annotator is an LLM** that also wrote the synthetic documents: lexical overlap between queries and D1b texts may inflate scores on D1b.
- **Incomplete judgments**: only the target passages are judged; other passages that also answer the query count as non-relevant, so absolute scores are underestimated (the same for all systems, so comparisons remain fair).
- Snippets on Gazzetta Ufficiale PDFs refer to the text as originally published.

## 5. Review checklist for the student (before submission)
- [ ] Read every test query: is it natural, unambiguous, and correctly typed?
- [ ] For each target, open the cited section (GET /v1/passages/{id} or the demo UI) and confirm the snippet really answers the query.
- [ ] For a sample of at least 20 test queries, look at the top-10 passages of S2 and B0 and note relevant passages that are NOT in the qrels (incomplete judgments).
- [ ] Confirm that out-of-scope queries are really not answered by the corpus (search them).
- [ ] Check the English queries for translation quality.
- [ ] Record the review outcome (changes made, number of corrections) in this file; if test queries change, re-freeze and re-run the evaluation.
