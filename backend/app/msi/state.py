"""MSI LangGraph state models."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class MSICollectedItem(BaseModel):
    title: str
    url: str
    source: str | None = None
    published_at: datetime | None = None
    summary: str | None = None
    content: str | None = None
    language: str | None = None
    domain: str | None = None


class MSIAnalyzedItem(MSICollectedItem):
    tone: float = 0.0  # -1..1
    intensity: float = 0.2  # 0..1
    novelty: float = 0.0  # 0..1
    propagation: float = 0.2  # 0..1
    topics: list[str] = Field(default_factory=list)
    is_negative: bool = False
    llm_failed: bool = False
    source_weight: float = 0.6


class MSIAggregates(BaseModel):
    total_items: int = 0
    unique_sources: int = 0
    llm_failure_ratio: float = 0.0
    pressure: float = 0.0
    shock: float = 0.0
    novelty: float = 0.0
    topic_volatility: float = 0.0
    topic_distribution: dict[str, float] = Field(default_factory=dict)
    top_negative_items: list[dict[str, Any]] = Field(default_factory=list)


class MSIComputed(BaseModel):
    msi: float = 100.0
    level: Literal["GREEN", "YELLOW", "ORANGE", "RED"] = "GREEN"
    components: dict[str, float] = Field(default_factory=dict)
    instability: float = 0.0


class MSIState(BaseModel):
    run_id: str
    profile_id: str
    entity: str
    mode: Literal["daily", "weekly"]
    period_start: datetime
    period_end: datetime
    timezone: str = "Africa/Algiers"
    watchlist_aliases: list[str] = Field(default_factory=list)

    profile: dict[str, Any] = Field(default_factory=dict)
    queries: list[str] = Field(default_factory=list)
    collected_items: list[MSICollectedItem] = Field(default_factory=list)
    analyzed_items: list[MSIAnalyzedItem] = Field(default_factory=list)
    aggregates: MSIAggregates = Field(default_factory=MSIAggregates)
    computed: MSIComputed = Field(default_factory=MSIComputed)
    baseline: dict[str, Any] = Field(default_factory=dict)
    report: dict[str, Any] = Field(default_factory=dict)

    errors: list[dict[str, Any]] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
