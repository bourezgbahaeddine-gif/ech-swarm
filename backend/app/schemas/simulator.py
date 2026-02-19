"""Audience simulator API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class SimRunRequest(BaseModel):
    headline: str = Field(..., min_length=6, max_length=1024)
    excerpt: str | None = Field(default=None, max_length=3000)
    platform: Literal["facebook", "x"] = "facebook"
    article_id: int | None = None
    draft_id: int | None = None
    mode: Literal["fast", "deep"] = "fast"
    idempotency_key: str | None = Field(default=None, max_length=128)


class SimRunResponse(BaseModel):
    run_id: str
    status: str
    platform: str
    mode: str
    headline: str


class SimRunStatusResponse(BaseModel):
    run_id: str
    status: str
    error: str | None = None
    created_at: datetime
    finished_at: datetime | None = None


class SimReactionResponse(BaseModel):
    persona_id: str
    persona_label: str | None = None
    comment: str
    sentiment: str
    risk_signal: float
    virality_signal: float


class SimResultResponse(BaseModel):
    run_id: str
    status: str
    headline: str
    platform: str
    mode: str
    risk_score: float
    virality_score: float
    confidence_score: float
    breakdown: dict
    reactions: list[dict]
    advice: dict
    red_flags: dict
    policy_level: str
    created_at: str


class SimHistoryItem(BaseModel):
    run_id: str
    status: str
    headline: str
    platform: str
    mode: str
    created_at: str | None = None
    risk_score: float | None = None
    virality_score: float | None = None
    policy_level: str | None = None


class SimHistoryResponse(BaseModel):
    items: list[SimHistoryItem]
    total: int

