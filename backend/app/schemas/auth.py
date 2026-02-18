"""
Echorouk AI Swarm — Authentication Schemas
============================================
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

from app.models.user import UserRole


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=50)
    password: str = Field(..., min_length=6)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserProfile"


class UserProfile(BaseModel):
    id: int
    full_name_ar: str
    username: str
    role: str
    departments: list[str]
    specialization: Optional[str]
    is_active: bool
    last_login_at: Optional[datetime]

    class Config:
        from_attributes = True


class UserListItem(BaseModel):
    id: int
    full_name_ar: str
    username: str
    role: str
    departments: list[str]
    specialization: Optional[str]
    is_active: bool
    is_online: bool
    last_login_at: Optional[datetime]

    class Config:
        from_attributes = True


class UserCreateRequest(BaseModel):
    full_name_ar: str = Field(..., min_length=2, max_length=100)
    username: str = Field(..., min_length=2, max_length=50)
    password: str = Field(..., min_length=8, max_length=128)
    role: UserRole
    departments: list[str] = Field(default_factory=list)
    specialization: Optional[str] = Field(default=None, max_length=200)
    is_active: bool = True


class UserUpdateRequest(BaseModel):
    full_name_ar: Optional[str] = Field(default=None, min_length=2, max_length=100)
    username: Optional[str] = Field(default=None, min_length=2, max_length=50)
    password: Optional[str] = Field(default=None, min_length=8, max_length=128)
    role: Optional[UserRole] = None
    departments: Optional[list[str]] = None
    specialization: Optional[str] = Field(default=None, max_length=200)
    is_active: Optional[bool] = None


class UserActivityItem(BaseModel):
    id: int
    actor_user_id: Optional[int] = None
    actor_username: Optional[str] = None
    target_user_id: Optional[int] = None
    target_username: Optional[str] = None
    action: str
    details: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# Rebuild model to resolve forward reference
TokenResponse.model_rebuild()
