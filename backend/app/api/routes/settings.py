"""
Echorouk Editorial OS — API Settings Routes
======================================
Admin endpoints for managing external API credentials/config.
"""

from datetime import datetime
from typing import Optional

import aiohttp
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.rbac import enforce_roles
from app.core.database import get_db
from app.core.logging import get_logger
from app.models.settings import ApiSetting
from app.models.audit import SettingsAudit
from app.models.user import User, UserRole
from app.schemas import ApiSettingResponse, ApiSettingUpsert, SettingsAuditResponse
from app.api.routes.auth import get_current_user
from app.services.settings_service import settings_service
from app.services.ai_service import ai_service
from app.services.notification_service import notification_service
from app.core.config import get_settings

logger = get_logger("api.settings")
router = APIRouter(prefix="/settings", tags=["Settings"])
settings = get_settings()


def _mask(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    return "••••••••"


def _require_admin(user: User) -> None:
    enforce_roles(user, {UserRole.director}, message="Not authorized")


def _audit_value(value: Optional[str], is_secret: bool) -> Optional[str]:
    if value is None:
        return None
    return _mask(value) if is_secret else value


@router.get("/", response_model=list[ApiSettingResponse])
async def list_settings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)

    result = await db.execute(select(ApiSetting).order_by(ApiSetting.key.asc()))
    settings_list = result.scalars().all()

    response = []
    for s in settings_list:
        response.append(ApiSettingResponse(
            key=s.key,
            value=_mask(s.value) if s.is_secret else s.value,
            description=s.description,
            is_secret=s.is_secret,
            has_value=bool(s.value),
            updated_at=s.updated_at,
        ))
    return response


@router.get("/{key}", response_model=ApiSettingResponse)
async def get_setting(
    key: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)

    result = await db.execute(select(ApiSetting).where(ApiSetting.key == key))
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Setting not found")

    return ApiSettingResponse(
        key=s.key,
        value=_mask(s.value) if s.is_secret else s.value,
        description=s.description,
        is_secret=s.is_secret,
        has_value=bool(s.value),
        updated_at=s.updated_at,
    )


@router.put("/{key}", response_model=ApiSettingResponse)
async def upsert_setting(
    key: str,
    data: ApiSettingUpsert,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)

    result = await db.execute(select(ApiSetting).where(ApiSetting.key == key))
    setting = result.scalar_one_or_none()

    if not setting:
        setting = ApiSetting(
            key=key,
            value=data.value,
            description=data.description,
            is_secret=data.is_secret if data.is_secret is not None else True,
            updated_at=datetime.utcnow(),
        )
        db.add(setting)
        db.add(SettingsAudit(
            key=key,
            action="create",
            old_value=None,
            new_value=_audit_value(data.value, setting.is_secret),
            actor=current_user.username,
        ))
    else:
        old_value = setting.value
        old_secret = setting.is_secret
        if data.value is not None:
            setting.value = data.value
        if data.description is not None:
            setting.description = data.description
        if data.is_secret is not None:
            setting.is_secret = data.is_secret
        setting.updated_at = datetime.utcnow()
        db.add(SettingsAudit(
            key=key,
            action="update",
            old_value=_audit_value(old_value, old_secret),
            new_value=_audit_value(setting.value, setting.is_secret),
            actor=current_user.username,
        ))

    await db.commit()
    await settings_service.set_value(key, setting.value)

    return ApiSettingResponse(
        key=setting.key,
        value=_mask(setting.value) if setting.is_secret else setting.value,
        description=setting.description,
        is_secret=setting.is_secret,
        has_value=bool(setting.value),
        updated_at=setting.updated_at,
    )


@router.post("/import-env", summary="Import settings from .env into DB (first-time)")
async def import_from_env(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)

    defaults = {
        "GEMINI_API_KEY": settings.gemini_api_key,
        "GEMINI_MODEL_FLASH": settings.gemini_model_flash,
        "GEMINI_MODEL_PRO": settings.gemini_model_pro,
        "GROQ_API_KEY": settings.groq_api_key,
        "YOUTUBE_DATA_API_KEY": settings.youtube_data_api_key,
        "YOUTUBE_TRENDS_ENABLED": str(settings.youtube_trends_enabled).lower(),
        "TELEGRAM_BOT_TOKEN": settings.telegram_bot_token,
        "TELEGRAM_CHANNEL_EDITORS": settings.telegram_channel_editors,
        "TELEGRAM_CHANNEL_ALERTS": settings.telegram_channel_alerts,
        "SLACK_WEBHOOK_URL": settings.slack_webhook_url,
        "MINIO_ENDPOINT": settings.minio_endpoint,
        "MINIO_ACCESS_KEY": settings.minio_access_key,
        "MINIO_SECRET_KEY": settings.minio_secret_key,
        "MINIO_BUCKET": settings.minio_bucket,
        "MINIO_USE_SSL": str(settings.minio_use_ssl).lower(),
    }

    for key, value in defaults.items():
        if value is None or value == "":
            continue
        result = await db.execute(select(ApiSetting).where(ApiSetting.key == key))
        existing = result.scalar_one_or_none()
        if not existing:
            is_secret = key.endswith("_KEY") or "TOKEN" in key or "WEBHOOK" in key or "SECRET" in key
            db.add(ApiSetting(
                key=key,
                value=str(value),
                description=None,
                is_secret=is_secret,
                updated_at=datetime.utcnow(),
            ))
            db.add(SettingsAudit(
                key=key,
                action="import",
                old_value=None,
                new_value=_audit_value(str(value), is_secret),
                actor=current_user.username,
            ))
    await db.commit()
    return {"message": "Imported settings from .env"}


@router.get("/audit", response_model=list[SettingsAuditResponse])
async def list_audit(
    limit: int = 200,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)

    result = await db.execute(
        select(SettingsAudit).order_by(SettingsAudit.created_at.desc()).limit(limit)
    )
    rows = result.scalars().all()
    return [SettingsAuditResponse(
        id=r.id,
        key=r.key,
        action=r.action,
        old_value=r.old_value,
        new_value=r.new_value,
        actor=r.actor,
        created_at=r.created_at,
    ) for r in rows]


@router.get("/test/{key}", summary="Test connectivity for a given API key")
async def test_setting(
    key: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)

    key = key.upper()
    if key == "GEMINI_API_KEY":
        gemini = await ai_service._get_gemini()
        return {"ok": gemini is not None}
    if key == "GROQ_API_KEY":
        groq = await ai_service._get_groq()
        return {"ok": groq is not None}
    if key == "YOUTUBE_DATA_API_KEY":
        api_key = await settings_service.get_value("YOUTUBE_DATA_API_KEY", settings.youtube_data_api_key or "")
        if not api_key:
            return {"ok": False, "missing": "YOUTUBE_DATA_API_KEY"}
        url = "https://www.googleapis.com/youtube/v3/videos"
        params = {
            "part": "id",
            "chart": "mostPopular",
            "regionCode": "US",
            "maxResults": 1,
            "key": api_key,
        }
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url, params=params) as resp:
                    if resp.status != 200:
                        return {"ok": False, "status": resp.status}
                    payload = await resp.json()
                    return {"ok": bool(payload.get("items"))}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)}
    if key == "YOUTUBE_TRENDS_ENABLED":
        enabled = await settings_service.get_value("YOUTUBE_TRENDS_ENABLED", str(settings.youtube_trends_enabled).lower())
        return {"ok": str(enabled).strip().lower() in {"1", "true", "yes", "on"}}
    if key in ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHANNEL_EDITORS", "TELEGRAM_CHANNEL_ALERTS"]:
        ok = await notification_service.send_telegram("✅ اختبار اتصال من لوحة المدير")
        return {"ok": ok}
    if key == "SLACK_WEBHOOK_URL":
        ok = await notification_service.send_slack("✅ اختبار اتصال من لوحة المدير")
        return {"ok": ok}
    if key in ["MINIO_ENDPOINT", "MINIO_ACCESS_KEY", "MINIO_SECRET_KEY", "MINIO_BUCKET", "MINIO_USE_SSL"]:
        # Simple check: all minio fields exist in DB
        required = ["MINIO_ENDPOINT", "MINIO_ACCESS_KEY", "MINIO_SECRET_KEY", "MINIO_BUCKET", "MINIO_USE_SSL"]
        for req in required:
            val = await settings_service.get_value(req, "")
            if not val:
                return {"ok": False, "missing": req}
        return {"ok": True}

    raise HTTPException(status_code=400, detail="Unsupported test key")
