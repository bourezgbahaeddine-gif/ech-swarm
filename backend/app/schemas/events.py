from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class EventMemoCreateRequest(BaseModel):
    scope: str = Field(default="national", pattern="^(national|international|religious)$")
    title: str = Field(..., min_length=3, max_length=512)
    summary: str | None = None
    coverage_plan: str | None = None
    starts_at: datetime
    ends_at: datetime | None = None
    timezone: str = Field(default="Africa/Algiers", min_length=2, max_length=64)
    country_code: str | None = Field(default=None, max_length=8)
    is_all_day: bool = False
    lead_time_hours: int = Field(default=24, ge=1, le=336)
    priority: int = Field(default=3, ge=1, le=5)
    status: str = Field(default="planned", pattern="^(planned|monitoring|covered|dismissed)$")
    readiness_status: str = Field(default="idea", pattern="^(idea|assigned|prepared|ready|covered)$")
    source_url: str | None = Field(default=None, max_length=2048)
    tags: list[str] = Field(default_factory=list)
    checklist: list[str] = Field(default_factory=list)
    owner_user_id: int | None = Field(default=None, ge=1)


class EventMemoUpdateRequest(BaseModel):
    scope: str | None = Field(default=None, pattern="^(national|international|religious)$")
    title: str | None = Field(default=None, min_length=3, max_length=512)
    summary: str | None = None
    coverage_plan: str | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    timezone: str | None = Field(default=None, min_length=2, max_length=64)
    country_code: str | None = Field(default=None, max_length=8)
    is_all_day: bool | None = None
    lead_time_hours: int | None = Field(default=None, ge=1, le=336)
    priority: int | None = Field(default=None, ge=1, le=5)
    status: str | None = Field(default=None, pattern="^(planned|monitoring|covered|dismissed)$")
    readiness_status: str | None = Field(default=None, pattern="^(idea|assigned|prepared|ready|covered)$")
    source_url: str | None = Field(default=None, max_length=2048)
    tags: list[str] | None = None
    checklist: list[str] | None = None
    owner_user_id: int | None = Field(default=None, ge=1)
    preparation_started_at: datetime | None = None


class EventMemoResponse(BaseModel):
    id: int
    scope: str
    title: str
    summary: str | None = None
    coverage_plan: str | None = None
    starts_at: datetime
    ends_at: datetime | None = None
    timezone: str
    country_code: str | None = None
    is_all_day: bool
    lead_time_hours: int
    priority: int
    status: str
    readiness_status: str
    source_url: str | None = None
    tags: list[str] = Field(default_factory=list)
    checklist: list[str] = Field(default_factory=list)
    prep_starts_at: datetime
    is_due_soon: bool
    is_overdue: bool
    preparation_started_at: datetime | None = None
    owner_user_id: int | None = None
    owner_username: str | None = None
    created_by_user_id: int | None = None
    created_by_username: str | None = None
    updated_by_user_id: int | None = None
    updated_by_username: str | None = None
    created_at: datetime
    updated_at: datetime


class EventMemoListResponse(BaseModel):
    items: list[EventMemoResponse]
    total: int
    page: int
    per_page: int
    pages: int


class EventMemoOverviewResponse(BaseModel):
    window_days: int
    total: int
    upcoming_24h: int
    upcoming_7d: int
    overdue: int
    by_scope: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    reminders: dict[str, int] = Field(default_factory=dict)
    kpi: dict[str, float | int] = Field(default_factory=dict)


class EventMemoRemindersResponse(BaseModel):
    t24: list[EventMemoResponse] = Field(default_factory=list)
    t6: list[EventMemoResponse] = Field(default_factory=list)
