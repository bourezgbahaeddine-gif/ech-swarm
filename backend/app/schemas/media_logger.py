"""Media Logger API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class MediaLoggerRunFromUrlRequest(BaseModel):
    media_url: str = Field(..., min_length=10, max_length=2048)
    language_hint: Literal["ar", "fr", "en", "auto"] = "ar"
    idempotency_key: str | None = Field(default=None, max_length=128)


class MediaLoggerRunResponse(BaseModel):
    run_id: str
    status: str
    source_type: str
    source_label: str | None = None
    language_hint: str
    created_at: datetime


class MediaLoggerRunStatusResponse(BaseModel):
    run_id: str
    status: str
    transcript_language: str | None = None
    segments_count: int
    highlights_count: int
    duration_seconds: float | None = None
    error: str | None = None
    created_at: datetime
    finished_at: datetime | None = None


class MediaLoggerSegmentResponse(BaseModel):
    segment_index: int
    start_sec: float
    end_sec: float
    text: str
    confidence: float | None = None
    speaker: str | None = None


class MediaLoggerHighlightResponse(BaseModel):
    rank: int
    quote: str
    reason: str | None = None
    start_sec: float
    end_sec: float
    confidence: float | None = None


class MediaLoggerResultResponse(BaseModel):
    run_id: str
    status: str
    source_type: str
    source_label: str | None = None
    language_hint: str
    transcript_language: str | None = None
    transcript_text: str
    duration_seconds: float | None = None
    segments_count: int
    highlights_count: int
    highlights: list[MediaLoggerHighlightResponse]
    segments: list[MediaLoggerSegmentResponse]
    created_at: datetime
    finished_at: datetime | None = None


class MediaLoggerAskRequest(BaseModel):
    run_id: str = Field(..., min_length=8, max_length=64)
    question: str = Field(..., min_length=4, max_length=1000)


class MediaLoggerAskResponse(BaseModel):
    run_id: str
    answer: str
    quote: str
    start_sec: float
    end_sec: float
    confidence: float
    context: list[MediaLoggerSegmentResponse]
