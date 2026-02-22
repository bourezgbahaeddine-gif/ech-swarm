"""
Echorouk Editorial OS — Settings Service
====================================
Centralized access to API settings stored in DB with cache.
"""

from datetime import timedelta
from typing import Optional

from sqlalchemy import select

from app.core.database import async_session
from app.models.settings import ApiSetting
from app.services.cache_service import cache_service


class SettingsService:
    """Fetch and cache API settings stored in the database."""

    async def get_value(self, key: str, default: Optional[str] = None) -> Optional[str]:
        cache_key = f"setting:{key}"
        cached = await cache_service.get(cache_key)
        if cached is not None:
            return cached if cached != "" else default

        async with async_session() as session:
            result = await session.execute(
                select(ApiSetting).where(ApiSetting.key == key)
            )
            setting = result.scalar_one_or_none()

        if setting and setting.value is not None:
            await cache_service.set(cache_key, setting.value, ttl=timedelta(minutes=5))
            return setting.value

        return default

    async def set_value(self, key: str, value: Optional[str]) -> None:
        cache_key = f"setting:{key}"
        if value is None:
            await cache_service.set(cache_key, "", ttl=timedelta(minutes=5))
        else:
            await cache_service.set(cache_key, value, ttl=timedelta(minutes=5))


# Singleton
settings_service = SettingsService()
