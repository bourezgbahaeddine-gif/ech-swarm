from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class MemoryCreateRequest(BaseModel):
    memory_type: str = Field(default="operational", pattern="^(operational|knowledge|session)$")
    title: str = Field(..., min_length=3, max_length=512)
    content: str = Field(..., min_length=10)
    tags: list[str] = Field(default_factory=list)
    source_type: str | None = Field(default=None, max_length=64)
    source_ref: str | None = Field(default=None, max_length=512)
    article_id: int | None = None
    importance: int = Field(default=3, ge=1, le=5)


class MemoryUpdateRequest(BaseModel):
    memory_type: str | None = Field(default=None, pattern="^(operational|knowledge|session)$")
    title: str | None = Field(default=None, min_length=3, max_length=512)
    content: str | None = Field(default=None, min_length=10)
    tags: list[str] | None = None
    source_type: str | None = Field(default=None, max_length=64)
    source_ref: str | None = Field(default=None, max_length=512)
    article_id: int | None = None
    importance: int | None = Field(default=None, ge=1, le=5)
    status: str | None = Field(default=None, pattern="^(active|archived)$")


class MemoryEventResponse(BaseModel):
    id: int
    memory_id: int
    event_type: str
    note: str | None = None
    actor_user_id: int | None = None
    actor_username: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class MemoryItemResponse(BaseModel):
    id: int
    memory_type: str
    title: str
    content: str
    tags: list[str]
    source_type: str | None = None
    source_ref: str | None = None
    article_id: int | None = None
    status: str
    importance: int
    created_by_user_id: int | None = None
    created_by_username: str | None = None
    updated_by_user_id: int | None = None
    updated_by_username: str | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MemoryListResponse(BaseModel):
    items: list[MemoryItemResponse]
    total: int
    page: int
    per_page: int
    pages: int


class MemoryOverviewResponse(BaseModel):
    total_active: int = 0
    operational_count: int = 0
    knowledge_count: int = 0
    session_count: int = 0
    archived_count: int = 0
    recent_updates: int = 0
