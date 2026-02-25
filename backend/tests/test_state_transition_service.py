from __future__ import annotations

from dataclasses import dataclass

import pytest
from fastapi import HTTPException

from app.models.news import NewsStatus
from app.services.state_transition_service import state_transition_service


@dataclass
class _ArticleRow:
    id: int
    status: NewsStatus


class _Result:
    def __init__(self, article):
        self._article = article

    def scalar_one_or_none(self):
        return self._article


class _DbSessionStub:
    def __init__(self, article):
        self._article = article

    async def execute(self, _stmt):
        return _Result(self._article)


@pytest.mark.asyncio
async def test_transition_article_updates_status_when_current_matches() -> None:
    article = _ArticleRow(id=77, status=NewsStatus.CANDIDATE)
    db = _DbSessionStub(article)

    locked_article, previous = await state_transition_service.transition_article(
        db=db,
        article_id=article.id,
        target=NewsStatus.APPROVED_HANDOFF,
        expected_current=NewsStatus.CANDIDATE,
    )

    assert previous == NewsStatus.CANDIDATE
    assert locked_article.status == NewsStatus.APPROVED_HANDOFF


@pytest.mark.asyncio
async def test_transition_article_returns_409_when_state_already_changed() -> None:
    article = _ArticleRow(id=78, status=NewsStatus.APPROVED)
    db = _DbSessionStub(article)

    with pytest.raises(HTTPException) as exc_info:
        await state_transition_service.transition_article(
            db=db,
            article_id=article.id,
            target=NewsStatus.APPROVED_HANDOFF,
            expected_current=NewsStatus.CANDIDATE,
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["code"] == "transition_conflict"
