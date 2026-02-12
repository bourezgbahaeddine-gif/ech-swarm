"""
Echorouk AI Swarm — User Model
================================
Journalist and editor accounts with role-based access.
"""

import enum
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Enum, Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY
from app.core.database import Base


class UserRole(str, enum.Enum):
    director = "director"
    editor_chief = "editor_chief"
    journalist = "journalist"
    social_media = "social_media"
    print_editor = "print_editor"


class Department(str, enum.Enum):
    NATIONAL = "national"
    INTERNATIONAL = "international"
    ECONOMY = "economy"
    SPORTS = "sports"
    FRENCH = "french"
    SOCIAL_MEDIA = "social_media"
    PRINT = "print"
    VARIETY = "variety"
    JEWELRY = "jewelry"
    MANAGEMENT = "management"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Identity
    full_name_ar = Column(String(100), nullable=False, comment="الاسم الكامل بالعربية")
    username = Column(String(50), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)

    # Role & Permissions
    role = Column(Enum(UserRole, name="user_role", create_type=False), nullable=False, default=UserRole.journalist)
    departments = Column(ARRAY(String), nullable=False, default=[], comment="الأقسام المسموح بها")
    specialization = Column(String(200), nullable=True, comment="التخصص")

    # Status
    is_active = Column(Boolean, default=True)
    is_online = Column(Boolean, default=False)
    last_login_at = Column(DateTime(timezone=True), nullable=True)

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<User {self.username} ({self.full_name_ar})>"
