"""Temporary payload storage for Document Intel async jobs."""

from __future__ import annotations

from uuid import uuid4

from redis.asyncio import Redis

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger("document_intel.job_storage")


class DocumentIntelJobStorage:
    def __init__(self) -> None:
        self._settings = get_settings()
        self._redis: Redis | None = None
        self._ttl_seconds = max(300, int(self._settings.document_intel_job_payload_ttl_seconds))

    async def _client(self) -> Redis:
        if self._redis is None:
            self._redis = Redis.from_url(self._settings.redis_queue_url, decode_responses=False)
        return self._redis

    async def save_payload(self, payload: bytes) -> str:
        key = f"doc-intel:upload:{uuid4()}"
        client = await self._client()
        await client.setex(key, self._ttl_seconds, payload)
        return key

    async def load_payload(self, key: str) -> bytes | None:
        client = await self._client()
        raw = await client.get(key)
        if raw is None:
            return None
        if isinstance(raw, bytes):
            return raw
        try:
            return raw.encode("utf-8")
        except Exception:  # noqa: BLE001
            logger.warning("document_intel_payload_decode_failed", key=key)
            return None

    async def delete_payload(self, key: str) -> None:
        client = await self._client()
        await client.delete(key)


document_intel_job_storage = DocumentIntelJobStorage()
