from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, Index, JSON, String, Text

from app.core.database import Base


class TaskIdempotencyKey(Base):
    __tablename__ = "task_idempotency_keys"

    idempotency_key = Column(String(190), primary_key=True)
    task_name = Column(String(100), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="running", index=True)  # running|completed|failed
    first_job_id = Column(String(64), nullable=True, index=True)
    last_job_id = Column(String(64), nullable=True, index=True)
    result_json = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, index=True)

    __table_args__ = (
        Index("ix_task_idempotency_task_status", "task_name", "status"),
    )

