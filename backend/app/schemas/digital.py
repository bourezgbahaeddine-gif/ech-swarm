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
    story_id: int | None = None
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
    story_id: int | None = Field(default=None, ge=1)


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
    story_id: int | None = Field(default=None, ge=1)


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
    versions_count: int = 0


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
    version_note: str | None = Field(default=None, max_length=4000)


class SocialPostListResponse(BaseModel):
    items: list[SocialPostResponse]
    total: int


class SocialPostVersionResponse(BaseModel):
    id: int
    post_id: int
    version_no: int
    version_type: str
    content_text: str
    hashtags: list[str] = Field(default_factory=list)
    media_urls: list[str] = Field(default_factory=list)
    note: str | None = None
    created_by_username: str | None = None
    created_at: datetime


class SocialPostVersionListResponse(BaseModel):
    items: list[SocialPostVersionResponse]
    total: int


class SocialPostVersionDuplicateRequest(BaseModel):
    source_version_no: int | None = Field(default=None, ge=1)
    version_type: str = Field(default="duplicated", max_length=32)
    note: str | None = Field(default=None, max_length=4000)


class SocialPostCompareResponse(BaseModel):
    post_id: int
    base_version_no: int
    target_version_no: int
    base_length: int
    target_length: int
    length_delta: int
    hashtags_added: list[str] = Field(default_factory=list)
    hashtags_removed: list[str] = Field(default_factory=list)
    media_added: list[str] = Field(default_factory=list)
    media_removed: list[str] = Field(default_factory=list)
    changed: bool = False


class DigitalEngagementScoreResponse(BaseModel):
    post_id: int
    platform: str
    score: int
    signals: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)


class DigitalPlaybookTemplate(BaseModel):
    key: str
    label: str
    objective: str
    platforms: list[str] = Field(default_factory=list)
    max_length_hint: dict[str, int] = Field(default_factory=dict)
    cta_style: str | None = None
    include_hashtags: bool = True
    include_media_slot: bool = False


class DigitalBundleGenerateRequest(BaseModel):
    playbook_key: str = Field(default="breaking_alert", max_length=64)
    save_as_posts: bool = True


class DigitalBundleGenerateResponse(BaseModel):
    task_id: int
    playbook_key: str
    generated_count: int
    created_post_ids: list[int] = Field(default_factory=list)
    variants: dict[str, str] = Field(default_factory=dict)
    hashtags: list[str] = Field(default_factory=list)


class DigitalDispatchRequest(BaseModel):
    adapter: str = Field(default="manual", max_length=32)
    action: str = Field(default="publish", pattern="^(publish|schedule)$")
    scheduled_at: datetime | None = None
    published_url: str | None = Field(default=None, max_length=2048)
    external_post_id: str | None = Field(default=None, max_length=128)


class DigitalDispatchResponse(BaseModel):
    post_id: int
    adapter: str
    action: str
    status: str
    dispatched_at: datetime
    message: str


class DigitalScopePerformanceItem(BaseModel):
    user_id: int | None = None
    username: str | None = None
    can_manage_news: bool = False
    can_manage_tv: bool = False
    total_tasks: int = 0
    active_tasks: int = 0
    overdue_tasks: int = 0
    done_tasks: int = 0
    failed_posts: int = 0
    published_posts: int = 0
    on_time_rate: float = 0.0


class DigitalScopePerformanceResponse(BaseModel):
    items: list[DigitalScopePerformanceItem] = Field(default_factory=list)
    total: int = 0


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


class DigitalComposeRequest(BaseModel):
    platform: str = Field(default="facebook", min_length=1, max_length=32)
    max_hashtags: int = Field(default=6, ge=1, le=12)


class DigitalComposeResponse(BaseModel):
    task_id: int
    platform: str
    recommended_text: str
    hashtags: list[str] = Field(default_factory=list)
    variants: dict[str, str] = Field(default_factory=dict)
    source: dict


class DigitalTaskActionItem(BaseModel):
    task: SocialTaskResponse
    next_best_action_code: str
    next_best_action: str
    why_now: str
    source_type: str
    source_ref: str | None = None
    auto_generated: bool = False
    trigger_window: str | None = None
    risk_flags: list[str] = Field(default_factory=list)


class DigitalActionDeskResponse(BaseModel):
    now: list[DigitalTaskActionItem] = Field(default_factory=list)
    next: list[DigitalTaskActionItem] = Field(default_factory=list)
    at_risk: list[DigitalTaskActionItem] = Field(default_factory=list)
    now_count: int = 0
    next_count: int = 0
    at_risk_count: int = 0


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
