"""
Echorouk AI Swarm — API Settings Model
======================================
Stores external API credentials and service configuration.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, Index

from app.core.database import Base


class ApiSetting(Base):
    """Key-value settings for external APIs (editable by admin)."""
    __tablename__ = "api_settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(100), unique=True, nullable=False, index=True)
    value = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    is_secret = Column(Boolean, default=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_api_settings_key", "key"),
    )
