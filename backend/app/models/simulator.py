"""
Audience Simulator models.
"""

from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text

from app.core.database import Base


class SimRun(Base):
    __tablename__ = "sim_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(64), nullable=False, unique=True, index=True)
    article_id = Column(Integer, ForeignKey("articles.id"), nullable=True, index=True)
    draft_id = Column(Integer, ForeignKey("editorial_drafts.id"), nullable=True, index=True)
    headline = Column(String(1024), nullable=False)
    body_excerpt = Column(Text, nullable=True)
    platform = Column(String(16), nullable=False, default="facebook", index=True)  # facebook|x
    mode = Column(String(16), nullable=False, default="fast", index=True)  # fast|deep
    status = Column(String(24), nullable=False, default="queued", index=True)  # queued|running|completed|failed
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    created_by_username = Column(String(64), nullable=True)
    idempotency_key = Column(String(128), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    finished_at = Column(DateTime, nullable=True)
    error = Column(Text, nullable=True)

    __table_args__ = (
        Index("ix_sim_runs_status_created", "status", "created_at"),
    )


class SimResult(Base):
    __tablename__ = "sim_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(64), ForeignKey("sim_runs.run_id", ondelete="CASCADE"), nullable=False, index=True)
    risk_score = Column(Float, nullable=False)
    virality_score = Column(Float, nullable=False)
    confidence_score = Column(Float, nullable=False, default=0.0)
    breakdown_json = Column(JSON, nullable=False, default=dict)
    reactions_json = Column(JSON, nullable=False, default=list)
    advice_json = Column(JSON, nullable=False, default=dict)
    red_flags_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class SimFeedback(Base):
    __tablename__ = "sim_feedback"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(64), ForeignKey("sim_runs.run_id", ondelete="CASCADE"), nullable=False, index=True)
    action = Column(String(32), nullable=False, index=True)  # accept|edit|ignore
    editor_notes = Column(Text, nullable=True)
    editor_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    editor_username = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class SimCalibration(Base):
    __tablename__ = "sim_calibration"

    id = Column(Integer, primary_key=True, autoincrement=True)
    platform = Column(String(16), nullable=False, index=True)
    bucket = Column(String(32), nullable=False, index=True)
    actual_ctr = Column(Float, nullable=True)
    actual_backlash = Column(Float, nullable=True)
    actual_shares = Column(Float, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, index=True)


class SimJobEvent(Base):
    __tablename__ = "sim_job_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(64), ForeignKey("sim_runs.run_id", ondelete="CASCADE"), nullable=False, index=True)
    node = Column(String(64), nullable=False, index=True)
    event_type = Column(String(32), nullable=False, index=True)  # started|finished|failed|state_update
    payload_json = Column(JSON, nullable=False, default=dict)
    ts = Column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index("ix_sim_job_events_run_ts", "run_id", "ts"),
    )
