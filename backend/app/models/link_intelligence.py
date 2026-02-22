"""
Link Intelligence models.
Internal/External link index + recommendation runs/items.
"""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)

from app.core.database import Base


class LinkIndexItem(Base):
    __tablename__ = "link_index_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    url = Column(String(2048), nullable=False, unique=True, index=True)
    domain = Column(String(255), nullable=False, index=True)
    link_type = Column(String(16), nullable=False, index=True)  # internal|external
    title = Column(String(1024), nullable=False)
    summary = Column(Text, nullable=True)
    category = Column(String(64), nullable=True, index=True)
    keywords_json = Column(JSON, nullable=False, default=list)
    metadata_json = Column(JSON, nullable=False, default=dict)
    published_at = Column(DateTime, nullable=True, index=True)
    authority_score = Column(Float, nullable=False, default=0.5)
    source_article_id = Column(Integer, ForeignKey("articles.id"), nullable=True, index=True)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    first_seen_at = Column(DateTime, default=datetime.utcnow)
    last_seen_at = Column(DateTime, default=datetime.utcnow, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, index=True)

    __table_args__ = (
        Index("ix_link_index_type_active_recent", "link_type", "is_active", "published_at"),
    )


class TrustedDomain(Base):
    __tablename__ = "trusted_domains"

    id = Column(Integer, primary_key=True, autoincrement=True)
    domain = Column(String(255), nullable=False, unique=True, index=True)
    display_name = Column(String(255), nullable=True)
    trust_score = Column(Float, nullable=False, default=0.7)
    tier = Column(String(24), nullable=False, default="standard", index=True)  # official|wire|institutional|standard
    enabled = Column(Boolean, nullable=False, default=True, index=True)
    notes = Column(Text, nullable=True)
    created_by = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, index=True)


class LinkRecommendationRun(Base):
    __tablename__ = "link_recommendation_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(64), nullable=False, unique=True, index=True)
    work_id = Column(String(64), nullable=False, index=True)
    article_id = Column(Integer, ForeignKey("articles.id"), nullable=True, index=True)
    draft_id = Column(Integer, ForeignKey("editorial_drafts.id"), nullable=True, index=True)
    mode = Column(String(16), nullable=False, default="mixed", index=True)  # internal|external|mixed
    status = Column(String(24), nullable=False, default="completed", index=True)  # completed|failed
    source_counts_json = Column(JSON, nullable=False, default=dict)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    created_by_username = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    finished_at = Column(DateTime, nullable=True)
    error = Column(Text, nullable=True)

    __table_args__ = (
        Index("ix_link_recommend_runs_work_created", "work_id", "created_at"),
    )


class LinkRecommendationItem(Base):
    __tablename__ = "link_recommendation_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(
        String(64),
        ForeignKey("link_recommendation_runs.run_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    link_index_item_id = Column(Integer, ForeignKey("link_index_items.id"), nullable=True, index=True)
    link_type = Column(String(16), nullable=False, index=True)  # internal|external
    url = Column(String(2048), nullable=False)
    title = Column(String(1024), nullable=False)
    anchor_text = Column(String(255), nullable=False)
    placement_hint = Column(String(255), nullable=True)
    reason = Column(Text, nullable=True)
    score = Column(Float, nullable=False, default=0.0, index=True)
    confidence = Column(Float, nullable=False, default=0.0)
    rel_attrs = Column(String(128), nullable=True)
    status = Column(String(24), nullable=False, default="suggested", index=True)  # suggested|applied|rejected
    metadata_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index("ix_link_recommend_items_run_score", "run_id", "score"),
    )


class LinkClickEvent(Base):
    __tablename__ = "link_click_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    article_id = Column(Integer, ForeignKey("articles.id"), nullable=True, index=True)
    work_id = Column(String(64), nullable=True, index=True)
    url = Column(String(2048), nullable=False)
    link_type = Column(String(16), nullable=False, index=True)
    clicked_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    clicked_by_username = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        UniqueConstraint("work_id", "url", "created_at", name="uq_link_click_work_url_time"),
    )
