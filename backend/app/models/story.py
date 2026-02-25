from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class StoryStatus(str, enum.Enum):
    open = "open"
    monitoring = "monitoring"
    closed = "closed"
    archived = "archived"


class Story(Base):
    __tablename__ = "stories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    story_key = Column(String(40), nullable=False, unique=True, index=True)
    title = Column(String(1024), nullable=False)
    summary = Column(Text, nullable=True)
    category = Column(String(80), nullable=True, index=True)
    geography = Column(String(24), nullable=True, index=True)
    status = Column(Enum(StoryStatus, name="story_status", create_type=False), nullable=False, default=StoryStatus.open)
    priority = Column(Integer, nullable=False, default=5)
    created_by = Column(String(128), nullable=True)
    updated_by = Column(String(128), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, index=True)

    items = relationship("StoryItem", back_populates="story", lazy="selectin")


class StoryItem(Base):
    __tablename__ = "story_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    story_id = Column(Integer, ForeignKey("stories.id", ondelete="CASCADE"), nullable=False, index=True)
    article_id = Column(Integer, ForeignKey("articles.id", ondelete="SET NULL"), nullable=True, index=True)
    draft_id = Column(Integer, ForeignKey("editorial_drafts.id", ondelete="SET NULL"), nullable=True, index=True)
    link_type = Column(String(16), nullable=False, default="article")  # article|draft
    note = Column(Text, nullable=True)
    created_by = Column(String(128), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    story = relationship("Story", back_populates="items")
    article = relationship("Article")
    draft = relationship("EditorialDraft")

    __table_args__ = (
        CheckConstraint(
            "((article_id IS NOT NULL AND draft_id IS NULL) OR (article_id IS NULL AND draft_id IS NOT NULL))",
            name="ck_story_items_exactly_one_ref",
        ),
        CheckConstraint(
            "((link_type = 'article' AND article_id IS NOT NULL AND draft_id IS NULL) "
            "OR (link_type = 'draft' AND draft_id IS NOT NULL AND article_id IS NULL))",
            name="ck_story_items_link_type_match",
        ),
        UniqueConstraint("story_id", "article_id", name="uq_story_item_story_article"),
        UniqueConstraint("story_id", "draft_id", name="uq_story_item_story_draft"),
        Index("ix_story_items_story_link_type", "story_id", "link_type"),
    )
