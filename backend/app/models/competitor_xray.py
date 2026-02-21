"""Competitor X-Ray models.

Tracks competitor monitoring sources, scan runs, detected coverage gaps,
and explainability events.
"""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text

from app.core.database import Base


class CompetitorXraySource(Base):
    __tablename__ = "competitor_xray_sources"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(120), nullable=False)
    feed_url = Column(String(2048), nullable=False, unique=True, index=True)
    domain = Column(String(255), nullable=False, index=True)
    language = Column(String(16), nullable=False, default="ar")
    weight = Column(Float, nullable=False, default=1.0)
    enabled = Column(Boolean, nullable=False, default=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, index=True)


class CompetitorXrayRun(Base):
    __tablename__ = "competitor_xray_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(64), nullable=False, unique=True, index=True)
    status = Column(String(24), nullable=False, default="queued", index=True)  # queued|running|completed|failed
    total_scanned = Column(Integer, nullable=False, default=0)
    total_gaps = Column(Integer, nullable=False, default=0)
    idempotency_key = Column(String(128), nullable=True, index=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    created_by_username = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    finished_at = Column(DateTime, nullable=True)
    error = Column(Text, nullable=True)

    __table_args__ = (
        Index("ix_competitor_xray_runs_status_created", "status", "created_at"),
    )


class CompetitorXrayItem(Base):
    __tablename__ = "competitor_xray_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(64), ForeignKey("competitor_xray_runs.run_id", ondelete="CASCADE"), nullable=False, index=True)
    source_id = Column(Integer, ForeignKey("competitor_xray_sources.id", ondelete="SET NULL"), nullable=True, index=True)
    competitor_title = Column(String(1024), nullable=False)
    competitor_url = Column(String(2048), nullable=False, index=True)
    competitor_summary = Column(Text, nullable=True)
    published_at = Column(DateTime, nullable=True, index=True)
    priority_score = Column(Float, nullable=False, default=0.0, index=True)
    status = Column(String(24), nullable=False, default="new", index=True)  # new|used|ignored
    angle_title = Column(String(512), nullable=True)
    angle_rationale = Column(Text, nullable=True)
    angle_questions_json = Column(JSON, nullable=False, default=list)
    starter_sources_json = Column(JSON, nullable=False, default=list)
    matched_article_id = Column(Integer, ForeignKey("articles.id"), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, index=True)

    __table_args__ = (
        Index("ix_competitor_xray_items_priority_created", "priority_score", "created_at"),
    )


class CompetitorXrayEvent(Base):
    __tablename__ = "competitor_xray_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(64), ForeignKey("competitor_xray_runs.run_id", ondelete="CASCADE"), nullable=False, index=True)
    node = Column(String(64), nullable=False, index=True)
    event_type = Column(String(32), nullable=False, index=True)  # started|finished|failed|state_update
    payload_json = Column(JSON, nullable=False, default=dict)
    ts = Column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index("ix_competitor_xray_events_run_ts", "run_id", "ts"),
    )
