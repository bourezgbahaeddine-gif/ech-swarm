from app.agents.published_monitor import PublishedContentMonitorAgent


def test_audit_entry_flags_clickbait_and_spelling():
    agent = PublishedContentMonitorAgent()
    item = agent._audit_entry(
        title="صدمة.. لن تصدق ماذا حدث",
        summary="هذا الخبر فيه ان شاء الله خطأ شائع.",
        body_text="",
        url="https://example.com/a",
        published_at="2026-02-18T12:00:00",
    )
    assert item["score"] < 90
    assert item["metrics"]["clickbait_hits"] >= 1
    assert item["metrics"]["spelling_hits"] >= 1
    assert item["issues"]


def test_grade_thresholds():
    agent = PublishedContentMonitorAgent()
    assert agent._grade(95) == "ممتاز"
    assert agent._grade(80) == "جيد"
    assert agent._grade(65) == "مقبول"
    assert agent._grade(40) == "ضعيف"


def test_feed_dedup_removes_same_topic_variants():
    agent = PublishedContentMonitorAgent()
    entries = [
        {"title": "عنوان 1", "link": "https://example.com/a?utm_source=rss"},
        {"title": "عنوان 1", "link": "https://example.com/a"},
        {"title": "عنوان 2", "link": "https://example.com/b?oc=5"},
        {"title": "عنوان 2", "link": "https://example.com/b"},
    ]

    unique = agent._deduplicate_feed_entries(entries, limit=10)
    assert len(unique) == 2
