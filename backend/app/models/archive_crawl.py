from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from app.core.database import Base


class ArchiveCrawlState(Base):
    __tablename__ = "archive_crawl_states"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_key = Column(String(64), nullable=False, unique=True, index=True)
    source_name = Column(String(255), nullable=False)
    base_url = Column(String(2048), nullable=False)
    status = Column(String(24), nullable=False, default="idle", index=True)  # idle|running|paused|failed
    seeded_at = Column(DateTime, nullable=True)
    last_run_started_at = Column(DateTime, nullable=True)
    last_run_finished_at = Column(DateTime, nullable=True)
    last_error = Column(Text, nullable=True)
    stats_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, index=True)

    urls = relationship("ArchiveCrawlUrl", back_populates="state", cascade="all, delete-orphan")


class ArchiveCrawlUrl(Base):
    __tablename__ = "archive_crawl_urls"

    id = Column(Integer, primary_key=True, autoincrement=True)
    state_id = Column(Integer, ForeignKey("archive_crawl_states.id"), nullable=False, index=True)
    url = Column(String(2048), nullable=False)
    url_type = Column(String(16), nullable=False, index=True)  # listing|article
    status = Column(String(24), nullable=False, default="discovered", index=True)  # discovered|processing|fetched|indexed|failed|skipped
    priority = Column(Integer, nullable=False, default=100, index=True)
    depth = Column(Integer, nullable=False, default=0)
    discovered_from_url = Column(String(2048), nullable=True)
    canonical_url = Column(String(2048), nullable=True)
    article_id = Column(Integer, ForeignKey("articles.id"), nullable=True, index=True)
    attempts = Column(Integer, nullable=False, default=0)
    last_http_status = Column(Integer, nullable=True)
    last_error = Column(Text, nullable=True)
    discovered_at = Column(DateTime, default=datetime.utcnow, index=True)
    fetched_at = Column(DateTime, nullable=True)
    indexed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, index=True)

    state = relationship("ArchiveCrawlState", back_populates="urls")
    article = relationship("Article")

    __table_args__ = (
        UniqueConstraint("state_id", "url", name="uq_archive_crawl_urls_state_url"),
        Index("ix_archive_crawl_urls_state_type_status", "state_id", "url_type", "status"),
        Index("ix_archive_crawl_urls_state_priority", "state_id", "priority", "id"),
    )
