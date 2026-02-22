"""
Echorouk Editorial OS - User Activity Log Model
==========================================
Tracks membership and authentication activity for admin audit.
"""

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text

from app.core.database import Base


class UserActivityLog(Base):
    __tablename__ = "user_activity_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    actor_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    actor_username = Column(String(50), nullable=True, index=True)
    target_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    target_username = Column(String(50), nullable=True, index=True)
    action = Column(String(80), nullable=False, index=True)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index("ix_user_activity_target_created_at", "target_user_id", "created_at"),
    )

