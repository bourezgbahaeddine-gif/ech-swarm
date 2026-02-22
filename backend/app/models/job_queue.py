"""Async job queue tracking models."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Column, DateTime, Index, Integer, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class JobRun(Base):
    __tablename__ = "job_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    job_type = Column(String(64), nullable=False, index=True)
    queue_name = Column(String(64), nullable=False, index=True)
    entity_id = Column(String(64), nullable=True, index=True)
    status = Column(String(24), nullable=False, default="queued", index=True)  # queued|running|completed|failed|dead_lettered
    priority = Column(String(16), nullable=False, default="normal")
    request_id = Column(String(64), nullable=True, index=True)
    correlation_id = Column(String(64), nullable=True, index=True)
    actor_user_id = Column(Integer, nullable=True, index=True)
    actor_username = Column(String(64), nullable=True)
    attempt = Column(Integer, nullable=False, default=0)
    max_attempts = Column(Integer, nullable=False, default=5)
    queued_at = Column(DateTime, default=datetime.utcnow, index=True)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    error = Column(Text, nullable=True)
    payload_json = Column(JSON, nullable=False, default=dict)
    result_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, index=True)

    __table_args__ = (
        Index("ix_job_runs_queue_status", "queue_name", "status"),
        Index("ix_job_runs_type_queued", "job_type", "queued_at"),
    )


class DeadLetterJob(Base):
    __tablename__ = "dead_letter_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    original_job_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    job_type = Column(String(64), nullable=False, index=True)
    queue_name = Column(String(64), nullable=False, index=True)
    failed_at = Column(DateTime, default=datetime.utcnow, index=True)
    error = Column(Text, nullable=False)
    traceback = Column(Text, nullable=True)
    payload_json = Column(JSON, nullable=False, default=dict)
    meta_json = Column(JSON, nullable=False, default=dict)

