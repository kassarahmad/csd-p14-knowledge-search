# Data description (deliverable 3)

The case study is a **fictional public organization, "Ente Demo"**. Its knowledge base combines real public legislation (D1a) with synthetic internal documents (D1b). A public benchmark (D2) is used only as a sanity check of the pipeline. Decision record: ADR-003 in DECISIONS.md.

Corpus statistics (characters, passages per source, per format): produced by `scripts/corpus_stats.py` into `eval/results/corpus_stats.json` - see section "Statistics" below.

## D1a - Real Italian official acts (32 documents)
| Aspect | Description |
|---|---|
| Content | Italian national acts relevant to a public employer: workplace safety (D.Lgs. 81/2008), smart working (L. 81/2017), data protection (D.Lgs. 196/2003, D.Lgs. 101/2018), digital administration (D.Lgs. 82/2005), transparency and anti-corruption, public employment, leave, whistleblowing, cybersecurity (L. 90/2024, D.Lgs. 138/2024), accessibility, etc. Full list with URNs: `data/d1a_manifest.json`. |
| Sources | Normattiva (www.normattiva.it, "esporta atto completo" of the consolidated text) and Gazzetta Ufficiale della Repubblica Italiana (www.gazzettaufficiale.it, PDF of the issue). Each file's URN, source URL, SHA-256 and fetch time are recorded by the fetch script in `data/raw/d1a/fetch_record.json`. |
| Licence / conditions of use | Art. 5, L. 633/1941 (Italian copyright law), verified on Normattiva: "Le disposizioni di questa legge non si applicano ai testi degli atti ufficiali dello stato e delle Amministrazioni pubbliche, sia italiane che straniere." The texts are therefore not covered by copyright. We cite the source of every file. Raw files are not committed; they are re-downloaded with `python scripts/fetch_corpus.py`. |
| Formats | 19 HTML (Normattiva export as served), 6 TXT (plain-text rendition of the Normattiva export, produced by `fetch_corpus.py:html_to_text` - content unchanged, markup removed), 7 PDF (Gazzetta Ufficiale issue as originally published). |
| Metadata assigned by us | `office` (hr, safety, privacy, it, legal) - the Ente Demo office that would own the topic; `access_level = public`; `type = legislation`; `owner` = head of that office (role). These assignments are ours, not part of the source. |
| Frequency | Static snapshot taken on the fetch date. Normattiva texts are the version in force on that date; they change when the law is amended. |
| Quality issues and limitations | (1) A GU PDF is the **whole issue** in which the act was published, so it also contains unrelated acts and notices: realistic archive noise, but the document title refers only to the target act. (2) GU PDFs contain the text **as originally published**; later amendments are not reflected, while HTML/TXT files are consolidated. (3) Normattiva states that consolidated texts are an editorial service; only the Gazzetta Ufficiale text is authentic. (4) Two acts published in the same GU issue were assigned different formats to avoid a duplicate file. (5) Some acts are very long (e.g. D.Lgs. 81/2008 with annexes), so the corpus is skewed toward a few large documents. (6) Legal language: queries in everyday wording face a strong vocabulary mismatch - this is intended, it is what P14 must handle. |
| Privacy | Target acts contain only names of signatories (public officials in their institutional role). The GU issues also contain unrelated acts naming private individuals: see "Privacy note" below. |

## D1b - Synthetic internal documents of Ente Demo (25 documents) - SYNTHETIC, LLM-GENERATED
| Aspect | Description |
|---|---|
| Content | Internal regulations, procedures, policies, FAQs, office circulars, one meeting minute, a budget, an audit report, extracts of a risk assessment and of the processing register. Sources: `data/d1b_source/*.md` (committed). |
| How produced | **Written by an LLM (Claude) during this project** and rendered to PDF/DOCX/TXT by `scripts/generate_d1b.py`. Every record carries `synthetic: true` and `llm_generated: true` (`data/raw/d1b/generation_record.json`); every rendered file starts with the banner "DOCUMENTO SINTETICO - Ente Demo è un'organizzazione fittizia". |
| Licence | Created for this project; may be redistributed with the project (proposal: CC BY 4.0, to be confirmed by the student). |
| Formats | 8 TXT, 8 DOCX, 9 PDF. |
| Access levels and offices | 5 `public`, 14 `internal`, 6 `restricted` (restricted: 2 it, 2 hr, 1 privacy, 1 safety). Used to test the ACL filter. |
| Links to D1a | Many synthetic documents cite real acts (e.g. the smart-working regulation implements L. 81/2017, artt. 18-23), so related sources across real and synthetic documents exist on purpose. |
| Limitations | (1) Not a real organization: internal facts (hours, budgets, deadlines) are invented and must not be read as real practice. (2) Legal references were written by an LLM: they are plausible but **not legally verified**. (3) The same author (an LLM) wrote documents and, later, queries: risk of lexical overlap that inflates scores; mitigations in ANNOTATION_PROTOCOL.md. (4) Small size compared with D1a. |
| Privacy | No personal data: people are referred to only by role; e-mail addresses use the reserved `.example` domain. |

## D2 - Sanity benchmark: BEIR SciFact (English)
| Aspect | Description |
|---|---|
| Content | Scientific claims (queries) and abstracts (corpus) with relevance judgments, BEIR version. 5,183 abstracts; 300 test queries; 339 test qrels lines (row counts of the downloaded files). |
| Source | https://public.ukp.informatik.tu-darmstadt.de/thakur/BEIR/datasets/scifact.zip (downloaded by `fetch_corpus.py`, SHA-256 recorded in `data/raw/d2/fetch_record.json`). Original dataset: github.com/allenai/scifact. |
| Licence | Claims and evidence annotations: CC BY 4.0. Abstracts: ODC-By 1.0 (part of S2ORC). Verified in the LICENSE.md of allenai/scifact. |
| Use | Only to check that the pipeline behaves as expected on data with independent qrels (not the case study). English only. |

## Schema of an ingested document
`IngestDocument` (contracts/schemas/): `source_id` (d1a / d1b), `external_id`, `title`, content or file, `metadata` {author, date, office, type, project}, `access_level`, `owner`, `source_piece`, plus `synthetic` / `llm_generated` flags carried into metadata and returned in search results.

## Statistics (from eval/results/corpus_stats.json, produced by scripts/corpus_stats.py)
| Group | Documents | Passages | Text characters |
|---|---|---|---|
| D1a real acts | 32 | 10,561 | 6,928,651 |
| - HTML | 19 | 5,399 | 3,516,692 |
| - PDF (GU issues) | 7 | 4,532 | 3,034,200 |
| - TXT | 6 | 630 | 377,759 |
| D1b synthetic | 25 | 128 | 34,644 |
| - DOCX / PDF / TXT | 8 / 9 / 8 | 51 / 28 / 49 | 10,743 / 14,141 / 9,760 |
| **Total** | **57** | **10,689** | **6,963,295** |

By access level: public 37 documents (10,582 passages), internal 14 (83), restricted 6 (24).
Mean passage length 668.7 characters; 97.85% of passages carry a section label (article or heading).
Largest documents: D.Lgs. 81/2008 (914 passages), then three GU PDF issues (D.Lgs. 24/2023, L. 81/2017, L. 90/2024: 868, 853, 803).
Note the imbalance: D1b is 0.5% of the text, so internal knowledge is a needle in a haystack of legislation - realistic, and it makes ACL tests meaningful.

## Parsing quality issues found (and how they were handled)
| Issue | Where | Handling |
|---|---|---|
| Amendment text nested as `<div>` inside `<span>` was dropped by a first, element-based HTML parser (coverage down to 27% on L. 300/1970) | Normattiva HTML | Parser rewritten as a document-order DOM walk; coverage 94-98% of the plain-text rendition (remaining difference = article headings moved into section labels) |
| Font without ToUnicode map: text extracted as glyph names (`/C76` = "L") | GU PDF 2004 (L. 4/2004) | pypdf fallback with glyph-name repair; words are still often merged without spaces and accented letters are wrong - this document remains low quality |
| Substitution-like font encoding with pypdf ("Eresidente" for "Presidente") | GU PDF 2005 (D.P.R. 68/2005) | pdfium (pypdfium2) as primary extractor, pypdf only when pdfium output is garbled and the fallback is clearly better |
| Soft-hyphen markers at line breaks, words split by hyphenation | GU PDFs | Removed / de-hyphenated in the parser |
| Ligature "fi" extracted as "fi " (e.g. "fi ni") | some GU PDFs | Not fixed (residual noise) |
| Running page headers of the Gazzetta | GU PDFs | Removed by pattern |

## Privacy note on the Gazzetta Ufficiale issues
A GU issue also contains unrelated acts, some of which name **private individuals** (e.g. decrees recognising professional qualifications, with name and date of birth). These are official publications, but they are personal data under the GDPR. Our use: local research prototype, no profiling, no queries about people in the question set; minimisation option (not applied): drop non-target acts from GU issues. Raised as OPEN_QUESTIONS Q11.
