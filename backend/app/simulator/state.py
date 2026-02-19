"""Audience simulator LangGraph state models."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class PersonaReaction(BaseModel):
    persona_id: str
    persona_label: str
    comment: str
    sentiment: Literal["Negative", "Neutral", "Positive", "Funny"] = "Neutral"
    risk_signal: float = 0.0  # 0..1
    virality_signal: float = 0.0  # 0..1


class SimulationBreakdown(BaseModel):
    risk: dict[str, float] = Field(
        default_factory=lambda: {
            "clickbait": 0.0,
            "legal": 0.0,
            "values": 0.0,
            "polarization": 0.0,
            "misinfo": 0.0,
        }
    )
    virality: dict[str, float] = Field(
        default_factory=lambda: {
            "emotion": 0.0,
            "clarity": 0.0,
            "novelty": 0.0,
            "meme": 0.0,
            "simplicity": 0.0,
        }
    )


class SimulationAdvice(BaseModel):
    summary: str = ""
    improvements: list[str] = Field(default_factory=list)
    alternative_headlines: list[str] = Field(default_factory=list)


class SimulationResult(BaseModel):
    risk_score: float = 1.0
    virality_score: float = 1.0
    confidence_score: float = 0.0
    breakdown: SimulationBreakdown = Field(default_factory=SimulationBreakdown)
    red_flags: dict[str, float] = Field(default_factory=dict)
    policy_level: Literal["LOW_RISK", "REVIEW_RECOMMENDED", "HIGH_RISK"] = "LOW_RISK"


class SimulationState(BaseModel):
    run_id: str
    headline: str
    body_excerpt: str = ""
    platform: Literal["facebook", "x"] = "facebook"
    mode: Literal["fast", "deep"] = "fast"
    article_id: int | None = None
    draft_id: int | None = None
    created_by_username: str | None = None

    profile_id: str = "dz_newsroom_v1"
    profile: dict[str, Any] = Field(default_factory=dict)
    personas: list[dict[str, Any]] = Field(default_factory=list)
    policy_rules: dict[str, Any] = Field(default_factory=dict)

    sanitized_headline: str = ""
    sanitized_excerpt: str = ""
    sanitized_context: dict[str, Any] = Field(default_factory=dict)

    reactions: list[PersonaReaction] = Field(default_factory=list)
    result: SimulationResult = Field(default_factory=SimulationResult)
    advice: SimulationAdvice = Field(default_factory=SimulationAdvice)
    report: dict[str, Any] = Field(default_factory=dict)

    metrics: dict[str, Any] = Field(default_factory=dict)
    errors: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
