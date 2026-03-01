"""
Digital team operational models.
Tracks channel scope ownership, program grid, social tasks, and social posts.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    Time,
    UniqueConstraint,
)

from app.core.database import Base


class DigitalTeamScope(Base):
    __tablename__ = "digital_team_scopes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True, index=True)
    can_manage_news = Column(Boolean, nullable=False, default=True)
    can_manage_tv = Column(Boolean, nullable=False, default=False)
    platforms = Column(JSON, nullable=False, default=list)
    notes = Column(Text, nullable=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    updated_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class ProgramSlot(Base):
    __tablename__ = "program_slots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    channel = Column(String(16), nullable=False, index=True)  # news|tv
    program_title = Column(String(255), nullable=False)
    program_type = Column(String(64), nullable=True)
    description = Column(Text, nullable=True)
    day_of_week = Column(Integer, nullable=True, index=True)  # 0 Monday .. 6 Sunday
    start_time = Column(Time, nullable=False, index=True)
    duration_minutes = Column(Integer, nullable=False, default=60)
    timezone = Column(String(64), nullable=False, default="Africa/Algiers")
    priority = Column(Integer, nullable=False, default=3)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    social_focus = Column(Text, nullable=True)
    tags = Column(JSON, nullable=False, default=list)
    source_ref = Column(String(2048), nullable=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    updated_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "channel",
            "program_title",
            "day_of_week",
            "start_time",
            name="uq_program_slot_channel_title_day_time",
        ),
        CheckConstraint("channel IN ('news','tv')", name="ck_program_slots_channel"),
        CheckConstraint("(day_of_week IS NULL) OR (day_of_week >= 0 AND day_of_week <= 6)", name="ck_program_slots_day_of_week"),
        CheckConstraint("duration_minutes >= 5 AND duration_minutes <= 480", name="ck_program_slots_duration"),
        CheckConstraint("priority >= 1 AND priority <= 5", name="ck_program_slots_priority"),
        Index("ix_program_slots_channel_active_time", "channel", "is_active", "day_of_week", "start_time"),
    )


class SocialTask(Base):
    __tablename__ = "social_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    channel = Column(String(16), nullable=False, index=True)  # news|tv
    platform = Column(String(32), nullable=False, default="all", index=True)
    task_type = Column(String(32), nullable=False, default="manual", index=True)
    title = Column(String(512), nullable=False)
    brief = Column(Text, nullable=True)
    status = Column(String(24), nullable=False, default="todo", index=True)
    priority = Column(Integer, nullable=False, default=3)
    due_at = Column(DateTime, nullable=True, index=True)
    scheduled_at = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    dedupe_key = Column(String(255), nullable=True, unique=True, index=True)

    program_slot_id = Column(Integer, ForeignKey("program_slots.id"), nullable=True, index=True)
    event_id = Column(Integer, ForeignKey("event_memo_items.id"), nullable=True, index=True)
    article_id = Column(Integer, ForeignKey("articles.id"), nullable=True, index=True)

    owner_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    owner_username = Column(String(64), nullable=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_by_username = Column(String(64), nullable=True)
    updated_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    updated_by_username = Column(String(64), nullable=True)
    published_posts_count = Column(Integer, nullable=False, default=0)
    last_published_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        CheckConstraint("channel IN ('news','tv')", name="ck_social_tasks_channel"),
        CheckConstraint("status IN ('todo','in_progress','review','done','cancelled')", name="ck_social_tasks_status"),
        CheckConstraint("priority >= 1 AND priority <= 5", name="ck_social_tasks_priority"),
        Index("ix_social_tasks_status_due", "status", "due_at"),
        Index("ix_social_tasks_channel_status_due", "channel", "status", "due_at"),
        Index("ix_social_tasks_owner_status_due", "owner_user_id", "status", "due_at"),
    )


class SocialPost(Base):
    __tablename__ = "social_posts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, ForeignKey("social_tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    channel = Column(String(16), nullable=False, index=True)
    platform = Column(String(32), nullable=False, index=True)
    content_text = Column(Text, nullable=False)
    hashtags = Column(JSON, nullable=False, default=list)
    media_urls = Column(JSON, nullable=False, default=list)
    status = Column(String(24), nullable=False, default="draft", index=True)
    scheduled_at = Column(DateTime, nullable=True, index=True)
    published_at = Column(DateTime, nullable=True, index=True)
    published_url = Column(String(2048), nullable=True)
    external_post_id = Column(String(128), nullable=True)
    error_message = Column(Text, nullable=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_by_username = Column(String(64), nullable=True)
    updated_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    updated_by_username = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        CheckConstraint("channel IN ('news','tv')", name="ck_social_posts_channel"),
        CheckConstraint("status IN ('draft','ready','approved','scheduled','published','failed')", name="ck_social_posts_status"),
        Index("ix_social_posts_task_status", "task_id", "status"),
        Index("ix_social_posts_platform_status_scheduled", "platform", "status", "scheduled_at"),
    )
