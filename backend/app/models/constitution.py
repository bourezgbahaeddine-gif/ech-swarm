"""
Echorouk Editorial OS — Constitution Models
=======================================
Tracks editorial constitution version and user acknowledgements.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Index, Text
from sqlalchemy.orm import relationship

from app.core.database import Base


class ConstitutionMeta(Base):
    __tablename__ = "constitution_meta"

    id = Column(Integer, primary_key=True, autoincrement=True)
    version = Column(String(50), nullable=False)
    file_url = Column(String(255), nullable=False, default="/Constitution.docx")
    is_active = Column(Boolean, default=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_constitution_meta_version", "version"),
        Index("ix_constitution_meta_active", "is_active"),
    )


class ConstitutionAck(Base):
    __tablename__ = "constitution_ack"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    version = Column(String(50), nullable=False)
    acknowledged_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_constitution_ack_user_version", "user_id", "version"),
    )


class ImagePrompt(Base):
    __tablename__ = "image_prompts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    article_id = Column(Integer, nullable=True, index=True)
    prompt_text = Column(Text, nullable=False)
    style = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String(100), nullable=True)

    __table_args__ = (
        Index("ix_image_prompts_article_id", "article_id"),
    )


class InfographicData(Base):
    __tablename__ = "infographics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    article_id = Column(Integer, nullable=True, index=True)
    data_json = Column(Text, nullable=False)
    prompt_text = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String(100), nullable=True)

    __table_args__ = (
        Index("ix_infographics_article_id", "article_id"),
    )
