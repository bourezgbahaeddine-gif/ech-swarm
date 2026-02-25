from __future__ import annotations

from datetime import datetime
import re
from collections import Counter
from difflib import SequenceMatcher
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.rbac import require_roles
from app.api.envelope import success_envelope
from app.core.database import get_db
from app.models import Article, ArticleRelation, EditorialDraft, Story, StoryItem, StoryStatus
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


def _tokenize(text: str | None) -> set[str]:
    if not text:
        return set()
    tokens = re.findall(r"[A-Za-z0-9\u0600-\u06FF]{3,}", text.lower())
    return {token for token in tokens if len(token) >= 3}


def _jaccard_similarity(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    union = left.union(right)
    if not union:
        return 0.0
    return len(left.intersection(right)) / len(union)


def _story_status_value(story: Story) -> str:
    return story.status.value if story.status else StoryStatus.open.value


def _story_linked_item_counts(story: Story) -> tuple[int, int]:
    article_count = 0
    draft_count = 0
    for item in story.items or []:
        if item.article_id:
            article_count += 1
        if item.draft_id:
            draft_count += 1
    return article_count, draft_count


def _story_to_dict(story: Story) -> dict:
    return {
        "id": story.id,
        "story_key": story.story_key,
        "title": story.title,
        "summary": story.summary,
        "category": story.category,
        "geography": story.geography,
        "priority": story.priority,
        "status": _story_status_value(story),
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
    current_user: User = Depends(require_roles(UserRole.director, UserRole.editor_chief, UserRole.journalist, UserRole.social_media, UserRole.print_editor)),
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


@router.post("/from-article/{article_id}", status_code=status.HTTP_201_CREATED)
async def create_story_from_article(
    article_id: int,
    reuse: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.director, UserRole.editor_chief, UserRole.journalist, UserRole.social_media, UserRole.print_editor)),
):
    article_row = await db.execute(select(Article).where(Article.id == article_id))
    article = article_row.scalar_one_or_none()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    if reuse:
        reused_row = await db.execute(
            select(Story)
            .join(StoryItem, StoryItem.story_id == Story.id)
            .where(StoryItem.article_id == article_id)
            .order_by(Story.updated_at.desc(), Story.id.desc())
            .limit(1)
        )
        reused_story = reused_row.scalar_one_or_none()
        if reused_story:
            return success_envelope(
                {
                    "story": _story_to_dict(reused_story),
                    "linked_items_count": len(reused_story.items or []),
                    "reused": True,
                }
            )

    story_key = f"STY-{datetime.utcnow():%Y%m%d}-{uuid4().hex[:8].upper()}"
    title = (article.title_ar or article.original_title or "").strip()
    if not title:
        title = f"Story #{article.id}"

    category_value = article.category.value if getattr(article, "category", None) else None
    geography_value = (getattr(article, "geography", None) or "").strip().upper() or None
    if not geography_value and category_value == "local_algeria":
        geography_value = "DZ"

    created_by = current_user.username or current_user.full_name_ar
    story = await story_repository.create_story(
        db,
        story_key=story_key,
        title=title,
        summary=(article.summary or "").strip() or None,
        category=category_value,
        geography=geography_value,
        priority=article.importance_score if article.importance_score and article.importance_score > 0 else 5,
        created_by=created_by,
    )
    item = await story_repository.link_article(
        db,
        story_id=story.id,
        article_id=article.id,
        note="created_from_article",
        created_by=created_by,
    )
    story.updated_by = created_by

    await audit_service.log_action(
        db,
        action="story_create_from_article",
        entity_type="story",
        entity_id=story.id,
        actor=current_user,
        details={"story_key": story.story_key, "article_id": article.id},
    )
    await audit_service.log_action(
        db,
        action="story_link_article",
        entity_type="story",
        entity_id=story.id,
        actor=current_user,
        details={"article_id": article.id, "story_item_id": item.id, "origin": "create_story_from_article"},
    )
    await db.commit()

    story = await story_repository.get_story_by_id(db, story.id)
    if not story:
        raise HTTPException(status_code=500, detail="Story created but failed to reload")

    return success_envelope(
        {
            "story": _story_to_dict(story),
            "linked_items_count": len(story.items or []),
            "reused": False,
        },
        status_code=status.HTTP_201_CREATED,
    )


@router.get("/suggest")
async def suggest_stories_for_article(
    article_id: int = Query(..., ge=1),
    limit: int = Query(10, ge=1, le=25),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(UserRole.director, UserRole.editor_chief, UserRole.journalist, UserRole.social_media, UserRole.print_editor)),
):
    article_row = await db.execute(select(Article).where(Article.id == article_id))
    article = article_row.scalar_one_or_none()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    candidate_count = max(60, limit * 10)
    stories = await story_repository.list_stories(db, limit=candidate_count)
    if not stories:
        return success_envelope([])

    article_title = (article.title_ar or article.original_title or "").strip()
    trigram_similarity_by_story: dict[int, float] = {}
    if article_title:
        story_ids = [story.id for story in stories]
        try:
            trigram_rows = await db.execute(
                select(
                    Story.id,
                    func.similarity(func.lower(Story.title), article_title.lower()).label("sim"),
                ).where(Story.id.in_(story_ids))
            )
            trigram_similarity_by_story = {
                int(story_id): max(float(similarity or 0.0), 0.0)
                for story_id, similarity in trigram_rows.all()
            }
        except SQLAlchemyError:
            trigram_similarity_by_story = {}

    relation_rows = await db.execute(
        select(ArticleRelation).where(
            or_(
                ArticleRelation.from_article_id == article_id,
                ArticleRelation.to_article_id == article_id,
            )
        )
    )
    related_article_ids: set[int] = set()
    for rel in relation_rows.scalars().all():
        if rel.from_article_id != article_id:
            related_article_ids.add(int(rel.from_article_id))
        if rel.to_article_id != article_id:
            related_article_ids.add(int(rel.to_article_id))

    article_title_tokens = _tokenize(article_title)
    article_entities_raw = article.entities if isinstance(article.entities, list) else []
    article_entities = {str(entity).strip().lower() for entity in article_entities_raw if str(entity).strip()}

    suggestions: list[dict] = []
    for story in stories:
        story_title = (story.title or "").strip()
        story_summary = (story.summary or "").strip()
        story_tokens = _tokenize(f"{story_title} {story_summary}")
        seq_score = SequenceMatcher(None, article_title.lower(), story_title.lower()).ratio() if story_title else 0.0
        token_score = _jaccard_similarity(article_title_tokens, story_tokens)
        trigram_score = trigram_similarity_by_story.get(story.id, 0.0)
        title_similarity = max(seq_score, token_score, trigram_score)

        entity_overlap = 0
        if article_entities and story_tokens:
            entity_overlap = sum(1 for entity in article_entities if entity in story_tokens)

        linked_article_ids = {item.article_id for item in (story.items or []) if item.article_id}
        relation_overlap = len(related_article_ids.intersection(linked_article_ids))

        score = 0.0
        reasons: list[str] = []
        if title_similarity > 0:
            score += title_similarity * 65.0
            reasons.append(f"title_similarity:{title_similarity:.2f}")
            if trigram_score > 0:
                reasons.append(f"title_similarity_trgm:{trigram_score:.2f}")
        if entity_overlap > 0:
            entity_score = min(20.0, entity_overlap * 4.0)
            score += entity_score
            reasons.append(f"entity_overlap:{entity_overlap}")
        if relation_overlap > 0:
            relation_score = min(15.0, relation_overlap * 5.0)
            score += relation_score
            reasons.append(f"related_article_overlap:{relation_overlap}")
        if article.category and story.category and article.category.value == story.category:
            score += 5.0
            reasons.append("category_match:1")

        if score <= 0:
            continue

        suggestions.append(
            {
                "story_id": story.id,
                "story_key": story.story_key,
                "title": story.title,
                "status": _story_status_value(story),
                "category": story.category,
                "geography": story.geography,
                "score": round(score, 2),
                "reasons": reasons,
                "last_updated_at": story.updated_at.isoformat() if story.updated_at else None,
            }
        )

    suggestions.sort(key=lambda item: (item["score"], item["last_updated_at"] or ""), reverse=True)
    return success_envelope(suggestions[:limit])


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


@router.get("/{story_id}/dossier")
async def get_story_dossier(
    story_id: int,
    timeline_limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(UserRole.director, UserRole.editor_chief, UserRole.journalist, UserRole.social_media, UserRole.print_editor)),
):
    story = await story_repository.get_story_by_id(db, story_id)
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")

    sorted_items = sorted(story.items or [], key=lambda item: item.created_at or datetime.min, reverse=True)
    limited_items = sorted_items[:timeline_limit]

    article_ids = [item.article_id for item in limited_items if item.article_id]
    draft_ids = [item.draft_id for item in limited_items if item.draft_id]

    article_map: dict[int, Article] = {}
    draft_map: dict[int, EditorialDraft] = {}

    if article_ids:
        article_rows = await db.execute(select(Article).where(Article.id.in_(article_ids)))
        article_map = {article.id: article for article in article_rows.scalars().all()}
    if draft_ids:
        draft_rows = await db.execute(select(EditorialDraft).where(EditorialDraft.id.in_(draft_ids)))
        draft_map = {draft.id: draft for draft in draft_rows.scalars().all()}

    timeline: list[dict] = []
    sources_counter: Counter[str] = Counter()
    activity_timestamps: list[datetime] = [value for value in [story.updated_at, story.created_at] if isinstance(value, datetime)]

    for item in limited_items:
        if item.article_id:
            article = article_map.get(item.article_id)
            if not article:
                continue
            title_value = (article.title_ar or article.original_title or "").strip()
            timeline.append(
                {
                    "type": "article",
                    "id": article.id,
                    "title": title_value,
                    "source_name": article.source_name,
                    "url": article.original_url,
                    "status": article.status.value if article.status else None,
                    "created_at": article.created_at.isoformat() if article.created_at else None,
                }
            )
            if article.source_name:
                sources_counter[str(article.source_name)] += 1
            if article.updated_at:
                activity_timestamps.append(article.updated_at)
            if article.created_at:
                activity_timestamps.append(article.created_at)
            continue

        if item.draft_id:
            draft = draft_map.get(item.draft_id)
            if not draft:
                continue
            timeline.append(
                {
                    "type": "draft",
                    "id": draft.id,
                    "title": draft.title or "Untitled Draft",
                    "work_id": draft.work_id,
                    "version": draft.version,
                    "status": draft.status,
                    "created_at": draft.created_at.isoformat() if draft.created_at else None,
                }
            )
            if draft.updated_at:
                activity_timestamps.append(draft.updated_at)
            if draft.created_at:
                activity_timestamps.append(draft.created_at)

    item_total = len(story.items or [])
    article_count, draft_count = _story_linked_item_counts(story)
    latest_titles: list[str] = []
    for entry in timeline:
        title = str(entry.get("title") or "").strip()
        if title and title not in latest_titles:
            latest_titles.append(title)
        if len(latest_titles) >= 5:
            break

    last_activity_at = max(activity_timestamps).isoformat() if activity_timestamps else None
    dossier = {
        "story": {
            "id": story.id,
            "story_key": story.story_key,
            "title": story.title,
            "status": _story_status_value(story),
            "category": story.category,
            "geography": story.geography,
            "priority": story.priority,
            "created_at": story.created_at.isoformat() if story.created_at else None,
            "updated_at": story.updated_at.isoformat() if story.updated_at else None,
        },
        "stats": {
            "items_total": item_total,
            "articles_count": article_count,
            "drafts_count": draft_count,
            "last_activity_at": last_activity_at,
        },
        "timeline": timeline,
        "highlights": {
            "latest_titles": latest_titles,
            "sources": [{"name": name, "count": count} for name, count in sources_counter.most_common(5)],
            "notes_count": sum(1 for item in (story.items or []) if item.note and item.note.strip()),
        },
    }
    return success_envelope(dossier)


@router.post("/{story_id}/link/article/{article_id}")
async def link_story_article(
    story_id: int,
    article_id: int,
    payload: StoryLinkRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.director, UserRole.editor_chief, UserRole.journalist, UserRole.social_media, UserRole.print_editor)),
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
    current_user: User = Depends(require_roles(UserRole.director, UserRole.editor_chief, UserRole.journalist, UserRole.social_media, UserRole.print_editor)),
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
