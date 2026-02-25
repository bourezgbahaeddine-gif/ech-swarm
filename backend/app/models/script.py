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
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class ScriptProjectType(str, enum.Enum):
    story_script = "story_script"
    video_script = "video_script"
    bulletin_daily = "bulletin_daily"
    bulletin_weekly = "bulletin_weekly"


class ScriptProjectStatus(str, enum.Enum):
    new = "new"
    generating = "generating"
    failed = "failed"
    ready_for_review = "ready_for_review"
    approved = "approved"
    rejected = "rejected"
    archived = "archived"


class ScriptOutputFormat(str, enum.Enum):
    markdown = "markdown"
    json = "json"
    srt = "srt"


class ScriptProject(Base):
    __tablename__ = "script_projects"

    id = Column(Integer, primary_key=True, autoincrement=True)
    type = Column(Enum(ScriptProjectType, name="script_project_type", create_type=False), nullable=False, index=True)
    status = Column(
        Enum(ScriptProjectStatus, name="script_project_status", create_type=False),
        nullable=False,
        default=ScriptProjectStatus.new,
        index=True,
    )
    story_id = Column(Integer, ForeignKey("stories.id", ondelete="SET NULL"), nullable=True, index=True)
    article_id = Column(Integer, ForeignKey("articles.id", ondelete="SET NULL"), nullable=True, index=True)
    title = Column(String(1024), nullable=False)
    params_json = Column(JSON, nullable=False, default=dict)
    created_by = Column(String(128), nullable=True)
    updated_by = Column(String(128), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, index=True)

    story = relationship("Story")
    article = relationship("Article")
    outputs = relationship("ScriptOutput", back_populates="project", cascade="all, delete-orphan", lazy="selectin")

    __table_args__ = (
        CheckConstraint(
            "("
            "(type IN ('story_script','video_script') AND "
            " ((story_id IS NOT NULL AND article_id IS NULL) OR (story_id IS NULL AND article_id IS NOT NULL))) "
            "OR "
            "(type IN ('bulletin_daily','bulletin_weekly') AND story_id IS NULL AND article_id IS NULL)"
            ")",
            name="ck_script_projects_target_scope",
        ),
        Index("ix_script_projects_type_status", "type", "status"),
    )


class ScriptOutput(Base):
    __tablename__ = "script_outputs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    script_id = Column(Integer, ForeignKey("script_projects.id", ondelete="CASCADE"), nullable=False, index=True)
    version = Column(Integer, nullable=False, default=1)
    content_json = Column(JSON, nullable=True)
    content_text = Column(Text, nullable=True)
    format = Column(Enum(ScriptOutputFormat, name="script_output_format", create_type=False), nullable=False, default=ScriptOutputFormat.json)
    quality_issues_json = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    project = relationship("ScriptProject", back_populates="outputs")

    __table_args__ = (
        UniqueConstraint("script_id", "version", name="uq_script_output_script_version"),
        Index("ix_script_outputs_script_created", "script_id", "created_at"),
    )
