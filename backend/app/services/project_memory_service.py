from __future__ import annotations

from datetime import datetime, timedelta
import re

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ProjectMemoryEvent, ProjectMemoryItem
from app.models.user import User


SPACE_RE = re.compile(r"\s+")


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
    ) -> ProjectMemoryItem:
        item = ProjectMemoryItem(
            memory_type=memory_type,
            title=self._normalize_text(title)[:512],
            content=self._normalize_text(content),
            tags=self._normalize_tags(tags),
            source_type=self._normalize_text(source_type)[:64] if source_type else None,
            source_ref=self._normalize_text(source_ref)[:512] if source_ref else None,
            article_id=article_id,
            importance=importance,
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
        page: int,
        per_page: int,
    ) -> tuple[list[ProjectMemoryItem], int]:
        filters = [ProjectMemoryItem.status == status]
        if memory_type:
            filters.append(ProjectMemoryItem.memory_type == memory_type)
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
