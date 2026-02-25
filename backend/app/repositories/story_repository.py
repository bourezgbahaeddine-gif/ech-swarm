from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Story, StoryItem, StoryStatus


class StoryRepository:
    async def create_story(
        self,
        db: AsyncSession,
        *,
        story_key: str,
        title: str,
        summary: str | None,
        category: str | None,
        geography: str | None,
        priority: int,
        created_by: str | None,
    ) -> Story:
        story = Story(
            story_key=story_key,
            title=title,
            summary=summary,
            category=category,
            geography=geography,
            priority=priority,
            status=StoryStatus.open,
            created_by=created_by,
            updated_by=created_by,
        )
        db.add(story)
        await db.flush()
        await db.refresh(story)
        return story

    async def get_story_by_id(self, db: AsyncSession, story_id: int) -> Story | None:
        row = await db.execute(
            select(Story)
            .options(selectinload(Story.items))
            .where(Story.id == story_id)
            .execution_options(populate_existing=True)
        )
        return row.scalar_one_or_none()

    async def list_stories(self, db: AsyncSession, *, limit: int = 100) -> list[Story]:
        rows = await db.execute(
            select(Story)
            .options(selectinload(Story.items))
            .order_by(Story.updated_at.desc(), Story.id.desc())
            .limit(max(1, min(limit, 500)))
        )
        return list(rows.scalars().all())

    async def link_article(
        self,
        db: AsyncSession,
        *,
        story_id: int,
        article_id: int,
        note: str | None,
        created_by: str | None,
    ) -> StoryItem:
        item = StoryItem(
            story_id=story_id,
            article_id=article_id,
            link_type="article",
            note=note,
            created_by=created_by,
        )
        db.add(item)
        await db.flush()
        await db.refresh(item)
        return item

    async def link_draft(
        self,
        db: AsyncSession,
        *,
        story_id: int,
        draft_id: int,
        note: str | None,
        created_by: str | None,
    ) -> StoryItem:
        item = StoryItem(
            story_id=story_id,
            draft_id=draft_id,
            link_type="draft",
            note=note,
            created_by=created_by,
        )
        db.add(item)
        await db.flush()
        await db.refresh(item)
        return item


story_repository = StoryRepository()
