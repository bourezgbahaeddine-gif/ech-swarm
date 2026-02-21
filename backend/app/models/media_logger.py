"""
Media Logger models.
Transcript runs, segments, highlights, and live job events.
"""

from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text

from app.core.database import Base


class MediaLoggerRun(Base):
    __tablename__ = "media_logger_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(64), nullable=False, unique=True, index=True)
    source_type = Column(String(16), nullable=False, default="url", index=True)  # url|upload
    source_ref = Column(Text, nullable=False)  # URL or local file path
    source_label = Column(String(255), nullable=True)  # Friendly source label (filename/title)
    language_hint = Column(String(16), nullable=False, default="ar")
    status = Column(String(24), nullable=False, default="queued", index=True)  # queued|running|completed|failed
    transcript_language = Column(String(16), nullable=True)
    transcript_text = Column(Text, nullable=True)
    duration_seconds = Column(Float, nullable=True)
    segments_count = Column(Integer, nullable=False, default=0)
    highlights_count = Column(Integer, nullable=False, default=0)
    idempotency_key = Column(String(128), nullable=True, index=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    created_by_username = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    finished_at = Column(DateTime, nullable=True)
    error = Column(Text, nullable=True)

    __table_args__ = (
        Index("ix_media_logger_runs_status_created", "status", "created_at"),
    )


class MediaLoggerSegment(Base):
    __tablename__ = "media_logger_segments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(64), ForeignKey("media_logger_runs.run_id", ondelete="CASCADE"), nullable=False, index=True)
    segment_index = Column(Integer, nullable=False, index=True)
    start_sec = Column(Float, nullable=False)
    end_sec = Column(Float, nullable=False)
    text = Column(Text, nullable=False)
    confidence = Column(Float, nullable=True)
    speaker = Column(String(32), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index("ix_media_logger_segments_run_order", "run_id", "segment_index"),
        Index("ix_media_logger_segments_run_start", "run_id", "start_sec"),
    )


class MediaLoggerHighlight(Base):
    __tablename__ = "media_logger_highlights"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(64), ForeignKey("media_logger_runs.run_id", ondelete="CASCADE"), nullable=False, index=True)
    rank = Column(Integer, nullable=False, default=1)
    quote = Column(Text, nullable=False)
    reason = Column(String(255), nullable=True)
    start_sec = Column(Float, nullable=False)
    end_sec = Column(Float, nullable=False)
    confidence = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index("ix_media_logger_highlights_run_rank", "run_id", "rank"),
    )


class MediaLoggerJobEvent(Base):
    __tablename__ = "media_logger_job_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(64), ForeignKey("media_logger_runs.run_id", ondelete="CASCADE"), nullable=False, index=True)
    node = Column(String(64), nullable=False, index=True)
    event_type = Column(String(32), nullable=False, index=True)  # started|finished|failed|state_update
    payload_json = Column(JSON, nullable=False, default=dict)
    ts = Column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index("ix_media_logger_job_events_run_ts", "run_id", "ts"),
    )
