"""
MSI (Media Stability Index) models.
"""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint

from app.core.database import Base


class MsiRun(Base):
    __tablename__ = "msi_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(64), nullable=False, unique=True, index=True)
    profile_id = Column(String(64), nullable=False, index=True)
    entity = Column(String(255), nullable=False, index=True)
    mode = Column(String(16), nullable=False, index=True)  # daily|weekly
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    timezone = Column(String(64), nullable=False, default="Africa/Algiers")
    status = Column(String(24), nullable=False, default="queued", index=True)  # queued|running|completed|failed
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_by_username = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    finished_at = Column(DateTime, nullable=True)
    error = Column(Text, nullable=True)


class MsiReport(Base):
    __tablename__ = "msi_reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(64), ForeignKey("msi_runs.run_id", ondelete="CASCADE"), nullable=False, index=True)
    report_json = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class MsiTimeseries(Base):
    __tablename__ = "msi_timeseries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    profile_id = Column(String(64), nullable=False, index=True)
    entity = Column(String(255), nullable=False, index=True)
    mode = Column(String(16), nullable=False, index=True)
    period_end = Column(DateTime, nullable=False, index=True)
    msi = Column(Float, nullable=False)
    level = Column(String(16), nullable=False)
    components_json = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        UniqueConstraint("profile_id", "entity", "mode", "period_end", name="uq_msi_timeseries_point"),
        Index("ix_msi_timeseries_lookup", "profile_id", "entity", "mode", "period_end"),
    )


class MsiArtifact(Base):
    __tablename__ = "msi_artifacts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(64), ForeignKey("msi_runs.run_id", ondelete="CASCADE"), nullable=False, index=True)
    items_json = Column(JSON, nullable=False)
    aggregates_json = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class MsiJobEvent(Base):
    __tablename__ = "msi_job_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(64), ForeignKey("msi_runs.run_id", ondelete="CASCADE"), nullable=False, index=True)
    node = Column(String(64), nullable=False, index=True)
    event_type = Column(String(32), nullable=False, index=True)  # started|finished|failed|state_update
    payload_json = Column(JSON, nullable=False, default=dict)
    ts = Column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index("ix_msi_job_events_run_ts", "run_id", "ts"),
    )


class MsiWatchlist(Base):
    __tablename__ = "msi_watchlist"

    id = Column(Integer, primary_key=True, autoincrement=True)
    profile_id = Column(String(64), nullable=False, index=True)
    entity = Column(String(255), nullable=False, index=True)
    aliases_json = Column(JSON, nullable=False, default=list)
    enabled = Column(Boolean, nullable=False, default=True, index=True)
    run_daily = Column(Boolean, nullable=False, default=True)
    run_weekly = Column(Boolean, nullable=False, default=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_by_username = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("profile_id", "entity", name="uq_msi_watchlist_profile_entity"),
    )


class MsiBaseline(Base):
    __tablename__ = "msi_baselines"

    id = Column(Integer, primary_key=True, autoincrement=True)
    profile_id = Column(String(64), nullable=False, index=True)
    entity = Column(String(255), nullable=False, index=True)
    pressure_history = Column(JSON, nullable=False, default=list)
    last_topic_dist = Column(JSON, nullable=False, default=dict)
    baseline_window_days = Column(Integer, nullable=False, default=90)
    last_updated = Column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        UniqueConstraint("profile_id", "entity", name="uq_msi_baseline_profile_entity"),
    )
