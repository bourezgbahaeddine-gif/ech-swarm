"""Document Intelligence API schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class DocumentExtractNewsItem(BaseModel):
    rank: int
    headline: str
    summary: str
    evidence: str
    confidence: float = Field(ge=0.0, le=1.0)
    entities: list[str] = Field(default_factory=list)


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
    headings: list[str] = Field(default_factory=list)
    news_candidates: list[DocumentExtractNewsItem] = Field(default_factory=list)
    data_points: list[DocumentExtractDataPoint] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    preview_text: str = ""
