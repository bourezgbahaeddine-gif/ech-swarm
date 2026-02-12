"""
Echorouk AI Swarm — Settings Audit Log
======================================
Tracks changes to API settings for admin visibility.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Index

from app.core.database import Base


class SettingsAudit(Base):
    __tablename__ = "settings_audit"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(100), nullable=False, index=True)
    action = Column(String(30), nullable=False)  # create/update/import
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    actor = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_settings_audit_key", "key"),
        Index("ix_settings_audit_created_at", "created_at"),
    )
