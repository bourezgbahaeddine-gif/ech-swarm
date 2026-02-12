"""
Echorouk AI Swarm — Authentication Schemas
============================================
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


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


# Rebuild model to resolve forward reference
TokenResponse.model_rebuild()
