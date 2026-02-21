"""Competitor X-Ray API schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class CompetitorXraySourceCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    feed_url: str = Field(..., min_length=8, max_length=2048)
    domain: str = Field(..., min_length=3, max_length=255)
    language: str = Field(default="ar", min_length=2, max_length=16)
    weight: float = Field(default=1.0, ge=0.1, le=3.0)
    enabled: bool = True


class CompetitorXraySourceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    language: str | None = Field(default=None, min_length=2, max_length=16)
    weight: float | None = Field(default=None, ge=0.1, le=3.0)
    enabled: bool | None = None


class CompetitorXraySourceResponse(BaseModel):
    id: int
    name: str
    feed_url: str
    domain: str
    language: str
    weight: float
    enabled: bool
    created_at: datetime
    updated_at: datetime


class CompetitorXrayRunRequest(BaseModel):
    limit_per_source: int = Field(default=8, ge=1, le=30)
    hours_window: int = Field(default=48, ge=6, le=120)
    idempotency_key: str | None = Field(default=None, max_length=128)


class CompetitorXrayRunResponse(BaseModel):
    run_id: str
    status: str
    created_at: datetime


class CompetitorXrayRunStatusResponse(BaseModel):
    run_id: str
    status: str
    total_scanned: int
    total_gaps: int
    created_at: datetime
    finished_at: datetime | None = None
    error: str | None = None


class CompetitorXrayItemResponse(BaseModel):
    id: int
    run_id: str
    source_id: int | None = None
    competitor_title: str
    competitor_url: str
    competitor_summary: str | None = None
    published_at: datetime | None = None
    priority_score: float
    status: str
    angle_title: str | None = None
    angle_rationale: str | None = None
    angle_questions_json: list[str]
    starter_sources_json: list[str]
    matched_article_id: int | None = None
    created_at: datetime
    updated_at: datetime


class CompetitorXrayBriefRequest(BaseModel):
    item_id: int
    tone: str = Field(default="newsroom", max_length=32)


class CompetitorXrayBriefResponse(BaseModel):
    item_id: int
    title: str
    counter_angle: str
    why_it_wins: str
    newsroom_plan: list[str]
    starter_sources: list[str]
