from __future__ import annotations

from datetime import date, datetime, time

from pydantic import BaseModel, Field


class DigitalTeamScopeResponse(BaseModel):
    id: int
    user_id: int
    username: str | None = None
    full_name_ar: str | None = None
    can_manage_news: bool
    can_manage_tv: bool
    platforms: list[str] = Field(default_factory=list)
    notes: str | None = None
    created_at: datetime
    updated_at: datetime


class DigitalTeamScopeUpsertRequest(BaseModel):
    can_manage_news: bool = True
    can_manage_tv: bool = False
    platforms: list[str] = Field(default_factory=lambda: ["facebook", "x", "youtube"])
    notes: str | None = Field(default=None, max_length=2000)


class ProgramSlotResponse(BaseModel):
    id: int
    channel: str
    program_title: str
    program_type: str | None = None
    description: str | None = None
    day_of_week: int | None = None
    start_time: time
    duration_minutes: int
    timezone: str
    priority: int
    is_active: bool
    social_focus: str | None = None
    tags: list[str] = Field(default_factory=list)
    source_ref: str | None = None
    created_at: datetime
    updated_at: datetime


class ProgramSlotCreateRequest(BaseModel):
    channel: str = Field(..., pattern="^(news|tv)$")
    program_title: str = Field(..., min_length=2, max_length=255)
    program_type: str | None = Field(default=None, max_length=64)
    description: str | None = Field(default=None, max_length=4000)
    day_of_week: int | None = Field(default=None, ge=0, le=6)
    start_time: str = Field(..., pattern="^([01]\\d|2[0-3]):[0-5]\\d$")
    duration_minutes: int = Field(default=60, ge=5, le=480)
    timezone: str = Field(default="Africa/Algiers", min_length=2, max_length=64)
    priority: int = Field(default=3, ge=1, le=5)
    is_active: bool = True
    social_focus: str | None = Field(default=None, max_length=4000)
    tags: list[str] = Field(default_factory=list)
    source_ref: str | None = Field(default=None, max_length=2048)


class ProgramSlotUpdateRequest(BaseModel):
    program_title: str | None = Field(default=None, min_length=2, max_length=255)
    program_type: str | None = Field(default=None, max_length=64)
    description: str | None = Field(default=None, max_length=4000)
    day_of_week: int | None = Field(default=None, ge=0, le=6)
    start_time: str | None = Field(default=None, pattern="^([01]\\d|2[0-3]):[0-5]\\d$")
    duration_minutes: int | None = Field(default=None, ge=5, le=480)
    timezone: str | None = Field(default=None, min_length=2, max_length=64)
    priority: int | None = Field(default=None, ge=1, le=5)
    is_active: bool | None = None
    social_focus: str | None = Field(default=None, max_length=4000)
    tags: list[str] | None = None
    source_ref: str | None = Field(default=None, max_length=2048)


class SocialTaskResponse(BaseModel):
    id: int
    channel: str
    platform: str
    task_type: str
    title: str
    brief: str | None = None
    status: str
    priority: int
    due_at: datetime | None = None
    scheduled_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    dedupe_key: str | None = None
    program_slot_id: int | None = None
    event_id: int | None = None
    article_id: int | None = None
    owner_user_id: int | None = None
    owner_username: str | None = None
    published_posts_count: int
    last_published_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class SocialTaskCreateRequest(BaseModel):
    channel: str = Field(..., pattern="^(news|tv)$")
    platform: str = Field(default="all", max_length=32)
    task_type: str = Field(default="manual", max_length=32)
    title: str = Field(..., min_length=3, max_length=512)
    brief: str | None = Field(default=None, max_length=8000)
    priority: int = Field(default=3, ge=1, le=5)
    due_at: datetime | None = None
    scheduled_at: datetime | None = None
    owner_user_id: int | None = Field(default=None, ge=1)
    program_slot_id: int | None = Field(default=None, ge=1)
    event_id: int | None = Field(default=None, ge=1)
    article_id: int | None = Field(default=None, ge=1)


class SocialTaskUpdateRequest(BaseModel):
    platform: str | None = Field(default=None, max_length=32)
    task_type: str | None = Field(default=None, max_length=32)
    title: str | None = Field(default=None, min_length=3, max_length=512)
    brief: str | None = Field(default=None, max_length=8000)
    status: str | None = Field(default=None, pattern="^(todo|in_progress|review|done|cancelled)$")
    priority: int | None = Field(default=None, ge=1, le=5)
    due_at: datetime | None = None
    scheduled_at: datetime | None = None
    owner_user_id: int | None = Field(default=None, ge=1)


class SocialTaskListResponse(BaseModel):
    items: list[SocialTaskResponse]
    total: int
    page: int
    per_page: int
    pages: int


class SocialPostResponse(BaseModel):
    id: int
    task_id: int
    channel: str
    platform: str
    content_text: str
    hashtags: list[str] = Field(default_factory=list)
    media_urls: list[str] = Field(default_factory=list)
    status: str
    scheduled_at: datetime | None = None
    published_at: datetime | None = None
    published_url: str | None = None
    external_post_id: str | None = None
    error_message: str | None = None
    created_by_username: str | None = None
    updated_by_username: str | None = None
    created_at: datetime
    updated_at: datetime


class SocialPostCreateRequest(BaseModel):
    platform: str = Field(..., min_length=2, max_length=32)
    content_text: str = Field(..., min_length=2, max_length=10000)
    hashtags: list[str] = Field(default_factory=list)
    media_urls: list[str] = Field(default_factory=list)
    status: str = Field(default="draft", pattern="^(draft|ready|approved|scheduled|published|failed)$")
    scheduled_at: datetime | None = None
    published_url: str | None = Field(default=None, max_length=2048)
    external_post_id: str | None = Field(default=None, max_length=128)


class SocialPostUpdateRequest(BaseModel):
    content_text: str | None = Field(default=None, min_length=2, max_length=10000)
    hashtags: list[str] | None = None
    media_urls: list[str] | None = None
    status: str | None = Field(default=None, pattern="^(draft|ready|approved|scheduled|published|failed)$")
    scheduled_at: datetime | None = None
    published_at: datetime | None = None
    published_url: str | None = Field(default=None, max_length=2048)
    external_post_id: str | None = Field(default=None, max_length=128)
    error_message: str | None = Field(default=None, max_length=4000)


class SocialPostListResponse(BaseModel):
    items: list[SocialPostResponse]
    total: int


class DigitalOverviewResponse(BaseModel):
    total_tasks: int
    due_today: int
    overdue: int
    in_progress: int
    done_today: int
    by_channel: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    scheduled_posts_next_24h: int = 0
    published_posts_24h: int = 0
    on_time_rate: float = 0.0


class DigitalGenerationResponse(BaseModel):
    generated_program_tasks: int = 0
    generated_event_tasks: int = 0
    generated_breaking_tasks: int = 0
    total_generated: int = 0
    skipped_duplicates: int = 0


class DigitalCalendarItem(BaseModel):
    item_type: str
    channel: str
    title: str
    starts_at: datetime
    ends_at: datetime | None = None
    reference_id: int | None = None
    status: str | None = None
    priority: int | None = None
    source: str | None = None


class DigitalCalendarResponse(BaseModel):
    from_date: date
    days: int
    items: list[DigitalCalendarItem] = Field(default_factory=list)
