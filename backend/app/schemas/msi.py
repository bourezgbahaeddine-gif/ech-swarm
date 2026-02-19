"""MSI API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class MsiProfileInfo(BaseModel):
    id: str
    display_name: str
    description: str | None = None


class MsiRunRequest(BaseModel):
    profile_id: str = Field(min_length=2, max_length=64)
    entity: str = Field(min_length=2, max_length=255)
    mode: Literal["daily", "weekly"]
    start: datetime | None = None
    end: datetime | None = None


class MsiRunResponse(BaseModel):
    run_id: str
    status: str
    profile_id: str
    entity: str
    mode: str
    start: datetime
    end: datetime


class MsiRunStatusResponse(BaseModel):
    run_id: str
    status: str
    error: str | None = None
    created_at: datetime
    finished_at: datetime | None = None


class MsiReportResponse(BaseModel):
    run_id: str
    profile_id: str
    entity: str
    mode: str
    period_start: datetime
    period_end: datetime
    msi: float
    level: str
    drivers: list[dict[str, Any]]
    top_negative_items: list[dict[str, Any]]
    topic_shift: dict[str, Any]
    explanation: str
    components: dict[str, Any]


class MsiTimeseriesPoint(BaseModel):
    ts: datetime
    msi: float
    level: str
    components: dict[str, Any] = Field(default_factory=dict)


class MsiTimeseriesResponse(BaseModel):
    profile_id: str
    entity: str
    mode: str
    points: list[MsiTimeseriesPoint]


class MsiTopEntityItem(BaseModel):
    profile_id: str
    entity: str
    mode: str
    msi: float
    level: str
    period_end: datetime


class MsiTopResponse(BaseModel):
    mode: str
    items: list[MsiTopEntityItem]


class MsiWatchlistCreateRequest(BaseModel):
    profile_id: str = Field(min_length=2, max_length=64)
    entity: str = Field(min_length=2, max_length=255)
    run_daily: bool = True
    run_weekly: bool = True
    enabled: bool = True


class MsiWatchlistUpdateRequest(BaseModel):
    run_daily: bool | None = None
    run_weekly: bool | None = None
    enabled: bool | None = None


class MsiWatchlistItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    profile_id: str
    entity: str
    enabled: bool
    run_daily: bool
    run_weekly: bool
    created_by_username: str | None = None
    created_at: datetime
    updated_at: datetime


class MsiLiveEvent(BaseModel):
    id: int
    run_id: str
    node: str
    event_type: str
    payload_json: dict[str, Any]
    ts: datetime
