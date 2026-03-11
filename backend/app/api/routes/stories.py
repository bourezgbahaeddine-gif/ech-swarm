from __future__ import annotations

from datetime import datetime, timedelta, timezone
import re
from collections import Counter
from difflib import SequenceMatcher
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.rbac import require_roles
from app.api.envelope import success_envelope
from app.core.database import get_db
from app.models import (
    Article,
    ArticleRelation,
    EditorialDraft,
    Story,
    StoryCluster,
    StoryClusterMember,
    StoryItem,
    StoryStatus,
)
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


def _article_status_value(article: Article | None) -> str | None:
    if article is None:
        return None
    status = getattr(article, "status", None)
    return status.value if status is not None else None


def _as_naive_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


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


def _normalize_story_text(*parts: str | None) -> str:
    return " ".join((part or "").strip().lower() for part in parts if part)


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in text for keyword in keywords)


def _detect_story_angles(article: Article) -> set[str]:
    title = (getattr(article, "title_ar", None) or getattr(article, "original_title", None) or "").strip()
    summary = (getattr(article, "summary", None) or "").strip()
    content = (getattr(article, "original_content", None) or "").strip()
    merged = _normalize_story_text(title, summary, content)

    detected: set[str] = set()
    urgency_value = str(getattr(getattr(article, "urgency", None), "value", "") or "").lower()
    is_breaking = bool(getattr(article, "is_breaking", False))
    if is_breaking or urgency_value in {"high", "critical"}:
        detected.add("breaking")

    follow_up_keywords = (
        "متابعة",
        "تطور",
        "تحديث",
        "حصيلة",
        "مستجد",
        "latest",
        "update",
        "follow-up",
    )
    if _contains_any(merged, follow_up_keywords):
        detected.add("follow_up")

    background_keywords = (
        "خلفية",
        "ملف",
        "سياق",
        "لماذا",
        "كيف",
        "شرح",
        "background",
        "context",
        "explainer",
    )
    if _contains_any(merged, background_keywords):
        detected.add("background")

    analysis_keywords = (
        "تحليل",
        "قراءة",
        "تداعيات",
        "سيناريو",
        "analysis",
        "insight",
        "outlook",
    )
    if _contains_any(merged, analysis_keywords):
        detected.add("analysis")

    reaction_keywords = (
        "رد",
        "تصريح",
        "قال",
        "أكد",
        "انتقد",
        "رحب",
        "comment",
        "reaction",
        "statement",
    )
    if _contains_any(merged, reaction_keywords):
        detected.add("reaction")

    has_numbers = bool(re.search(r"\d", merged))
    data_keywords = (
        "إحصاء",
        "نسبة",
        "مليون",
        "مليار",
        "percent",
        "statistics",
        "data",
    )
    if has_numbers or _contains_any(merged, data_keywords):
        detected.add("data")

    if not detected:
        detected.add("general")
    return detected


def _build_story_coverage_map(articles: list[Article]) -> dict:
    angle_specs = [
        ("breaking", "خبر عاجل", "تغطية الحدث الأساسي السريع"),
        ("follow_up", "متابعة", "متابعة التطورات والنتائج"),
        ("background", "خلفية", "سياق يشرح أصل القضية"),
        ("analysis", "تحليل", "قراءة أعمق للأثر والمعنى"),
        ("reaction", "ردود فعل", "تصريحات الأطراف المعنية"),
        ("data", "بيانات", "أرقام أو مؤشرات داعمة"),
    ]
    counts: Counter[str] = Counter()
    for article in articles:
        counts.update(_detect_story_angles(article))

    items: list[dict] = []
    available: list[str] = []
    missing: list[str] = []
    for key, label_ar, description in angle_specs:
        covered_count = int(counts.get(key, 0))
        status_value = "covered" if covered_count > 0 else "missing"
        items.append(
            {
                "key": key,
                "label": label_ar,
                "status": status_value,
                "count": covered_count,
                "description": description,
            }
        )
        if covered_count > 0:
            available.append(key)
        else:
            missing.append(key)

    coverage_score = round((len(available) / len(angle_specs)) * 100) if angle_specs else 100
    return {
        "score": coverage_score,
        "available": available,
        "missing": missing,
        "items": items,
    }


def _build_story_gaps(coverage_map: dict, sources_count: int, last_activity_at: str | None) -> list[dict]:
    gap_messages = {
        "breaking": ("لا يوجد خبر عاجل داخل القصة", "أنشئ نسخة خبر عاجل قصيرة لتثبيت الحدث الرئيسي."),
        "follow_up": ("لا توجد متابعة واضحة", "أضف خبر متابعة يشرح ما تغير بعد الخبر الأول."),
        "background": ("لا توجد خلفية كافية", "أضف فقرة/خبر خلفية لشرح السياق للقارئ."),
        "analysis": ("لا يوجد تحليل معمق", "أضف تحليل يربط المعطيات بالأثر المتوقع."),
        "reaction": ("لا توجد ردود فعل كافية", "أضف تصريحات الأطراف الأساسية أو ردود المؤسسات."),
        "data": ("لا توجد بيانات داعمة", "أضف أرقامًا موثقة أو مؤشرات رسمية تدعم السرد."),
    }
    severity_map = {
        "breaking": "high",
        "follow_up": "high",
        "background": "medium",
        "analysis": "medium",
        "reaction": "medium",
        "data": "medium",
    }
    gaps: list[dict] = []
    for angle in coverage_map.get("missing", []):
        title, recommendation = gap_messages.get(angle, ("فجوة تحريرية", "أضف مادة تغطي هذه الزاوية."))
        gaps.append(
            {
                "code": f"missing_{angle}",
                "severity": severity_map.get(angle, "medium"),
                "title": title,
                "recommendation": recommendation,
            }
        )

    if sources_count < 2:
        gaps.append(
            {
                "code": "low_source_diversity",
                "severity": "medium",
                "title": "تنوع المصادر منخفض",
                "recommendation": "عزز القصة بمصدر إضافي موثوق لتقليل الانحياز.",
            }
        )

    if last_activity_at:
        try:
            last_dt = datetime.fromisoformat(last_activity_at)
            age_hours = max(0.0, (datetime.utcnow() - last_dt).total_seconds() / 3600.0)
            if age_hours >= 24:
                gaps.append(
                    {
                        "code": "stale_story",
                        "severity": "low",
                        "title": "القصة بحاجة تحديث",
                        "recommendation": "مرّ أكثر من 24 ساعة دون تحديث؛ أضف متابعة جديدة.",
                    }
                )
        except ValueError:
            pass

    return gaps


def _story_templates() -> list[dict]:
    return [
        {
            "key": "breaking_story",
            "label": "قالب عاجل",
            "sections": ["المعلومة الأساسية", "التفاصيل الأولية", "ماذا بعد؟"],
        },
        {
            "key": "followup_story",
            "label": "قالب متابعة",
            "sections": ["ما الجديد", "ما تغير منذ الخبر السابق", "الأثر على الجمهور"],
        },
        {
            "key": "analysis_story",
            "label": "قالب تحليل",
            "sections": ["السياق", "المعطيات", "التحليل", "السيناريوهات"],
        },
    ]


async def _build_story_dossier_payload(
    db: AsyncSession,
    story: Story,
    timeline_limit: int,
) -> tuple[dict, list[Article]]:
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
    linked_articles: list[Article] = []

    for item in limited_items:
        if item.article_id:
            article = article_map.get(item.article_id)
            if not article:
                continue
            linked_articles.append(article)
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
    return dossier, linked_articles


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
            reloaded_reused_story = await story_repository.get_story_by_id(db, reused_story.id)
            if not reloaded_reused_story:
                raise HTTPException(status_code=404, detail="Story not found")
            return success_envelope(
                {
                    "story": _story_to_dict(reloaded_reused_story),
                    "linked_items_count": len(reloaded_reused_story.items or []),
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


@router.get("/clusters")
async def list_story_clusters(
    hours: int = Query(24, ge=1, le=168),
    category: str | None = Query(default=None),
    min_size: int = Query(2, ge=2, le=100),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(UserRole.director, UserRole.editor_chief, UserRole.journalist, UserRole.social_media, UserRole.print_editor)),
):
    """
    Return recent story clusters with members, top entities/topics, and observability metrics.
    """
    now = datetime.utcnow()
    cutoff = now - timedelta(hours=hours)

    size_subq = (
        select(
            StoryClusterMember.cluster_id.label("cluster_id"),
            func.count(StoryClusterMember.article_id).label("cluster_size"),
        )
        .group_by(StoryClusterMember.cluster_id)
        .subquery()
    )

    stmt = (
        select(StoryCluster, size_subq.c.cluster_size)
        .join(size_subq, size_subq.c.cluster_id == StoryCluster.id)
        .where(size_subq.c.cluster_size >= min_size)
        .order_by(desc(size_subq.c.cluster_size), desc(StoryCluster.updated_at), desc(StoryCluster.id))
        .limit(limit * 3)
    )
    if category:
        stmt = stmt.where(StoryCluster.category == category)

    cluster_rows = (await db.execute(stmt)).all()
    if not cluster_rows:
        return success_envelope(
            {
                "generated_at": now.isoformat(),
                "window_hours": hours,
                "filters": {"category": category, "min_size": min_size, "limit": limit},
                "metrics": {
                    "clusters_created": 0,
                    "average_cluster_size": 0.0,
                    "time_to_cluster_minutes": None,
                },
                "items": [],
            }
        )

    cluster_payload: dict[int, dict] = {}
    ordered_cluster_ids: list[int] = []
    for cluster, cluster_size in cluster_rows:
        cid = int(cluster.id)
        ordered_cluster_ids.append(cid)
        cluster_payload[cid] = {
            "cluster_id": cid,
            "cluster_key": cluster.cluster_key,
            "label": cluster.label,
            "category": cluster.category,
            "geography": cluster.geography,
            "created_at": cluster.created_at.isoformat() if cluster.created_at else None,
            "updated_at": cluster.updated_at.isoformat() if cluster.updated_at else None,
            "cluster_size": int(cluster_size or 0),
            "members": [],
            "top_entities": [],
            "top_topics": [],
            "latest_article_at": None,
            "_created_at_dt": cluster.created_at,
        }

    members_stmt = (
        select(StoryClusterMember, Article)
        .join(Article, Article.id == StoryClusterMember.article_id)
        .where(StoryClusterMember.cluster_id.in_(ordered_cluster_ids))
        .order_by(StoryClusterMember.cluster_id.asc(), desc(StoryClusterMember.score), desc(Article.crawled_at))
    )
    member_rows = (await db.execute(members_stmt)).all()

    cluster_entities: dict[int, Counter[str]] = {cid: Counter() for cid in ordered_cluster_ids}
    cluster_topics: dict[int, Counter[str]] = {cid: Counter() for cid in ordered_cluster_ids}
    cluster_latest_at: dict[int, datetime | None] = {cid: None for cid in ordered_cluster_ids}
    time_to_cluster_minutes: list[float] = []

    for member, article in member_rows:
        cid = int(member.cluster_id)
        if cid not in cluster_payload:
            continue

        article_ts = article.crawled_at or article.created_at
        member_ts = member.created_at or article_ts
        if article_ts and member_ts and member_ts >= article_ts:
            delta = (member_ts - article_ts).total_seconds() / 60.0
            time_to_cluster_minutes.append(max(0.0, delta))
        if article_ts:
            latest = cluster_latest_at[cid]
            cluster_latest_at[cid] = article_ts if latest is None or article_ts > latest else latest

        entities = article.entities if isinstance(article.entities, list) else []
        for entity in entities:
            cleaned = str(entity or "").strip()
            if cleaned:
                cluster_entities[cid][cleaned] += 1

        keywords = article.keywords if isinstance(article.keywords, list) else []
        for topic in keywords:
            cleaned = str(topic or "").strip()
            if cleaned:
                cluster_topics[cid][cleaned] += 1

        cluster_payload[cid]["members"].append(
            {
                "article_id": article.id,
                "score": round(float(member.score or 0.0), 4),
                "title": (article.title_ar or article.original_title or "").strip(),
                "source_name": article.source_name,
                "category": article.category.value if getattr(article, "category", None) else None,
                "status": _article_status_value(article),
                "crawled_at": article.crawled_at.isoformat() if article.crawled_at else None,
                "created_at": article.created_at.isoformat() if article.created_at else None,
            }
        )

    clusters_created = 0
    filtered_items: list[dict] = []
    for cid in ordered_cluster_ids:
        payload = cluster_payload[cid]
        latest = cluster_latest_at[cid]
        latest_dt = _as_naive_utc(latest)
        if latest_dt is None or latest_dt < cutoff:
            continue
        created_dt = _as_naive_utc(payload.get("_created_at_dt"))
        if created_dt and created_dt >= cutoff:
            clusters_created += 1
        payload["latest_article_at"] = latest.isoformat() if latest else None
        payload["top_entities"] = [
            {"entity": name, "count": int(count)}
            for name, count in cluster_entities[cid].most_common(5)
        ]
        payload["top_topics"] = [
            {"topic": name, "count": int(count)}
            for name, count in cluster_topics[cid].most_common(5)
        ]
        payload["members"] = payload["members"][:30]
        payload.pop("_created_at_dt", None)
        filtered_items.append(payload)

    filtered_items.sort(
        key=lambda item: (
            int(item.get("cluster_size", 0)),
            item.get("latest_article_at") or "",
        ),
        reverse=True,
    )
    filtered_items = filtered_items[:limit]

    avg_cluster_size = (
        round(
            sum(int(item.get("cluster_size", 0)) for item in filtered_items) / len(filtered_items),
            2,
        )
        if filtered_items
        else 0.0
    )
    avg_time_to_cluster = (
        round(sum(time_to_cluster_minutes) / len(time_to_cluster_minutes), 2)
        if time_to_cluster_minutes
        else None
    )

    return success_envelope(
        {
            "generated_at": now.isoformat(),
            "window_hours": hours,
            "filters": {"category": category, "min_size": min_size, "limit": limit},
            "metrics": {
                "clusters_created": clusters_created,
                "average_cluster_size": avg_cluster_size,
                "time_to_cluster_minutes": avg_time_to_cluster,
            },
            "items": filtered_items,
        }
    )


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
    dossier, _ = await _build_story_dossier_payload(db, story, timeline_limit=timeline_limit)
    return success_envelope(dossier)


@router.get("/{story_id}/control-center")
async def get_story_control_center(
    story_id: int,
    timeline_limit: int = Query(30, ge=10, le=120),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(UserRole.director, UserRole.editor_chief, UserRole.journalist, UserRole.social_media, UserRole.print_editor)),
):
    story = await story_repository.get_story_by_id(db, story_id)
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")

    dossier, linked_articles = await _build_story_dossier_payload(db, story, timeline_limit=timeline_limit)
    coverage_map = _build_story_coverage_map(linked_articles)
    source_count = len(dossier.get("highlights", {}).get("sources", []))
    last_activity_at = dossier.get("stats", {}).get("last_activity_at")
    gaps = _build_story_gaps(coverage_map=coverage_map, sources_count=source_count, last_activity_at=last_activity_at)

    control_center = {
        "story": dossier["story"],
        "overview": {
            "items_total": dossier["stats"]["items_total"],
            "articles_count": dossier["stats"]["articles_count"],
            "drafts_count": dossier["stats"]["drafts_count"],
            "last_activity_at": dossier["stats"]["last_activity_at"],
            "coverage_score": coverage_map["score"],
            "gaps_count": len(gaps),
        },
        "coverage_map": coverage_map,
        "gaps": gaps,
        "timeline": dossier["timeline"],
        "highlights": dossier["highlights"],
        "templates": _story_templates(),
    }
    return success_envelope(control_center)


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
