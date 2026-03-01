"""
Digital team service.
Provides channel-scope enforcement, program-grid import, and auto social task generation.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from pathlib import Path

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models import Article, EventMemoItem, NewsStatus
from app.models.digital_team import DigitalTeamScope, ProgramSlot, SocialPost, SocialTask
from app.models.user import User, UserRole

logger = get_logger("digital_team_service")

PROGRAM_GRID_PATH = Path(__file__).resolve().parents[1] / "data" / "programs" / "program_grid.json"
ACTIVE_TASK_STATUSES = {"todo", "in_progress", "review"}
ACTIVE_EVENT_STATUSES = {"planned", "monitoring"}


@dataclass(slots=True)
class ChannelScope:
    can_news: bool
    can_tv: bool

    def allows(self, channel: str) -> bool:
        if channel == "news":
            return self.can_news
        if channel == "tv":
            return self.can_tv
        return False


class DigitalTeamService:
    async def resolve_scope(self, db: AsyncSession, user: User) -> ChannelScope:
        if user.role in {UserRole.director, UserRole.editor_chief}:
            return ChannelScope(can_news=True, can_tv=True)

        if user.role != UserRole.social_media:
            return ChannelScope(can_news=False, can_tv=False)

        row = await db.execute(select(DigitalTeamScope).where(DigitalTeamScope.user_id == user.id))
        scope = row.scalar_one_or_none()
        if scope:
            return ChannelScope(can_news=bool(scope.can_manage_news), can_tv=bool(scope.can_manage_tv))

        # Fallback for existing social-media users created before this module.
        return ChannelScope(can_news=True, can_tv=True)

    async def list_scopes(self, db: AsyncSession) -> list[dict]:
        rows = await db.execute(
            select(DigitalTeamScope, User)
            .join(User, User.id == DigitalTeamScope.user_id)
            .order_by(User.full_name_ar.asc(), User.username.asc())
        )
        out: list[dict] = []
        for scope, user in rows.all():
            out.append(
                {
                    "id": scope.id,
                    "user_id": user.id,
                    "username": user.username,
                    "full_name_ar": user.full_name_ar,
                    "can_manage_news": bool(scope.can_manage_news),
                    "can_manage_tv": bool(scope.can_manage_tv),
                    "platforms": _normalize_short_list(scope.platforms or []),
                    "notes": scope.notes,
                    "created_at": scope.created_at,
                    "updated_at": scope.updated_at,
                }
            )
        return out

    async def upsert_scope(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        can_manage_news: bool,
        can_manage_tv: bool,
        platforms: list[str],
        notes: str | None,
        actor: User,
    ) -> DigitalTeamScope:
        user_row = await db.execute(select(User).where(User.id == user_id))
        user = user_row.scalar_one_or_none()
        if not user:
            raise ValueError("User not found")
        if user.role != UserRole.social_media:
            raise ValueError("Target user must have social_media role")
        if not can_manage_news and not can_manage_tv:
            raise ValueError("At least one channel must be enabled")

        row = await db.execute(select(DigitalTeamScope).where(DigitalTeamScope.user_id == user_id))
        scope = row.scalar_one_or_none()
        if scope is None:
            scope = DigitalTeamScope(
                user_id=user_id,
                created_by_user_id=actor.id,
                updated_by_user_id=actor.id,
            )
            db.add(scope)

        scope.can_manage_news = bool(can_manage_news)
        scope.can_manage_tv = bool(can_manage_tv)
        scope.platforms = _normalize_short_list(platforms, max_len=24)
        scope.notes = _clean_text(notes, max_len=2000)
        scope.updated_by_user_id = actor.id
        scope.updated_at = datetime.utcnow()
        await db.flush()
        return scope

    async def import_program_grid(
        self,
        db: AsyncSession,
        *,
        actor: User | None,
        overwrite: bool = False,
    ) -> dict:
        if not PROGRAM_GRID_PATH.exists():
            raise FileNotFoundError(f"Program grid file not found: {PROGRAM_GRID_PATH}")

        payload = json.loads(PROGRAM_GRID_PATH.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError("Program grid must be a JSON array")

        created = 0
        updated = 0
        skipped = 0
        errors: list[dict] = []

        for idx, item in enumerate(payload, start=1):
            try:
                if not isinstance(item, dict):
                    raise ValueError("Record must be an object")

                channel = _normalize_channel(item.get("channel"))
                title = _clean_text(item.get("program_title"), max_len=255)
                if not title:
                    raise ValueError("program_title is required")
                day_of_week = _normalize_day_of_week(item.get("day_of_week"))
                start_time = _parse_time(item.get("start_time"))
                duration = _clamp_int(item.get("duration_minutes"), minimum=5, maximum=480, default=60)

                existing_row = await db.execute(
                    select(ProgramSlot).where(
                        ProgramSlot.channel == channel,
                        ProgramSlot.program_title == title,
                        ProgramSlot.day_of_week == day_of_week,
                        ProgramSlot.start_time == start_time,
                    )
                )
                existing = existing_row.scalar_one_or_none()

                record = {
                    "channel": channel,
                    "program_title": title,
                    "program_type": _clean_text(item.get("program_type"), max_len=64),
                    "description": _clean_text(item.get("description"), max_len=4000),
                    "day_of_week": day_of_week,
                    "start_time": start_time,
                    "duration_minutes": duration,
                    "timezone": _clean_text(item.get("timezone"), max_len=64) or "Africa/Algiers",
                    "priority": _clamp_int(item.get("priority"), minimum=1, maximum=5, default=3),
                    "is_active": bool(item.get("is_active", True)),
                    "social_focus": _clean_text(item.get("social_focus"), max_len=4000),
                    "tags": _normalize_short_list(item.get("tags") or []),
                    "source_ref": _clean_text(item.get("source_ref"), max_len=2048),
                }

                if existing is None:
                    db.add(
                        ProgramSlot(
                            **record,
                            created_by_user_id=actor.id if actor else None,
                            updated_by_user_id=actor.id if actor else None,
                        )
                    )
                    created += 1
                    continue

                if not overwrite:
                    skipped += 1
                    continue

                for key, value in record.items():
                    setattr(existing, key, value)
                existing.updated_by_user_id = actor.id if actor else None
                existing.updated_at = datetime.utcnow()
                updated += 1
            except Exception as exc:  # noqa: BLE001
                errors.append({"index": idx, "error": str(exc)})

        await db.flush()
        return {
            "file": str(PROGRAM_GRID_PATH),
            "total_records": len(payload),
            "created": created,
            "updated": updated,
            "skipped": skipped,
            "errors_count": len(errors),
            "errors": errors[:100],
        }

    async def generate_program_tasks(
        self,
        db: AsyncSession,
        *,
        hours_ahead: int = 48,
        actor: User | None = None,
    ) -> dict[str, int]:
        now = datetime.utcnow()
        window_end = now + timedelta(hours=max(1, min(hours_ahead, 24 * 14)))

        rows = await db.execute(
            select(ProgramSlot)
            .where(ProgramSlot.is_active == True)
            .order_by(ProgramSlot.channel.asc(), ProgramSlot.day_of_week.asc().nullsfirst(), ProgramSlot.start_time.asc())
        )
        slots = rows.scalars().all()

        created = 0
        skipped = 0
        for slot in slots:
            for start_dt in _slot_occurrences(slot, start=now, end=window_end):
                end_dt = start_dt + timedelta(minutes=max(5, int(slot.duration_minutes or 60)))
                task_defs = [
                    (
                        "pre_show",
                        start_dt - timedelta(hours=2),
                        f"{slot.program_title} | تحضير قبل البث",
                        _build_program_brief(slot, start_dt, phase="pre"),
                        4,
                    ),
                    (
                        "live_coverage",
                        start_dt,
                        f"{slot.program_title} | تغطية مباشرة",
                        _build_program_brief(slot, start_dt, phase="live"),
                        5,
                    ),
                    (
                        "post_show",
                        end_dt + timedelta(minutes=15),
                        f"{slot.program_title} | ملخص ما بعد البث",
                        _build_program_brief(slot, start_dt, phase="post"),
                        3,
                    ),
                ]

                for task_type, due_at, title, brief, priority in task_defs:
                    dedupe_key = f"program:{slot.id}:{start_dt.isoformat()}:{task_type}"
                    owner_user_id, owner_username = await self._pick_owner_for_channel(db, slot.channel)
                    task = SocialTask(
                        channel=slot.channel,
                        platform="all",
                        task_type=task_type,
                        title=title,
                        brief=brief,
                        status="todo",
                        priority=max(priority, int(slot.priority or 3)),
                        due_at=due_at,
                        scheduled_at=start_dt,
                        dedupe_key=dedupe_key,
                        program_slot_id=slot.id,
                        owner_user_id=owner_user_id,
                        owner_username=owner_username,
                        created_by_user_id=actor.id if actor else None,
                        created_by_username=actor.username if actor else "system",
                        updated_by_user_id=actor.id if actor else None,
                        updated_by_username=actor.username if actor else "system",
                    )
                    created_ok = await self._create_task_if_new(db, task)
                    if created_ok:
                        created += 1
                    else:
                        skipped += 1

        return {"created": created, "skipped": skipped}

    async def generate_event_tasks(
        self,
        db: AsyncSession,
        *,
        window_hours: int = 24,
        actor: User | None = None,
    ) -> dict[str, int]:
        now = datetime.utcnow()
        window_end = now + timedelta(hours=max(1, min(window_hours, 24 * 7)))
        rows = await db.execute(
            select(EventMemoItem).where(
                EventMemoItem.status.in_(list(ACTIVE_EVENT_STATUSES)),
                EventMemoItem.starts_at >= now,
                EventMemoItem.starts_at <= window_end,
            )
        )
        events = rows.scalars().all()

        created = 0
        skipped = 0
        for event in events:
            channel = "tv" if (event.scope or "").lower() == "religious" else "news"
            dedupe_key = f"event:{event.id}:{event.starts_at.isoformat()}"
            owner_user_id, owner_username = await self._pick_owner_for_channel(db, channel)
            task = SocialTask(
                channel=channel,
                platform="all",
                task_type="event_coverage",
                title=f"{event.title} | تغطية سوشيال استباقية",
                brief=_build_event_brief(event),
                status="todo",
                priority=max(1, min(5, int(event.priority or 3))),
                due_at=event.starts_at - timedelta(hours=min(6, max(1, int(event.lead_time_hours or 6)))),
                scheduled_at=event.starts_at,
                dedupe_key=dedupe_key,
                event_id=event.id,
                owner_user_id=owner_user_id,
                owner_username=owner_username,
                created_by_user_id=actor.id if actor else None,
                created_by_username=actor.username if actor else "system",
                updated_by_user_id=actor.id if actor else None,
                updated_by_username=actor.username if actor else "system",
            )
            created_ok = await self._create_task_if_new(db, task)
            if created_ok:
                created += 1
            else:
                skipped += 1

        return {"created": created, "skipped": skipped}

    async def generate_breaking_tasks(
        self,
        db: AsyncSession,
        *,
        window_hours: int = 8,
        actor: User | None = None,
    ) -> dict[str, int]:
        now = datetime.utcnow()
        cutoff = now - timedelta(hours=max(1, min(window_hours, 48)))
        rows = await db.execute(
            select(Article).where(
                Article.is_breaking == True,
                Article.crawled_at >= cutoff,
                Article.status.in_(
                    [
                        NewsStatus.CANDIDATE,
                        NewsStatus.APPROVED,
                        NewsStatus.APPROVED_HANDOFF,
                        NewsStatus.READY_FOR_MANUAL_PUBLISH,
                        NewsStatus.PUBLISHED,
                    ]
                ),
            )
        )
        articles = rows.scalars().all()

        created = 0
        skipped = 0
        for article in articles:
            dedupe_key = f"breaking:{article.id}"
            owner_user_id, owner_username = await self._pick_owner_for_channel(db, "news")
            task = SocialTask(
                channel="news",
                platform="all",
                task_type="breaking",
                title=f"عاجل | {article.title_ar or article.original_title}",
                brief="إعداد نسخة سوشيال عاجلة ومختصرة مع التحقق من الدقة قبل النشر.",
                status="todo",
                priority=5,
                due_at=now + timedelta(minutes=10),
                scheduled_at=now,
                dedupe_key=dedupe_key,
                article_id=article.id,
                owner_user_id=owner_user_id,
                owner_username=owner_username,
                created_by_user_id=actor.id if actor else None,
                created_by_username=actor.username if actor else "system",
                updated_by_user_id=actor.id if actor else None,
                updated_by_username=actor.username if actor else "system",
            )
            created_ok = await self._create_task_if_new(db, task)
            if created_ok:
                created += 1
            else:
                skipped += 1

        return {"created": created, "skipped": skipped}

    async def generate_all(
        self,
        db: AsyncSession,
        *,
        actor: User | None = None,
        hours_ahead: int = 48,
        include_events: bool = True,
        include_breaking: bool = True,
    ) -> dict[str, int]:
        program_stats = await self.generate_program_tasks(db, hours_ahead=hours_ahead, actor=actor)
        event_stats = {"created": 0, "skipped": 0}
        breaking_stats = {"created": 0, "skipped": 0}

        if include_events:
            event_stats = await self.generate_event_tasks(db, window_hours=min(24, hours_ahead), actor=actor)
        if include_breaking:
            breaking_stats = await self.generate_breaking_tasks(db, window_hours=8, actor=actor)

        return {
            "generated_program_tasks": program_stats["created"],
            "generated_event_tasks": event_stats["created"],
            "generated_breaking_tasks": breaking_stats["created"],
            "total_generated": program_stats["created"] + event_stats["created"] + breaking_stats["created"],
            "skipped_duplicates": program_stats["skipped"] + event_stats["skipped"] + breaking_stats["skipped"],
        }

    async def due_task_notifications(
        self,
        db: AsyncSession,
        *,
        scope: ChannelScope,
        limit: int = 12,
    ) -> list[dict]:
        now = datetime.utcnow()
        filters = [
            SocialTask.status.in_(list(ACTIVE_TASK_STATUSES)),
            SocialTask.due_at.isnot(None),
            SocialTask.due_at <= now + timedelta(hours=6),
        ]

        channel_filters = []
        if scope.can_news:
            channel_filters.append(SocialTask.channel == "news")
        if scope.can_tv:
            channel_filters.append(SocialTask.channel == "tv")
        if not channel_filters:
            return []
        filters.append(or_(*channel_filters))

        rows = await db.execute(
            select(SocialTask)
            .where(and_(*filters))
            .order_by(SocialTask.due_at.asc(), SocialTask.priority.desc())
            .limit(max(1, min(limit, 50)))
        )
        out: list[dict] = []
        for task in rows.scalars().all():
            severity = "high" if task.due_at and task.due_at <= now else "medium"
            out.append(
                {
                    "id": f"digital-task-{task.id}",
                    "type": "digital_task",
                    "title": task.title,
                    "message": f"مهمة سوشيال مستحقة على قناة {task.channel}. الحالة الحالية: {task.status}.",
                    "created_at": task.updated_at or task.created_at,
                    "severity": severity,
                    "task_id": task.id,
                    "channel": task.channel,
                    "due_at": task.due_at.isoformat() if task.due_at else None,
                }
            )
        return out

    async def _pick_owner_for_channel(self, db: AsyncSession, channel: str) -> tuple[int | None, str | None]:
        users_row = await db.execute(
            select(User)
            .where(User.role == UserRole.social_media, User.is_active == True)
            .order_by(User.id.asc())
        )
        users = users_row.scalars().all()
        if not users:
            return None, None

        scope_rows = await db.execute(select(DigitalTeamScope))
        scope_map = {item.user_id: item for item in scope_rows.scalars().all()}

        for user in users:
            scope = scope_map.get(user.id)
            if not scope:
                return user.id, user.username
            if channel == "news" and scope.can_manage_news:
                return user.id, user.username
            if channel == "tv" and scope.can_manage_tv:
                return user.id, user.username
        return None, None

    async def _create_task_if_new(self, db: AsyncSession, task: SocialTask) -> bool:
        if task.dedupe_key:
            existing = await db.execute(select(SocialTask.id).where(SocialTask.dedupe_key == task.dedupe_key))
            if existing.scalar_one_or_none() is not None:
                return False
        db.add(task)
        await db.flush()
        return True

    async def refresh_task_post_stats(self, db: AsyncSession, task_id: int) -> None:
        row = await db.execute(
            select(
                func.count(SocialPost.id).filter(SocialPost.status == "published"),
                func.max(SocialPost.published_at),
            ).where(SocialPost.task_id == task_id)
        )
        published_count, last_published_at = row.one()

        task_row = await db.execute(select(SocialTask).where(SocialTask.id == task_id))
        task = task_row.scalar_one_or_none()
        if not task:
            return

        task.published_posts_count = int(published_count or 0)
        task.last_published_at = last_published_at
        if task.published_posts_count > 0 and task.status != "done":
            task.status = "done"
            if task.completed_at is None:
                task.completed_at = datetime.utcnow()
        task.updated_at = datetime.utcnow()
        await db.flush()


def _normalize_channel(value: object) -> str:
    channel = str(value or "").strip().lower()
    if channel not in {"news", "tv"}:
        raise ValueError("channel must be news or tv")
    return channel


def _normalize_day_of_week(value: object) -> int | None:
    if value is None or value == "":
        return None
    day = int(value)
    if day < 0 or day > 6:
        raise ValueError("day_of_week must be between 0 and 6")
    return day


def _parse_time(value: object) -> time:
    raw = str(value or "").strip()
    if len(raw) != 5 or raw[2] != ":":
        raise ValueError("start_time must be HH:MM")
    hh = int(raw[:2])
    mm = int(raw[3:5])
    if hh < 0 or hh > 23 or mm < 0 or mm > 59:
        raise ValueError("invalid start_time")
    return time(hour=hh, minute=mm)


def _clean_text(value: object, *, max_len: int) -> str | None:
    if value is None:
        return None
    clean = str(value).strip()
    if not clean:
        return None
    return clean[:max_len]


def _normalize_short_list(values: object, *, max_len: int = 48) -> list[str]:
    if not isinstance(values, list):
        return []
    out: list[str] = []
    seen = set()
    for value in values:
        clean = str(value or "").strip()
        if not clean:
            continue
        clean = clean[:max_len]
        key = clean.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(clean)
    return out


def _clamp_int(value: object, *, minimum: int, maximum: int, default: int) -> int:
    try:
        parsed = int(value)
    except Exception:
        parsed = default
    return max(minimum, min(maximum, parsed))


def _slot_occurrences(slot: ProgramSlot, *, start: datetime, end: datetime) -> list[datetime]:
    occurrences: list[datetime] = []
    current_day = start.date()
    end_day = end.date()
    while current_day <= end_day:
        if slot.day_of_week is None or current_day.weekday() == slot.day_of_week:
            occurrence = datetime.combine(current_day, slot.start_time)
            if start <= occurrence <= end:
                occurrences.append(occurrence)
        current_day += timedelta(days=1)
    return occurrences


def _build_program_brief(slot: ProgramSlot, starts_at: datetime, *, phase: str) -> str:
    phase_map = {
        "pre": "Prepare teaser copy and hook before the show starts.",
        "live": "Publish live updates while the show is on-air.",
        "post": "Publish recap and key highlights after the show ends.",
    }
    line = phase_map.get(phase, "")
    return (
        f"Channel: {slot.channel} | Program: {slot.program_title} | Starts: {starts_at.isoformat()}\n"
        f"{line}\n"
        f"Social focus: {slot.social_focus or 'No specific focus provided.'}"
    )


def _build_event_brief(event: EventMemoItem) -> str:
    return (
        f"Event: {event.title}\n"
        f"Starts: {event.starts_at.isoformat()} | Scope: {event.scope}\n"
        f"Coverage plan: {event.coverage_plan or 'Not provided'}"
    )


digital_team_service = DigitalTeamService()
