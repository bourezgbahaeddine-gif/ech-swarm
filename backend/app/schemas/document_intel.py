"""Document Intelligence API schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class DocumentExtractNewsItem(BaseModel):
    rank: int
    headline: str
    summary: str
    evidence: str
    confidence: float = Field(ge=0.0, le=1.0)
    entities: list[str] = Field(default_factory=list)


class DocumentExtractClaim(BaseModel):
    text: str
    type: str
    confidence: float = Field(ge=0.0, le=1.0)
    risk_level: str


class DocumentExtractEntity(BaseModel):
    name: str
    type: str


class DocumentStoryAngle(BaseModel):
    title: str
    why_it_matters: str


class DocumentExtractDataPoint(BaseModel):
    rank: int
    category: str
    value_tokens: list[str] = Field(default_factory=list)
    context: str


class DocumentExtractStats(BaseModel):
    pages: int | None = None
    characters: int = 0
    paragraphs: int = 0
    headings: int = 0


class DocumentExtractResponse(BaseModel):
    filename: str
    parser_used: str
    language_hint: str
    detected_language: str
    stats: DocumentExtractStats
    document_summary: str = ""
    document_type: str = "report"
    headings: list[str] = Field(default_factory=list)
    news_candidates: list[DocumentExtractNewsItem] = Field(default_factory=list)
    claims: list[DocumentExtractClaim] = Field(default_factory=list)
    entities: list[DocumentExtractEntity] = Field(default_factory=list)
    story_angles: list[DocumentStoryAngle] = Field(default_factory=list)
    data_points: list[DocumentExtractDataPoint] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    preview_text: str = ""


class DocumentExtractSubmitResponse(BaseModel):
    job_id: str
    status: str
    filename: str
    message: str | None = None


class DocumentExtractJobStatusResponse(BaseModel):
    job_id: str
    status: str
    error: str | None = None
    result: DocumentExtractResponse | None = None
    queued_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
