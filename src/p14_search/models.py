"""Domain and API models. These Pydantic models are the source of the JSON Schemas in contracts/schemas/."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AccessLevel(str, Enum):
    public = "public"
    internal = "internal"
    restricted = "restricted"


ACCESS_ORDER = {AccessLevel.public: 0, AccessLevel.internal: 1, AccessLevel.restricted: 2}


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --- Ingestion -------------------------------------------------------------------------------

class DocumentMetadata(_Strict):
    office: str = Field(..., min_length=1, max_length=40, description="Owning office, e.g. hr, it, legal.")
    type: str = Field(..., min_length=1, max_length=40, description="Document type, e.g. legislation, procedure, faq.")
    author: str | None = Field(None, max_length=200)
    date: str | None = Field(None, description="ISO date (YYYY-MM-DD) of the document.", pattern=r"^\d{4}-\d{2}-\d{2}$")
    project: str | None = Field(None, max_length=100)
    source_url: str | None = Field(None, max_length=2000, description="Where the original was obtained.")


class FileContent(_Strict):
    filename: str = Field(..., min_length=1, max_length=255)
    media_type: Literal[
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/html",
        "text/plain",
    ]
    content_base64: str = Field(..., description="File bytes, base64-encoded.")


class IngestDocument(_Strict):
    """Inbound format shared by every producer (admin upload, P11, P15, P25)."""

    source_id: str = Field(..., pattern=r"^[a-z0-9][a-z0-9_-]{0,31}$", description="Source/repository identifier.")
    external_id: str = Field(..., pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$", description="Id of the document in its source.")
    title: str = Field(..., min_length=1, max_length=500)
    file: FileContent
    metadata: DocumentMetadata
    access_level: AccessLevel
    owner: str = Field(..., min_length=1, max_length=200, description="Accountable owner (a role, not a person).")
    source_piece: str = Field("P14", pattern=r"^P\d{2}$", description="Puzzle piece that produced the document.")
    validated_by: str | None = Field(None, max_length=200, description="Expert validation (P25 knowledge cards).")
    synthetic: bool = False
    llm_generated: bool = False


class IngestResult(BaseModel):
    document_id: str
    document_version: str
    status: Literal["pending", "approved"]
    passages: int
    unchanged: bool = Field(False, description="True when the same version was already ingested.")


# --- Search ----------------------------------------------------------------------------------

class SearchFilters(_Strict):
    office: list[str] | None = None
    type: list[str] | None = None
    source_id: list[str] | None = None


class SearchRequest(_Strict):
    query: str = Field(..., min_length=1, max_length=1000)
    top_k: int = Field(10, ge=1, le=50, description="Number of passages to return.")
    filters: SearchFilters | None = None
    with_summary: bool = True


class Citation(BaseModel):
    document_id: str
    document_version: str
    title: str
    section: str | None = Field(None, description="Section heading, e.g. 'Art. 18'.")
    page: int | None = Field(None, description="1-based page for paginated formats (PDF).")
    char_start: int = Field(..., description="Offset in the parsed document text.")
    char_end: int
    source_url: str | None = None


class Evidence(BaseModel):
    """Ranking evidence. Scores are NOT calibrated probabilities and must not be read as confidence."""

    score: float = Field(..., description="Score of the system that produced the ranking (RRF for hybrid).")
    rank: int = Field(..., ge=1)
    retriever_ranks: dict[str, int | None] = Field(..., description="Rank in each retriever (bm25, dense); null = not retrieved.")
    retriever_scores: dict[str, float | None]


class Passage(BaseModel):
    passage_id: str
    text: str
    citation: Citation
    evidence: Evidence


class ResultDocument(BaseModel):
    document_id: str
    document_version: str
    title: str
    access_level: AccessLevel
    metadata: DocumentMetadata
    owner: str
    synthetic: bool
    llm_generated: bool
    best_rank: int
    passages: list[Passage]


class SummarySentence(BaseModel):
    text: str
    passage_id: str


class Summary(BaseModel):
    method: Literal["extractive"] = "extractive"
    generated: bool = Field(False, description="False: sentences are copied verbatim from passages.")
    sentences: list[SummarySentence]


class Versions(BaseModel):
    pipeline_version: str
    chunker_version: str
    embedding_model: str
    reranker_model: str | None
    index_snapshot_id: str | None


class SearchResponse(BaseModel):
    request_id: str
    query: str
    system: str = Field(..., description="Retrieval system that produced the shown ranking (B0, S1, S2).")
    results: list[ResultDocument] = Field(..., description="Documents ranked by their best passage.")
    insufficient_evidence: bool
    summary: Summary | None
    versions: Versions


# --- Documents, passages, feedback ----------------------------------------------------------

class DocumentInfo(BaseModel):
    document_id: str
    source_id: str
    external_id: str
    title: str
    access_level: AccessLevel
    metadata: DocumentMetadata
    owner: str
    source_piece: str
    validated_by: str | None
    synthetic: bool
    llm_generated: bool
    status: Literal["pending", "approved"]
    current_version: str
    versions: list[str]


class PassageInfo(BaseModel):
    passage_id: str
    text: str
    citation: Citation
    active: bool = Field(..., description="False when the passage belongs to a superseded document version.")


class FeedbackJudgement(str, Enum):
    useful = "useful"
    not_useful = "not_useful"
    wrong_source = "wrong_source"


class FeedbackRequest(_Strict):
    request_id: str = Field(..., min_length=1, max_length=64)
    passage_id: str = Field(..., min_length=1, max_length=64)
    judgement: FeedbackJudgement
    comment: str | None = Field(None, max_length=1000)


class FeedbackResult(BaseModel):
    feedback_id: int
    stored: bool = True


class Problem(BaseModel):
    """RFC 9457 problem details."""

    type: str = "about:blank"
    title: str
    status: int
    detail: str | None = None
    instance: str | None = None
