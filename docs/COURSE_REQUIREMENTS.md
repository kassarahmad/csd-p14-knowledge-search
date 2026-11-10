# Course requirements (verified)

Source: "AI PUZZLE - Framework of Autonomous Artificial Intelligence Projects for Public and Private Organizations",
Consolidated version 5.0 - Complex Systems Design course (distributed by the course; not redistributed in this repository).
Only facts stated in that document are listed here. Everything else is in OPEN_QUESTIONS.md.
Section names of the source are given in [brackets]; text in quotes is verbatim.
Last verified against the PDF: 2026-11-10 (text extracted with pdftotext; the two figures are images and were not verified).

## Puzzle rule [General architecture and puzzle rule]
- Projects "can be assigned independently to different groups".
- Each group designs its piece "as a system that is useful on its own, while also preparing it so that its outputs can become inputs to other pieces".
- "Connections are not mandatory dependencies: they are composition opportunities that ultimately reveal the behaviour of the complex system."
- Two views of the puzzle: by thematic area and by function ("from raw data to action"; "each level uses outputs from the levels below").
- "Cross-cutting requirements - human oversight, traceability, security, shadow-mode validation, and evaluation - apply to all projects."

## Principles [Principle of autonomy] [Principle of integrability] [Infrastructure inside the projects]
- Autonomy: "The project must produce value even if no other puzzle piece is available."
- Integrability: "The project must document inputs, outputs, and at least one standard mechanism through which other systems can consume its results."
- Infrastructure: "Data acquisition, identity, security, MLOps, observability, knowledge bases, validation, and human oversight are not separate pieces: they are designed inside the projects that need them."

## Common design principles [Common design principles]
- Autonomy: each piece must produce value even when the other pieces are unavailable.
- Interoperability: inputs and outputs must be documented and at least one integration mechanism must be designed and justified.
- Embedded infrastructure: data acquisition, dataset management, access, MLOps, monitoring, security, and privacy become part of the project when needed.
- Human oversight and explainability: "when an output affects people, processes, or decisions, the project must include human validation, reasons/evidence, and traceability."
- Validation before automation: "whenever possible, the system is initially tested in shadow mode by comparing its proposals with the real process without changing it."
- Open standards: where appropriate, OpenAPI/REST, CloudEvents, MQTT/OPC UA, MCP, and documented structured formats.

## Shared group template (7 sections) [Shared group template]
1 Project - 2 Input data sources - 3 Objectives - 4 Expected result / Output - 5 Required components - 6 Connections with other puzzle pieces - 7 Success criteria.
Section 6 must specify "which pieces can use its outputs, which outputs from other pieces can become its inputs, and which technical mechanisms can support the exchange (for example REST/OpenAPI APIs, events, webhooks, MQTT, OPC UA, structured JSON/CSV files, message queues, or MCP where appropriate)."

## Common deliverables for each group [COMMON DELIVERABLES FOR EACH GROUP]
1. Architecture of the piece and rationale for the main design choices.
2. Executable prototype or demonstrator on the selected case study.
3. Data description: sources, schema, quality, limitations, privacy aspects, and conditions of use.
4. Experimental evaluation with baseline, metrics, and the success criteria defined in the project sheet.
5. Contract for the selected integration interface (for example OpenAPI, event schema, MQTT/OPC UA topic, or MCP where appropriate).
6. At least one real exchangeable input example and one real machine-readable output example.
7. Description of at least two possible connections with other pieces: data received, data provided, and expected behaviour.
8. Note on human oversight, traceability, security, and validation before automation.

## Common design rules [Common design rules]
- Autonomy: "Each piece must be usable and assessable on its own."
- Explicit data: "Format, frequency, quality, ownership, and limitations of inputs must be documented."
- Machine-readable outputs: "At least the main outputs must have a structured representation in addition to the user-facing presentation."
- Documented interface: "Each group must design at least one mechanism through which other systems can consume its outputs."
- Security and privacy: addressed inside the project "in proportion to the data and actions involved."
- Human oversight: "When the system supports consequential decisions, it must be clear where and how a person intervenes."
- Evaluation: "Each group must define a baseline, metrics, and acceptance conditions before declaring the project successful."
- Final composition: "Only in the final stage of the course will outputs and interfaces of the pieces be connected to study the emerging complex system."

## P14 project sheet [14. Intelligent search across organizational knowledge]
Thematic area in the index: "Documents, Knowledge & Organizational Memory".

1. Project: "Build a search engine capable of finding information by meaning, not only by exact keyword match. The system should search across heterogeneous documents and repositories and always return the precise references to the sources from which information was obtained."
2. Input data sources: internal documents, manuals, procedures, regulations, reports, and authorised archives; metadata (author, date, office, type, project, access level); questions or queries submitted by users; website and intranet; shared mailboxes and internal FAQs; technical manuals for machines and plants.
3. Objectives: reduce the time needed to find information; retrieve content even when users use different wording from the documents; connect relevant sources on the same topic; always make the provenance of results verifiable.
4. Expected result / Output: ranked list of the most relevant documents; specific passages that answer the search request; source references and metadata; optional summary built only from retrieved content.
5. Required components: document ingestion; semantic/keyword indexing; embeddings; retrieval/reranking; access control; citations. "Infrastructure to consider where relevant: source and permission management, prompt/model versioning, processing logs, data protection, and quality monitoring in operation."
6. Connections:
   - "P12 Generation, P15 Meetings, P25 Expert knowledge, P24 External assistant: provides retrieval with source attribution."
   - "Exchange: search/retrieval API; persistent document and passage identifiers."
   - "The group must document at least one exchange contract: data provided, data received, format, frequency, and error/version management."
   - "Candidate mechanisms: REST/OpenAPI, events/CloudEvents, structured JSON/document formats; MCP when the piece exposes capabilities usable by AI assistants or agents."
7. Success criteria:
   - "Retrieval recall/precision on a question set; quality of returned sources; latency; percentage of answers with the correct source."
   - "Traceability/explainability: retain model version, relevant inputs, outputs, confidence level or evidence, and, where applicable, the operator's final decision."

Note (fact about the document, not an interpretation): unlike several other sheets (e.g. P11), the P14 sheet has no
"Recommended validation" (shadow mode) bullet and no "Human oversight: define which outputs require confirmation..." bullet
in section 7. Shadow-mode validation and human oversight still apply through the cross-cutting requirements and
common design principles quoted above.

## Mentions of P14 in other sheets (verbatim, section 6 of each sheet)
| Sheet | Text | Direction as we read it |
|---|---|---|
| 11. Automatic document reading and classification | "P14 Search: feeds the index/knowledge base." | P11 -> P14 |
| 12. Assisted document generation | "P14 Search and P25 Expert knowledge: uses trusted sources." | P14 -> P12 |
| 15. Intelligent meeting memory | "P14 Search: indexes meeting memory." | P15 -> P14 |
| 24. Information assistant for external users | "P14 Search: receives passages and sources." | P14 -> P24 (P24 receives) |
| 25. Capturing and transferring expert knowledge | "P14 Search: feeds the knowledge base." | P25 -> P14 (wording ambiguous) |

The "Direction" column is our reading of the text, not a statement of the document.
