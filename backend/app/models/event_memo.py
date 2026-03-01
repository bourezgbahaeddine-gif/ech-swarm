"""
Event memo board models.
Tracks national/international/religious events that need proactive coverage.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, JSON, String, Text

from app.core.database import Base


class EventMemoItem(Base):
    __tablename__ = "event_memo_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    scope = Column(String(24), nullable=False, default="national", index=True)
    title = Column(String(512), nullable=False)
    summary = Column(Text, nullable=True)
    coverage_plan = Column(Text, nullable=True)
    starts_at = Column(DateTime, nullable=False, index=True)
    ends_at = Column(DateTime, nullable=True)
    timezone = Column(String(64), nullable=False, default="Africa/Algiers")
    country_code = Column(String(8), nullable=True)
    is_all_day = Column(Boolean, nullable=False, default=False)
    lead_time_hours = Column(Integer, nullable=False, default=24)
    priority = Column(Integer, nullable=False, default=3)
    status = Column(String(24), nullable=False, default="planned", index=True)
    source_url = Column(String(2048), nullable=True)
    tags = Column(JSON, default=list)

    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    created_by_username = Column(String(64), nullable=True)
    updated_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    updated_by_username = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_event_memo_scope_status_start", "scope", "status", "starts_at"),
        Index("ix_event_memo_status_start", "status", "starts_at"),
    )

