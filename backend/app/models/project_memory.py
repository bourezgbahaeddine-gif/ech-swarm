"""
Project Memory models.
Stores operational/session/knowledge memory for newsroom workflows.
"""

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import relationship

from app.core.database import Base


class ProjectMemoryItem(Base):
    __tablename__ = "project_memory_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    memory_type = Column(String(24), nullable=False, index=True, default="operational")  # operational|knowledge|session
    title = Column(String(512), nullable=False)
    content = Column(Text, nullable=False)
    tags = Column(JSON, nullable=False, default=list)
    source_type = Column(String(64), nullable=True)  # decision|incident|doc|article|manual
    source_ref = Column(String(512), nullable=True)
    article_id = Column(Integer, ForeignKey("articles.id"), nullable=True, index=True)
    status = Column(String(24), nullable=False, index=True, default="active")  # active|archived
    importance = Column(Integer, nullable=False, default=3)

    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    created_by_username = Column(String(64), nullable=True)
    updated_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    updated_by_username = Column(String(64), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    article = relationship("Article")
    events = relationship("ProjectMemoryEvent", back_populates="memory_item", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_project_memory_type_status_updated", "memory_type", "status", "updated_at"),
    )


class ProjectMemoryEvent(Base):
    __tablename__ = "project_memory_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    memory_id = Column(Integer, ForeignKey("project_memory_items.id"), nullable=False, index=True)
    event_type = Column(String(32), nullable=False, index=True)  # created|updated|used|archived|pinned
    note = Column(Text, nullable=True)
    actor_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    actor_username = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    memory_item = relationship("ProjectMemoryItem", back_populates="events")

    __table_args__ = (
        Index("ix_project_memory_events_memory_created", "memory_id", "created_at"),
    )
