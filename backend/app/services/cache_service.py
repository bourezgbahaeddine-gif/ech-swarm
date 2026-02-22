"""
Echorouk Editorial OS — Cache Service
====================================
Redis-based caching for deduplication and rate limiting.
Implements the Global Cache System (24h URL cache).
"""

import json
from typing import Optional
from datetime import timedelta

import redis.asyncio as redis

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger("cache_service")
settings = get_settings()

# Cache TTL defaults
URL_CACHE_TTL = timedelta(hours=24)
ANALYSIS_CACHE_TTL = timedelta(hours=12)
TREND_CACHE_TTL = timedelta(minutes=30)


class CacheService:
    """Redis-based cache for deduplication and performance."""

    def __init__(self):
        self._client: Optional[redis.Redis] = None

    async def connect(self):
        """Initialize Redis connection."""
        try:
            self._client = redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            await self._client.ping()
            logger.info("redis_connected", url=settings.redis_host)
        except Exception as e:
            logger.error("redis_connection_failed", error=str(e))
            self._client = None

    async def disconnect(self):
        """Close Redis connection."""
        if self._client:
            await self._client.close()

    @property
    def connected(self) -> bool:
        return self._client is not None

    # ── URL Dedup Cache ──

    async def is_url_processed(self, url_hash: str) -> bool:
        """Check if a URL has been processed in the last 24 hours."""
        if not self._client:
            return False
        try:
            return await self._client.exists(f"url:{url_hash}") > 0
        except Exception:
            return False

    async def mark_url_processed(self, url_hash: str, article_id: int = 0):
        """Mark a URL as processed with 24h TTL."""
        if not self._client:
            return
        try:
            await self._client.setex(
                f"url:{url_hash}",
                URL_CACHE_TTL,
                str(article_id),
            )
        except Exception as e:
            logger.warning("cache_write_error", error=str(e))

    # ── Recent Titles Cache (for fuzzy dedup) ──

    async def get_recent_titles(self, limit: int = 50) -> list[str]:
        """Get the last N article titles for fuzzy matching."""
        if not self._client:
            return []
        try:
            titles = await self._client.lrange("recent_titles", 0, limit - 1)
            return titles
        except Exception:
            return []

    async def add_recent_title(self, title: str):
        """Add a title to the recent titles list (FIFO, max 200)."""
        if not self._client:
            return
        try:
            await self._client.lpush("recent_titles", title)
            await self._client.ltrim("recent_titles", 0, 199)
        except Exception as e:
            logger.warning("cache_title_error", error=str(e))

    # ── General Cache ──

    async def get(self, key: str) -> Optional[str]:
        """Get a value from cache."""
        if not self._client:
            return None
        try:
            return await self._client.get(key)
        except Exception:
            return None

    async def set(self, key: str, value: str, ttl: timedelta = None):
        """Set a value in cache with optional TTL."""
        if not self._client:
            return
        try:
            if ttl:
                await self._client.setex(key, ttl, value)
            else:
                await self._client.set(key, value)
        except Exception as e:
            logger.warning("cache_set_error", error=str(e))

    async def get_json(self, key: str) -> Optional[dict]:
        """Get a JSON value from cache."""
        raw = await self.get(key)
        if raw:
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return None
        return None

    async def set_json(self, key: str, value: dict, ttl: timedelta = None):
        """Set a JSON value in cache."""
        await self.set(key, json.dumps(value, ensure_ascii=False), ttl)

    # ── Counters (Observability) ──

    async def increment_counter(self, key: str) -> int:
        """Increment a counter (for tracking AI calls, etc.)."""
        if not self._client:
            return 0
        try:
            count = await self._client.incr(f"counter:{key}")
            # Auto-expire counters daily
            await self._client.expire(f"counter:{key}", 86400)
            return count
        except Exception:
            return 0

    async def get_counter(self, key: str) -> int:
        """Get current counter value."""
        if not self._client:
            return 0
        try:
            val = await self._client.get(f"counter:{key}")
            return int(val) if val else 0
        except Exception:
            return 0


# Singleton
cache_service = CacheService()
