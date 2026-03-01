"""
Event reminder service.
Builds deduplicated T-24 / T-6 reminder notifications for in-app feed.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models import EventMemoItem
from app.services.cache_service import cache_service

logger = get_logger("event_reminder_service")

ACTIVE_STATUSES = {"planned", "monitoring"}
FEED_CACHE_KEY = "events:reminders:feed"


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        return None


class EventReminderService:
    async def scan_and_publish(self, db: AsyncSession, *, limit: int = 400) -> dict[str, int]:
        now = datetime.utcnow()
        window_end = now + timedelta(hours=24)
        result = await db.execute(
            select(EventMemoItem)
            .where(
                EventMemoItem.status.in_(list(ACTIVE_STATUSES)),
                EventMemoItem.starts_at > now,
                EventMemoItem.starts_at <= window_end,
            )
            .order_by(EventMemoItem.starts_at.asc(), EventMemoItem.priority.desc())
            .limit(max(20, min(limit, 1000)))
        )
        events = result.scalars().all()

        existing_feed = await cache_service.get_json(FEED_CACHE_KEY) or {"items": []}
        existing_items: list[dict[str, Any]] = list(existing_feed.get("items", []))
        created = 0
        created_t24 = 0
        created_t6 = 0

        for event in events:
            hours_to_start = max(0.0, (event.starts_at - now).total_seconds() / 3600.0)
            window = "t6" if hours_to_start <= 6 else "t24"
            dedup_key = f"events:reminder:sent:{window}:{event.id}:{event.starts_at.isoformat()}"
            if await cache_service.get(dedup_key):
                continue

            ttl_hours = 8 if window == "t6" else 30
            ttl = timedelta(hours=ttl_hours)
            await cache_service.set(dedup_key, "1", ttl=ttl)

            if window == "t6":
                created_t6 += 1
                severity = "high"
                message = "حدث مهم خلال أقل من 6 ساعات. جهّز التغطية فوراً."
            else:
                created_t24 += 1
                severity = "medium"
                message = "حدث خلال 24 ساعة. ابدأ التحضير التحريري."

            created_at = datetime.utcnow().isoformat()
            existing_items.append(
                {
                    "id": f"event-{window}-{event.id}-{int(event.starts_at.timestamp())}",
                    "type": "event_reminder",
                    "title": event.title,
                    "message": message,
                    "event_id": event.id,
                    "starts_at": event.starts_at.isoformat(),
                    "scope": event.scope,
                    "severity": severity,
                    "created_at": created_at,
                }
            )
            created += 1

        # Keep recent reminders only.
        cutoff = now - timedelta(hours=72)
        filtered: list[dict[str, Any]] = []
        for item in existing_items:
            created_at = _parse_iso(str(item.get("created_at") or ""))
            if created_at and created_at < cutoff:
                continue
            filtered.append(item)

        filtered.sort(
            key=lambda x: _parse_iso(str(x.get("created_at") or "")) or datetime.min,
            reverse=True,
        )
        filtered = filtered[:300]
        await cache_service.set_json(FEED_CACHE_KEY, {"items": filtered}, ttl=timedelta(days=4))

        if created:
            logger.info("event_reminders_emitted", total=created, t24=created_t24, t6=created_t6)

        return {"created": created, "t24": created_t24, "t6": created_t6, "tracked": len(filtered)}

    async def get_feed(self, *, limit: int = 30) -> list[dict[str, Any]]:
        payload = await cache_service.get_json(FEED_CACHE_KEY) or {"items": []}
        items = list(payload.get("items", []))
        items.sort(
            key=lambda x: _parse_iso(str(x.get("created_at") or "")) or datetime.min,
            reverse=True,
        )
        return items[: max(1, min(limit, 300))]


event_reminder_service = EventReminderService()

