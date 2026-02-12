"""
Echorouk AI Swarm — Authentication Routes
==========================================
Login, current user, and user management endpoints.
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import verify_password, create_access_token, decode_access_token
from app.core.logging import get_logger
from app.models.user import User, UserRole
from app.schemas.auth import (
    LoginRequest, TokenResponse, UserProfile, UserListItem,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])
logger = get_logger("auth")
security = HTTPBearer()


# ── Dependency: Get Current User ──

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Extract and validate the current user from JWT token."""
    payload = decode_access_token(credentials.credentials)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="رمز المصادقة غير صالح أو منتهي الصلاحية",
        )

    username = payload.get("sub")
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="رمز المصادقة غير صالح",
        )

    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="الحساب غير موجود أو معطّل",
        )

    return user


# ── Login ──

@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    """
    تسجيل الدخول — Authenticate journalist and return JWT token.
    """
    # Find user
    result = await db.execute(
        select(User).where(User.username == request.username)
    )
    user = result.scalar_one_or_none()

    if not user or not verify_password(request.password, user.hashed_password):
        logger.warning("login_failed", username=request.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="اسم المستخدم أو كلمة السر غير صحيحة",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="الحساب معطّل — تواصل مع المدير",
        )

    # Update last login & online status
    await db.execute(
        update(User)
        .where(User.id == user.id)
        .values(
            last_login_at=datetime.now(timezone.utc),
            is_online=True,
        )
    )
    await db.commit()

    # Create JWT
    token = create_access_token(
        data={
            "sub": user.username,
            "role": user.role.value,
            "departments": user.departments,
            "name": user.full_name_ar,
        }
    )

    logger.info("login_success", username=user.username, role=user.role.value)

    return TokenResponse(
        access_token=token,
        user=UserProfile.model_validate(user),
    )


# ── Current User ──

@router.get("/me", response_model=UserProfile)
async def get_me(current_user: User = Depends(get_current_user)):
    """الحصول على بيانات المستخدم الحالي."""
    return UserProfile.model_validate(current_user)


# ── Logout ──

@router.post("/logout")
async def logout(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """تسجيل الخروج — Mark user as offline."""
    await db.execute(
        update(User)
        .where(User.id == current_user.id)
        .values(is_online=False)
    )
    await db.commit()
    logger.info("logout", username=current_user.username)
    return {"message": "تم تسجيل الخروج بنجاح"}


# ── List All Users (Director only) ──

@router.get("/users", response_model=list[UserListItem])
async def list_users(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    قائمة الصحفيين — Director and Editor-in-Chief only.
    """
    if current_user.role not in [UserRole.director, UserRole.editor_chief]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="غير مصرح — الصلاحية للمدير ورئيس التحرير فقط",
        )

    result = await db.execute(
        select(User).order_by(User.role, User.full_name_ar)
    )
    users = result.scalars().all()
    return [UserListItem.model_validate(u) for u in users]
