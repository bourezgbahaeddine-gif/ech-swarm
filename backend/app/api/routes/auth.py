"""
Echorouk AI Swarm - Authentication and Membership Routes
=======================================================
Login, current user, logout, and director membership management.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.logging import get_logger
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.models.user import Department, User, UserRole
from app.models.user_activity import UserActivityLog
from app.schemas.auth import (
    LoginRequest,
    TokenResponse,
    UserActivityItem,
    UserCreateRequest,
    UserListItem,
    UserProfile,
    UserUpdateRequest,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])
logger = get_logger("auth")
security = HTTPBearer()


def _require_director(user: User) -> None:
    if user.role != UserRole.director:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="هذه العملية متاحة للمدير فقط",
        )


def _require_manager_view(user: User) -> None:
    if user.role != UserRole.director:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="غير مصرح. المتاح للمدير فقط",
        )


def _normalize_departments(values: list[str]) -> list[str]:
    allowed = {d.value for d in Department}
    clean = []
    for value in values:
        normalized = (value or "").strip()
        if normalized not in allowed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"قسم غير صالح: {normalized}",
            )
        if normalized not in clean:
            clean.append(normalized)
    return clean


async def _log_activity(
    db: AsyncSession,
    *,
    action: str,
    actor: User | None = None,
    target: User | None = None,
    details: dict | None = None,
) -> None:
    """
    Best-effort audit logging.
    Must never break critical auth/workflow paths when audit schema is missing or degraded.
    """
    try:
        async with db.begin_nested():
            db.add(
                UserActivityLog(
                    actor_user_id=actor.id if actor else None,
                    actor_username=actor.username if actor else None,
                    target_user_id=target.id if target else None,
                    target_username=target.username if target else None,
                    action=action,
                    details=json.dumps(details, ensure_ascii=False) if details else None,
                )
            )
            await db.flush()
    except SQLAlchemyError as exc:
        logger.warning(
            "activity_log_write_failed",
            action=action,
            error=str(exc.__class__.__name__),
        )


async def _active_directors_count(db: AsyncSession) -> int:
    result = await db.execute(
        select(func.count(User.id)).where(
            User.role == UserRole.director,
            User.is_active.is_(True),
        )
    )
    return int(result.scalar_one() or 0)


# -- Dependency: current user --
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
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
            detail="الحساب غير موجود أو معطل",
        )
    return user


# -- Login --
@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == request.username))
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
            detail="الحساب معطل. تواصل مع المدير",
        )

    now = datetime.now(timezone.utc)
    await db.execute(
        update(User).where(User.id == user.id).values(last_login_at=now, is_online=True)
    )
    await _log_activity(
        db,
        action="auth_login",
        actor=user,
        target=user,
        details={"ip_context": "api"},
    )
    await db.commit()

    token = create_access_token(
        data={
            "sub": user.username,
            "role": user.role.value,
            "departments": user.departments,
            "name": user.full_name_ar,
        }
    )

    logger.info("login_success", username=user.username, role=user.role.value)
    return TokenResponse(access_token=token, user=UserProfile.model_validate(user))


# -- Current user --
@router.get("/me", response_model=UserProfile)
async def get_me(current_user: User = Depends(get_current_user)):
    return UserProfile.model_validate(current_user)


# -- Logout --
@router.post("/logout")
async def logout(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await db.execute(
        update(User).where(User.id == current_user.id).values(is_online=False)
    )
    await _log_activity(
        db,
        action="auth_logout",
        actor=current_user,
        target=current_user,
    )
    await db.commit()
    logger.info("logout", username=current_user.username)
    return {"message": "تم تسجيل الخروج بنجاح"}


# -- Users list (manager view) --
@router.get("/users", response_model=list[UserListItem])
async def list_users(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_manager_view(current_user)
    result = await db.execute(select(User).order_by(User.role, User.full_name_ar))
    users = result.scalars().all()
    return [UserListItem.model_validate(u) for u in users]


# -- Create user (director only) --
@router.post("/users", response_model=UserListItem, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_director(current_user)
    departments = _normalize_departments(payload.departments)

    user = User(
        full_name_ar=payload.full_name_ar.strip(),
        username=payload.username.strip(),
        hashed_password=hash_password(payload.password),
        role=payload.role,
        departments=departments,
        specialization=payload.specialization.strip() if payload.specialization else None,
        is_active=payload.is_active,
        is_online=False,
    )
    db.add(user)

    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="اسم المستخدم مستخدم مسبقًا",
        )

    await _log_activity(
        db,
        action="membership_create_user",
        actor=current_user,
        target=user,
        details={
            "role": payload.role.value,
            "is_active": payload.is_active,
            "departments": departments,
        },
    )
    await db.commit()
    await db.refresh(user)
    return UserListItem.model_validate(user)


# -- Update user (director only) --
@router.put("/users/{user_id}", response_model=UserListItem)
async def update_user(
    user_id: int,
    payload: UserUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_director(current_user)

    result = await db.execute(select(User).where(User.id == user_id))
    target_user = result.scalar_one_or_none()
    if not target_user:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")

    changes: dict[str, object] = {}
    data = payload.model_dump(exclude_unset=True)

    if "username" in data:
        next_username = str(data["username"]).strip()
        check = await db.execute(
            select(User.id).where(User.username == next_username, User.id != user_id)
        )
        if check.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="اسم المستخدم مستخدم مسبقًا",
            )
        target_user.username = next_username
        changes["username"] = next_username

    if "full_name_ar" in data:
        target_user.full_name_ar = str(data["full_name_ar"]).strip()
        changes["full_name_ar"] = target_user.full_name_ar

    if "password" in data and data["password"]:
        target_user.hashed_password = hash_password(str(data["password"]))
        changes["password_reset"] = True

    if "role" in data and data["role"] is not None:
        next_role = data["role"]
        if (
            target_user.role == UserRole.director
            and next_role != UserRole.director
            and await _active_directors_count(db) <= 1
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="لا يمكن إزالة آخر مدير نشط في النظام",
            )
        target_user.role = next_role
        changes["role"] = next_role.value

    if "departments" in data and data["departments"] is not None:
        next_departments = _normalize_departments(data["departments"])
        target_user.departments = next_departments
        changes["departments"] = next_departments

    if "specialization" in data:
        value = data["specialization"]
        target_user.specialization = value.strip() if isinstance(value, str) else value
        changes["specialization"] = target_user.specialization

    if "is_active" in data and data["is_active"] is not None:
        next_active = bool(data["is_active"])
        if (
            target_user.role == UserRole.director
            and not next_active
            and await _active_directors_count(db) <= 1
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="لا يمكن تعطيل آخر مدير نشط في النظام",
            )
        target_user.is_active = next_active
        if not next_active:
            target_user.is_online = False
        changes["is_active"] = next_active

    if not changes:
        return UserListItem.model_validate(target_user)

    await _log_activity(
        db,
        action="membership_update_user",
        actor=current_user,
        target=target_user,
        details=changes,
    )

    await db.commit()
    await db.refresh(target_user)
    return UserListItem.model_validate(target_user)


# -- User activity log (manager view) --
@router.get("/users/{user_id}/activity", response_model=list[UserActivityItem])
async def user_activity(
    user_id: int,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_manager_view(current_user)

    exists = await db.execute(select(User.id).where(User.id == user_id))
    if not exists.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")

    rows = await db.execute(
        select(UserActivityLog)
        .where(UserActivityLog.target_user_id == user_id)
        .order_by(UserActivityLog.created_at.desc())
        .limit(max(1, min(limit, 500)))
    )
    return [UserActivityItem.model_validate(item) for item in rows.scalars().all()]
