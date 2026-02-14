"""
Echorouk AI Swarm — Database Models
=====================================
SQLAlchemy ORM models for the news pipeline.
Status Pipeline: NEW → CLEANED → DEDUPED → CLASSIFIED → CANDIDATE → APPROVED/REJECTED → PUBLISHED → ARCHIVED
"""

import enum
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, Float, Boolean, DateTime,
    Enum, ForeignKey, Index, JSON, UniqueConstraint,
)
from sqlalchemy.orm import relationship
from app.core.database import Base


# ── Enums ──

class NewsStatus(str, enum.Enum):
    NEW = "new"
    CLEANED = "cleaned"
    DEDUPED = "deduped"
    CLASSIFIED = "classified"
    CANDIDATE = "candidate"
    APPROVED = "approved"
    REJECTED = "rejected"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class NewsCategory(str, enum.Enum):
    POLITICS = "politics"
    ECONOMY = "economy"
    SPORTS = "sports"
    TECHNOLOGY = "technology"
    LOCAL_ALGERIA = "local_algeria"
    INTERNATIONAL = "international"
    CULTURE = "culture"
    SOCIETY = "society"
    HEALTH = "health"
    ENVIRONMENT = "environment"


class UrgencyLevel(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    BREAKING = "breaking"


class Sentiment(str, enum.Enum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


# ── Models ──

class Source(Base):
    """RSS/Web news source registry."""
    __tablename__ = "sources"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    slug = Column(String(255), nullable=True)
    method = Column(String(20), default="rss")  # rss | scraper
    url = Column(String(1024), nullable=False, unique=True)
    rss_url = Column(String(1024), nullable=True)
    category = Column(String(100), default="general")
    language = Column(String(10), default="ar")
    languages = Column(String(50), nullable=True)  # ar/fr/en...
    region = Column(String(50), nullable=True)  # algeria/arab/international
    source_type = Column(String(50), nullable=True)  # media/agency/official/aggregator/business/tech
    description = Column(Text, nullable=True)
    trust_score = Column(Float, default=0.5)
    credibility = Column(String(20), default="medium")  # official/high/medium/low
    priority = Column(Integer, default=5)
    enabled = Column(Boolean, default=True)
    fetch_interval_minutes = Column(Integer, default=30)
    last_fetched_at = Column(DateTime, nullable=True)
    error_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    articles = relationship("Article", back_populates="source", lazy="dynamic")

    def __repr__(self):
        return f"<Source(name='{self.name}', url='{self.url}')>"


class Article(Base):
    """Core news article — the main entity in the pipeline."""
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    unique_hash = Column(String(64), nullable=False, unique=True, index=True)

    # ── Raw Data ──
    original_title = Column(String(1024), nullable=False)
    original_url = Column(String(2048), nullable=False)
    original_content = Column(Text, nullable=True)
    published_at = Column(DateTime, nullable=True)
    crawled_at = Column(DateTime, default=datetime.utcnow)

    # ── Source ──
    source_id = Column(Integer, ForeignKey("sources.id"), nullable=True)
    source_name = Column(String(255), nullable=True)

    # ── AI Analysis ──
    title_ar = Column(String(1024), nullable=True)
    summary = Column(Text, nullable=True)
    body_html = Column(Text, nullable=True)
    category = Column(Enum(NewsCategory), nullable=True)
    importance_score = Column(Integer, default=0)
    urgency = Column(Enum(UrgencyLevel), default=UrgencyLevel.LOW)
    is_breaking = Column(Boolean, default=False)
    sentiment = Column(Enum(Sentiment), nullable=True)
    truth_score = Column(Float, nullable=True)
    entities = Column(JSON, default=list)
    keywords = Column(JSON, default=list)
    seo_title = Column(String(512), nullable=True)
    seo_description = Column(String(512), nullable=True)

    # ── Pipeline State ──
    status = Column(Enum(NewsStatus), default=NewsStatus.NEW, index=True)
    rejection_reason = Column(Text, nullable=True)

    # ── Editorial ──
    reviewed_by = Column(String(255), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    published_url = Column(String(2048), nullable=True)

    # ── Metadata ──
    processing_time_ms = Column(Integer, nullable=True)
    ai_model_used = Column(String(100), nullable=True)
    retry_count = Column(Integer, default=0)
    trace_id = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    source = relationship("Source", back_populates="articles")
    editor_decisions = relationship("EditorDecision", back_populates="article", lazy="dynamic")

    __table_args__ = (
        Index("ix_articles_status_category", "status", "category"),
        Index("ix_articles_crawled", "crawled_at"),
        Index("ix_articles_importance", "importance_score"),
    )

    def __repr__(self):
        return f"<Article(id={self.id}, title='{self.title_ar or self.original_title[:50]}')>"


class EditorDecision(Base):
    """Human-in-the-loop editorial decisions (feedback loop)."""
    __tablename__ = "editor_decisions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    article_id = Column(Integer, ForeignKey("articles.id"), nullable=False)
    editor_name = Column(String(255), nullable=False)
    decision = Column(String(50), nullable=False)  # approve / reject / rewrite
    reason = Column(Text, nullable=True)
    original_ai_title = Column(String(1024), nullable=True)
    edited_title = Column(String(1024), nullable=True)
    original_ai_body = Column(Text, nullable=True)
    edited_body = Column(Text, nullable=True)
    decided_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    article = relationship("Article", back_populates="editor_decisions")

    def __repr__(self):
        return f"<EditorDecision(article_id={self.article_id}, decision='{self.decision}')>"


class EditorialDraft(Base):
    """Versioned editable draft generated from editorial actions."""
    __tablename__ = "editorial_drafts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    article_id = Column(Integer, ForeignKey("articles.id"), nullable=False, index=True)
    work_id = Column(String(64), nullable=False, unique=True, index=True)
    source_action = Column(String(100), nullable=False, default="manual")
    title = Column(String(1024), nullable=True)
    body = Column(Text, nullable=False)
    note = Column(Text, nullable=True)
    status = Column(String(30), nullable=False, default="draft")  # draft|applied|archived
    version = Column(Integer, nullable=False, default=1)
    created_by = Column(String(255), nullable=False)
    updated_by = Column(String(255), nullable=True)
    applied_by = Column(String(255), nullable=True)
    applied_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    article = relationship("Article")

    __table_args__ = (
        UniqueConstraint("article_id", "source_action", "version", name="uq_draft_article_action_version"),
        Index("ix_editorial_drafts_article_status", "article_id", "status"),
    )

    def __repr__(self):
        return f"<EditorialDraft(id={self.id}, article_id={self.article_id}, version={self.version})>"


class FeedbackLog(Base):
    """RLHF — Records diffs between AI output and human edits."""
    __tablename__ = "feedback_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    article_id = Column(Integer, ForeignKey("articles.id"), nullable=False)
    field_name = Column(String(100), nullable=False)
    original_value = Column(Text, nullable=True)
    corrected_value = Column(Text, nullable=True)
    correction_type = Column(String(50), nullable=True)  # style, factual, tone
    logged_at = Column(DateTime, default=datetime.utcnow)


class FailedJob(Base):
    """Dead Letter Queue — tracks failed processing attempts."""
    __tablename__ = "failed_jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_type = Column(String(100), nullable=False)
    payload = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    error_traceback = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    resolved = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)


class PipelineRun(Base):
    """Observability — logs for each pipeline execution."""
    __tablename__ = "pipeline_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_type = Column(String(100), nullable=False)  # scout, triage, publish
    started_at = Column(DateTime, default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)
    total_items = Column(Integer, default=0)
    new_items = Column(Integer, default=0)
    duplicates = Column(Integer, default=0)
    errors = Column(Integer, default=0)
    ai_calls = Column(Integer, default=0)
    status = Column(String(50), default="running")  # running, success, failed
    details = Column(JSON, nullable=True)
