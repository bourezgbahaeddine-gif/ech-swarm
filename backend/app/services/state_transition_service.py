from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.news.state_machine import validate_transition
from app.models.news import Article, NewsStatus


class StateTransitionService:
    def assert_transition(self, *, current: NewsStatus, target: NewsStatus, entity: str = "article") -> None:
        result = validate_transition(current, target)
        if result.valid:
            return
        raise HTTPException(
            status_code=409,
            detail={
                "code": "invalid_state_transition",
                "entity": entity,
                "from_state": current.value,
                "to_state": target.value,
                "allowed_targets": [item.value for item in result.allowed_targets],
            },
        )

    async def transition_article(
        self,
        *,
        db: AsyncSession,
        article_id: int,
        target: NewsStatus,
        expected_current: NewsStatus | None = None,
        entity: str | None = None,
        lock_nowait: bool = True,
    ) -> tuple[Article, NewsStatus]:
        entity_name = entity or f"article:{article_id}"
        try:
            row = await db.execute(
                select(Article)
                .where(Article.id == article_id)
                .with_for_update(nowait=lock_nowait)
            )
        except OperationalError as exc:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "transition_conflict",
                    "entity": entity_name,
                    "message": "The article is being updated by another operation. Retry.",
                },
            ) from exc

        article = row.scalar_one_or_none()
        if not article:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": "article_not_found",
                    "entity": entity_name,
                },
            )

        current_status = article.status or NewsStatus.NEW
        if expected_current and current_status != expected_current:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "transition_conflict",
                    "entity": entity_name,
                    "message": "The article state changed before transition.",
                    "expected_current_state": expected_current.value,
                    "actual_current_state": current_status.value,
                    "target_state": target.value,
                },
            )

        self.assert_transition(current=current_status, target=target, entity=entity_name)
        article.status = target
        return article, current_status


state_transition_service = StateTransitionService()
