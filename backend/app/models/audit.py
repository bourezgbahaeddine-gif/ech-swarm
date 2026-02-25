"""
Echorouk Editorial OS — Settings Audit Log
======================================
Tracks changes to API settings for admin visibility.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Index, JSON

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

    __table_args__ = (Index("ix_settings_audit_created_at", "created_at"),)


class ActionAuditLog(Base):
    __tablename__ = "action_audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    action = Column(String(80), nullable=False, index=True)
    entity_type = Column(String(80), nullable=False, index=True)
    entity_id = Column(String(120), nullable=True, index=True)
    from_state = Column(String(64), nullable=True)
    to_state = Column(String(64), nullable=True)
    reason = Column(Text, nullable=True)
    details_json = Column(JSON, nullable=True, default=dict)
    actor_user_id = Column(Integer, nullable=True, index=True)
    actor_username = Column(String(100), nullable=True, index=True)
    correlation_id = Column(String(64), nullable=True, index=True)
    request_id = Column(String(64), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index("ix_action_audit_entity_created", "entity_type", "entity_id", "created_at"),
    )
