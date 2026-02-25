from __future__ import annotations

import json
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.api.routes import stories as stories_route
from app.models.story import StoryStatus


class _ScalarResult:
    def __init__(self, scalar_value):
        self._scalar_value = scalar_value

    def scalar_one_or_none(self):
        return self._scalar_value

    def scalars(self):
        return SimpleNamespace(all=lambda: list(self._scalar_value or []))


class _SequenceDb:
    def __init__(self, results):
        self._results = list(results)
        self._index = 0
        self.committed = False

    async def execute(self, _stmt):
        if self._index >= len(self._results):
            raise AssertionError("Unexpected DB execute call")
        item = self._results[self._index]
        self._index += 1
        return _ScalarResult(item)

    async def commit(self):
        self.committed = True

    async def rollback(self):
        return None


def _decode_response_data(response):
    payload = json.loads(response.body.decode("utf-8"))
    return payload["data"]


@pytest.mark.asyncio
async def test_create_story_from_article_smoke(monkeypatch):
    now = datetime.now(timezone.utc)
    article = SimpleNamespace(
        id=101,
        title_ar="عنوان عربي",
        original_title="Original title",
        summary="summary",
        category=SimpleNamespace(value="politics"),
        importance_score=8,
    )
    linked_item = SimpleNamespace(id=9001)
    reloaded_story = SimpleNamespace(
        id=77,
        story_key="STY-20260225-AAAA1111",
        title="عنوان عربي",
        summary="summary",
        category="politics",
        geography=None,
        priority=8,
        status=StoryStatus.open,
        created_by="editor",
        updated_by="editor",
        created_at=now,
        updated_at=now,
        items=[
            SimpleNamespace(
                id=9001,
                link_type="article",
                article_id=101,
                draft_id=None,
                note="created_from_article",
                created_by="editor",
                created_at=now,
            )
        ],
    )
    db = _SequenceDb([article])
    current_user = SimpleNamespace(id=1, username="editor", full_name_ar="Editor")

    async def _noop_audit(*_args, **_kwargs):
        return None

    async def _fake_create_story(*_args, **_kwargs):
        return SimpleNamespace(id=77, items=[], updated_by=None)

    async def _fake_link_article(*_args, **_kwargs):
        return linked_item

    async def _fake_get_story_by_id(*_args, **_kwargs):
        return reloaded_story

    monkeypatch.setattr(stories_route.audit_service, "log_action", _noop_audit)
    monkeypatch.setattr(stories_route.story_repository, "create_story", _fake_create_story)
    monkeypatch.setattr(stories_route.story_repository, "link_article", _fake_link_article)
    monkeypatch.setattr(stories_route.story_repository, "get_story_by_id", _fake_get_story_by_id)

    response = await stories_route.create_story_from_article(
        article_id=101,
        reuse=False,
        db=db,
        current_user=current_user,
    )
    data = _decode_response_data(response)

    assert db.committed is True
    assert data["reused"] is False
    assert data["story"]["id"] == 77
    assert data["linked_items_count"] == 1


@pytest.mark.asyncio
async def test_suggest_stories_returns_ranked_list(monkeypatch):
    now = datetime.now(timezone.utc)
    article = SimpleNamespace(
        id=501,
        title_ar="اجتماع الحكومة حول الاقتصاد",
        original_title="",
        entities=["الحكومة", "الاقتصاد"],
        category=SimpleNamespace(value="economy"),
    )
    relation = SimpleNamespace(from_article_id=501, to_article_id=77)
    story_match = SimpleNamespace(
        id=1,
        story_key="STY-ONE",
        title="الحكومة تناقش الاقتصاد الوطني",
        summary="ملف اقتصادي",
        status=StoryStatus.open,
        category="economy",
        geography="DZ",
        updated_at=now,
        items=[SimpleNamespace(article_id=77, draft_id=None)],
    )
    story_weak = SimpleNamespace(
        id=2,
        story_key="STY-TWO",
        title="رياضة عالمية",
        summary="كرة قدم",
        status=StoryStatus.open,
        category="sports",
        geography="WORLD",
        updated_at=now,
        items=[SimpleNamespace(article_id=88, draft_id=None)],
    )
    db = _SequenceDb([article, [relation]])
    current_user = SimpleNamespace(id=1, username="editor", full_name_ar="Editor")

    async def _fake_list_stories(*_args, **_kwargs):
        return [story_match, story_weak]

    monkeypatch.setattr(stories_route.story_repository, "list_stories", _fake_list_stories)

    response = await stories_route.suggest_stories_for_article(
        article_id=501,
        limit=10,
        db=db,
        _=current_user,
    )
    data = _decode_response_data(response)

    assert len(data) >= 1
    assert data[0]["story_id"] == 1
    assert data[0]["score"] >= data[-1]["score"]
    assert any(reason.startswith("title_similarity:") for reason in data[0]["reasons"])


@pytest.mark.asyncio
async def test_dossier_returns_timeline(monkeypatch):
    now = datetime.now(timezone.utc)
    story = SimpleNamespace(
        id=700,
        story_key="STY-DOSSIER",
        title="Story dossier",
        status=StoryStatus.monitoring,
        category="politics",
        geography="DZ",
        priority=7,
        created_at=now,
        updated_at=now,
        items=[
            SimpleNamespace(id=1, article_id=11, draft_id=None, note="x", created_at=now),
            SimpleNamespace(id=2, article_id=None, draft_id=22, note=None, created_at=now),
        ],
    )
    article = SimpleNamespace(
        id=11,
        title_ar="عنوان الخبر",
        original_title="",
        source_name="APS",
        original_url="https://example.com/11",
        status=SimpleNamespace(value="approved_handoff"),
        created_at=now,
        updated_at=now,
    )
    draft = SimpleNamespace(
        id=22,
        title="عنوان المسودة",
        work_id="WRK-22",
        version=3,
        status="draft",
        created_at=now,
        updated_at=now,
    )
    db = _SequenceDb([[article], [draft]])
    current_user = SimpleNamespace(id=1, username="editor", full_name_ar="Editor")

    async def _fake_get_story(*_args, **_kwargs):
        return story

    monkeypatch.setattr(stories_route.story_repository, "get_story_by_id", _fake_get_story)

    response = await stories_route.get_story_dossier(
        story_id=700,
        timeline_limit=20,
        db=db,
        _=current_user,
    )
    data = _decode_response_data(response)

    assert data["story"]["id"] == 700
    assert data["stats"]["items_total"] == 2
    assert len(data["timeline"]) == 2
    assert data["highlights"]["sources"][0]["name"] == "APS"
