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
    playbook_key: str = Field(default="general", min_length=2, max_length=32)
    story_id: int | None = Field(default=None, ge=1)


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
    playbook_key: str | None = Field(default=None, min_length=2, max_length=32)
    story_id: int | None = Field(default=None, ge=1)


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
    playbook_key: str
    story_id: int | None = None
    story_key: str | None = None
    story_title: str | None = None
    prep_starts_at: datetime
    is_due_soon: bool
    is_overdue: bool
    readiness_score: int = 0
    readiness_breakdown: dict[str, int] = Field(default_factory=dict)
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


class EventActionItem(BaseModel):
    code: str
    severity: str
    title: str
    recommendation: str
    action: str
    event: EventMemoResponse


class EventActionItemsResponse(BaseModel):
    total: int
    high: int
    medium: int
    low: int
    items: list[EventActionItem] = Field(default_factory=list)


class EventCoverageResponse(BaseModel):
    event_id: int
    story_id: int | None = None
    story_key: str | None = None
    story_title: str | None = None
    coverage_score: int = 0
    readiness_score: int = 0
    readiness_breakdown: dict[str, int] = Field(default_factory=dict)
    metrics: dict[str, int] = Field(default_factory=dict)
    timeline: list[dict] = Field(default_factory=list)
    next_action: str | None = None


class EventLinkStoryRequest(BaseModel):
    story_id: int | None = Field(default=None, ge=1)
    create_if_missing: bool = False
    title: str | None = Field(default=None, min_length=4, max_length=1024)
    summary: str | None = Field(default=None, max_length=4000)
    category: str | None = Field(default=None, max_length=80)
    geography: str | None = Field(default=None, max_length=24)


class EventAutomationRunResponse(BaseModel):
    event_id: int
    story_created: bool = False
    story_linked: bool = False
    status_updated: bool = False
    readiness_updated: bool = False
    actions: list[str] = Field(default_factory=list)


class EventPlaybookTemplate(BaseModel):
    key: str
    label: str
    checklist: list[str] = Field(default_factory=list)
    timeline: list[str] = Field(default_factory=list)
