import asyncio

from app.services.notification_service import NotificationService
from app.services.cache_service import cache_service
from app.services.settings_service import settings_service


def test_published_quality_alert_deduplicates_repeated_topics(monkeypatch):
    service = NotificationService()
    memory_cache: dict[str, str] = {}
    sent_messages: list[str] = []

    async def fake_cache_get(key: str):
        return memory_cache.get(key)

    async def fake_cache_set(key: str, value: str, ttl=None):
        memory_cache[key] = value

    async def fake_get_value(_key: str, default=None):
        return default or "test"

    async def fake_send_telegram(message: str, channel=None, parse_mode="HTML"):
        sent_messages.append(message)
        return True

    monkeypatch.setattr(cache_service, "get", fake_cache_get)
    monkeypatch.setattr(cache_service, "set", fake_cache_set)
    monkeypatch.setattr(settings_service, "get_value", fake_get_value)
    monkeypatch.setattr(service, "send_telegram", fake_send_telegram)

    report = {
        "average_score": 68,
        "executed_at": "2026-02-18T16:00:00",
        "items": [
            {
                "title": "عنوان ضعيف 1",
                "url": "https://example.com/a?utm_source=rss",
                "score": 60,
                "grade": "ضعيف",
                "issues": ["مشكلة 1"],
            },
            {
                "title": "عنوان ضعيف 1",
                "url": "https://example.com/a",
                "score": 58,
                "grade": "ضعيف",
                "issues": ["مشكلة 2"],
            },
        ],
    }

    asyncio.run(service.send_published_quality_alert(report))
    assert len(sent_messages) == 1

    # same report should not resend due to dedup TTL cache
    asyncio.run(service.send_published_quality_alert(report))
    assert len(sent_messages) == 1
