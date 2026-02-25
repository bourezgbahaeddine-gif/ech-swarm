from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.rbac import require_roles
from app.api.envelope import success_envelope
from app.core.database import get_db
from app.models import Article, EditorialDraft, Story, StoryStatus
from app.models.user import User, UserRole
from app.repositories.story_repository import story_repository
from app.services.audit_service import audit_service

router = APIRouter(prefix="/stories", tags=["Stories"])


class StoryCreateRequest(BaseModel):
    title: str = Field(..., min_length=4, max_length=1024)
    summary: str | None = Field(default=None, max_length=5000)
    category: str | None = Field(default=None, max_length=80)
    geography: str | None = Field(default=None, max_length=24)
    priority: int = Field(default=5, ge=1, le=10)


class StoryLinkRequest(BaseModel):
    note: str | None = Field(default=None, max_length=1000)


def _story_to_dict(story: Story) -> dict:
    return {
        "id": story.id,
        "story_key": story.story_key,
        "title": story.title,
        "summary": story.summary,
        "category": story.category,
        "geography": story.geography,
        "priority": story.priority,
        "status": story.status.value if story.status else StoryStatus.open.value,
        "created_by": story.created_by,
        "updated_by": story.updated_by,
        "created_at": story.created_at.isoformat() if isinstance(story.created_at, datetime) else None,
        "updated_at": story.updated_at.isoformat() if isinstance(story.updated_at, datetime) else None,
        "items": [
            {
                "id": item.id,
                "link_type": item.link_type,
                "article_id": item.article_id,
                "draft_id": item.draft_id,
                "note": item.note,
                "created_by": item.created_by,
                "created_at": item.created_at.isoformat() if isinstance(item.created_at, datetime) else None,
            }
            for item in (story.items or [])
        ],
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_story(
    payload: StoryCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.director, UserRole.editor_chief, UserRole.journalist)),
):
    story_key = f"STY-{datetime.utcnow():%Y%m%d}-{uuid4().hex[:8].upper()}"
    story = await story_repository.create_story(
        db,
        story_key=story_key,
        title=payload.title.strip(),
        summary=(payload.summary or "").strip() or None,
        category=(payload.category or "").strip() or None,
        geography=(payload.geography or "").strip().upper() or None,
        priority=payload.priority,
        created_by=current_user.username,
    )
    await audit_service.log_action(
        db,
        action="story_create",
        entity_type="story",
        entity_id=story.id,
        actor=current_user,
        details={"story_key": story.story_key, "title": story.title},
    )
    await db.commit()
    await db.refresh(story)
    return success_envelope(_story_to_dict(story), status_code=status.HTTP_201_CREATED)


@router.get("")
async def list_stories(
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(UserRole.director, UserRole.editor_chief, UserRole.journalist, UserRole.social_media, UserRole.print_editor)),
):
    stories = await story_repository.list_stories(db, limit=limit)
    return success_envelope([_story_to_dict(story) for story in stories])


@router.get("/{story_id}")
async def get_story(
    story_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(UserRole.director, UserRole.editor_chief, UserRole.journalist, UserRole.social_media, UserRole.print_editor)),
):
    story = await story_repository.get_story_by_id(db, story_id)
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")
    return success_envelope(_story_to_dict(story))


@router.post("/{story_id}/link/article/{article_id}")
async def link_story_article(
    story_id: int,
    article_id: int,
    payload: StoryLinkRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.director, UserRole.editor_chief, UserRole.journalist)),
):
    story = await story_repository.get_story_by_id(db, story_id)
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")

    article_row = await db.execute(select(Article).where(Article.id == article_id))
    if not article_row.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Article not found")

    try:
        item = await story_repository.link_article(
            db,
            story_id=story_id,
            article_id=article_id,
            note=(payload.note or "").strip() or None,
            created_by=current_user.username,
        )
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Article already linked to this story") from exc

    story.updated_by = current_user.username
    await audit_service.log_action(
        db,
        action="story_link_article",
        entity_type="story",
        entity_id=story_id,
        actor=current_user,
        details={"article_id": article_id, "story_item_id": item.id},
    )
    await db.commit()
    return success_envelope({"story_id": story_id, "article_id": article_id, "story_item_id": item.id})


@router.post("/{story_id}/link/draft/{draft_id}")
async def link_story_draft(
    story_id: int,
    draft_id: int,
    payload: StoryLinkRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.director, UserRole.editor_chief, UserRole.journalist)),
):
    story = await story_repository.get_story_by_id(db, story_id)
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")

    draft_row = await db.execute(select(EditorialDraft).where(EditorialDraft.id == draft_id))
    if not draft_row.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Draft not found")

    try:
        item = await story_repository.link_draft(
            db,
            story_id=story_id,
            draft_id=draft_id,
            note=(payload.note or "").strip() or None,
            created_by=current_user.username,
        )
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Draft already linked to this story") from exc

    story.updated_by = current_user.username
    await audit_service.log_action(
        db,
        action="story_link_draft",
        entity_type="story",
        entity_id=story_id,
        actor=current_user,
        details={"draft_id": draft_id, "story_item_id": item.id},
    )
    await db.commit()
    return success_envelope({"story_id": story_id, "draft_id": draft_id, "story_item_id": item.id})
