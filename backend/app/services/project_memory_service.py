from __future__ import annotations

from datetime import datetime, timedelta
import re

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Article, ProjectMemoryEvent, ProjectMemoryItem
from app.models.user import User


SPACE_RE = re.compile(r"\s+")
TOKEN_RE = re.compile(r"[\w\u0600-\u06FF]{3,}", re.UNICODE)

ALLOWED_SUBTYPES = {
    "general",
    "style_rule",
    "editorial_decision",
    "fact_pattern",
    "coverage_lesson",
    "source_note",
    "story_context",
    "event_playbook",
    "incident_postmortem",
}
ALLOWED_FRESHNESS = {"stable", "review_soon", "expired"}


class ProjectMemoryService:
    @staticmethod
    def _normalize_text(value: str) -> str:
        return SPACE_RE.sub(" ", (value or "").strip())

    @staticmethod
    def _normalize_tags(tags: list[str] | None) -> list[str]:
        if not tags:
            return []
        out: list[str] = []
        for tag in tags:
            clean = SPACE_RE.sub(" ", (tag or "").strip().lower())
            if not clean:
                continue
            if clean not in out:
                out.append(clean[:64])
        return out[:12]

    @staticmethod
    def _normalize_subtype(value: str | None) -> str:
        candidate = SPACE_RE.sub("_", (value or "general").strip().lower())
        return candidate if candidate in ALLOWED_SUBTYPES else "general"

    @staticmethod
    def _normalize_freshness(value: str | None) -> str:
        candidate = (value or "stable").strip().lower()
        return candidate if candidate in ALLOWED_FRESHNESS else "stable"

    @staticmethod
    def _tokenize(values: list[str | None]) -> list[str]:
        seen: list[str] = []
        for value in values:
            for token in TOKEN_RE.findall((value or "").lower()):
                if token not in seen:
                    seen.append(token)
        return seen[:18]

    async def log_event(
        self,
        db: AsyncSession,
        *,
        memory_id: int,
        event_type: str,
        actor: User | None = None,
        note: str | None = None,
    ) -> None:
        db.add(
            ProjectMemoryEvent(
                memory_id=memory_id,
                event_type=event_type[:32],
                note=self._normalize_text(note) if note else None,
                actor_user_id=actor.id if actor else None,
                actor_username=actor.username if actor else None,
            )
        )
        await db.flush()

    async def create_item(
        self,
        db: AsyncSession,
        *,
        actor: User,
        memory_type: str,
        title: str,
        content: str,
        tags: list[str] | None,
        source_type: str | None,
        source_ref: str | None,
        article_id: int | None,
        importance: int,
        memory_subtype: str | None = None,
        freshness_status: str | None = None,
        valid_until: datetime | None = None,
    ) -> ProjectMemoryItem:
        item = ProjectMemoryItem(
            memory_type=memory_type,
            memory_subtype=self._normalize_subtype(memory_subtype),
            title=self._normalize_text(title)[:512],
            content=self._normalize_text(content),
            tags=self._normalize_tags(tags),
            source_type=self._normalize_text(source_type)[:64] if source_type else None,
            source_ref=self._normalize_text(source_ref)[:512] if source_ref else None,
            article_id=article_id,
            importance=importance,
            freshness_status=self._normalize_freshness(freshness_status),
            valid_until=valid_until,
            created_by_user_id=actor.id,
            created_by_username=actor.username,
            updated_by_user_id=actor.id,
            updated_by_username=actor.username,
        )
        db.add(item)
        await db.flush()
        await self.log_event(db, memory_id=item.id, event_type="created", actor=actor)
        return item

    async def search_items(
        self,
        db: AsyncSession,
        *,
        q: str | None,
        memory_type: str | None,
        status: str,
        tag: str | None,
        memory_subtype: str | None,
        freshness_status: str | None,
        page: int,
        per_page: int,
    ) -> tuple[list[ProjectMemoryItem], int]:
        filters = [ProjectMemoryItem.status == status]
        if memory_type:
            filters.append(ProjectMemoryItem.memory_type == memory_type)
        if memory_subtype:
            filters.append(ProjectMemoryItem.memory_subtype == self._normalize_subtype(memory_subtype))
        if freshness_status:
            filters.append(ProjectMemoryItem.freshness_status == self._normalize_freshness(freshness_status))
        if tag:
            filters.append(ProjectMemoryItem.tags.contains([tag.lower().strip()]))
        if q:
            like = f"%{q.strip()}%"
            filters.append(
                or_(
                    ProjectMemoryItem.title.ilike(like),
                    ProjectMemoryItem.content.ilike(like),
                    ProjectMemoryItem.source_ref.ilike(like),
                )
            )

        where = and_(*filters)
        total_q = await db.execute(select(func.count(ProjectMemoryItem.id)).where(where))
        total = int(total_q.scalar() or 0)

        rows = await db.execute(
            select(ProjectMemoryItem)
            .where(where)
            .order_by(ProjectMemoryItem.updated_at.desc(), ProjectMemoryItem.id.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        return list(rows.scalars().all()), total

    async def recommend_items(
        self,
        db: AsyncSession,
        *,
        article_id: int | None,
        q: str | None,
        tags: list[str] | None,
        memory_type: str | None,
        limit: int,
    ) -> list[dict]:
        filters = [ProjectMemoryItem.status == "active"]
        if memory_type:
            filters.append(ProjectMemoryItem.memory_type == memory_type)

        now = datetime.utcnow()
        filters.append(or_(ProjectMemoryItem.valid_until.is_(None), ProjectMemoryItem.valid_until >= now))

        rows = await db.execute(
            select(ProjectMemoryItem)
            .where(and_(*filters))
            .order_by(ProjectMemoryItem.importance.desc(), ProjectMemoryItem.updated_at.desc())
            .limit(250)
        )
        items = list(rows.scalars().all())
        article = None
        if article_id is not None:
            article_row = await db.execute(select(Article).where(Article.id == article_id))
            article = article_row.scalar_one_or_none()

        normalized_tags = self._normalize_tags(tags)
        article_tokens = self._tokenize(
            [
                article.title_ar if article else None,
                article.original_title if article else None,
                article.summary if article else None,
                article.source_name if article else None,
                q,
            ]
            + (article.keywords if article and isinstance(article.keywords, list) else [])
        )

        recommendations: list[dict] = []
        for item in items:
            score = float(item.importance or 0)
            reasons: list[str] = []
            matched_signals: list[str] = []

            if article_id is not None and item.article_id == article_id:
                score += 12.0
                reasons.append("مرتبط مباشرة بهذه المادة")
                matched_signals.append("same_article")

            tag_overlap = len(set(item.tags or []).intersection(normalized_tags))
            if tag_overlap:
                score += tag_overlap * 2.5
                reasons.append(f"يشارك {tag_overlap} وسم/وسوم مع المادة الحالية")
                matched_signals.append("tag_overlap")

            haystack = " ".join(
                filter(
                    None,
                    [
                        (item.title or "").lower(),
                        (item.content or "").lower(),
                        (item.source_ref or "").lower(),
                        " ".join(item.tags or []),
                    ],
                )
            )
            token_hits = [token for token in article_tokens if token in haystack]
            if token_hits:
                score += min(len(token_hits), 4) * 1.5
                reasons.append("يتقاطع مع موضوع أو كيان موجود في المادة الحالية")
                matched_signals.append("topic_overlap")

            if item.memory_subtype in {"style_rule", "editorial_decision"}:
                score += 1.25
            if item.freshness_status == "review_soon":
                score -= 0.5

            reason = reasons[0] if reasons else "مفيد كسياق تحريري قريب من المادة الحالية"
            recommendations.append(
                {
                    "id": item.id,
                    "memory_type": item.memory_type,
                    "memory_subtype": item.memory_subtype,
                    "title": item.title,
                    "content": item.content,
                    "tags": item.tags or [],
                    "source_type": item.source_type,
                    "source_ref": item.source_ref,
                    "article_id": item.article_id,
                    "status": item.status,
                    "importance": item.importance,
                    "freshness_status": item.freshness_status,
                    "valid_until": item.valid_until,
                    "created_by_user_id": item.created_by_user_id,
                    "created_by_username": item.created_by_username,
                    "updated_by_user_id": item.updated_by_user_id,
                    "updated_by_username": item.updated_by_username,
                    "created_at": item.created_at,
                    "updated_at": item.updated_at,
                    "recommendation_reason": reason,
                    "recommendation_score": round(score, 2),
                    "matched_signals": matched_signals,
                }
            )

        recommendations.sort(key=lambda item: (item["recommendation_score"], item["updated_at"]), reverse=True)
        return recommendations[:limit]

    async def overview(self, db: AsyncSession) -> dict[str, int]:
        total_active = int(
            (await db.execute(select(func.count(ProjectMemoryItem.id)).where(ProjectMemoryItem.status == "active"))).scalar() or 0
        )
        operational_count = int(
            (
                await db.execute(
                    select(func.count(ProjectMemoryItem.id)).where(
                        and_(ProjectMemoryItem.status == "active", ProjectMemoryItem.memory_type == "operational")
                    )
                )
            ).scalar()
            or 0
        )
        knowledge_count = int(
            (
                await db.execute(
                    select(func.count(ProjectMemoryItem.id)).where(
                        and_(ProjectMemoryItem.status == "active", ProjectMemoryItem.memory_type == "knowledge")
                    )
                )
            ).scalar()
            or 0
        )
        session_count = int(
            (
                await db.execute(
                    select(func.count(ProjectMemoryItem.id)).where(
                        and_(ProjectMemoryItem.status == "active", ProjectMemoryItem.memory_type == "session")
                    )
                )
            ).scalar()
            or 0
        )
        archived_count = int(
            (await db.execute(select(func.count(ProjectMemoryItem.id)).where(ProjectMemoryItem.status == "archived"))).scalar() or 0
        )
        recent_updates = int(
            (
                await db.execute(
                    select(func.count(ProjectMemoryItem.id)).where(
                        ProjectMemoryItem.updated_at >= datetime.utcnow() - timedelta(hours=24)
                    )
                )
            ).scalar()
            or 0
        )
        return {
            "total_active": total_active,
            "operational_count": operational_count,
            "knowledge_count": knowledge_count,
            "session_count": session_count,
            "archived_count": archived_count,
            "recent_updates": recent_updates,
        }


project_memory_service = ProjectMemoryService()
