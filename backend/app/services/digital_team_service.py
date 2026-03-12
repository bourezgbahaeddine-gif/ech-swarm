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
from app.models import Article, EventMemoItem, NewsStatus, Story
from app.models.digital_team import DigitalTeamScope, ProgramSlot, SocialPost, SocialPostVersion, SocialTask
from app.models.user import User, UserRole
from app.services.smart_editor_service import smart_editor_service

logger = get_logger("digital_team_service")

PROGRAM_GRID_PATH = Path(__file__).resolve().parents[1] / "data" / "programs" / "program_grid.json"
ACTIVE_TASK_STATUSES = {"todo", "in_progress", "review"}
ACTIVE_EVENT_STATUSES = {"planned", "monitoring"}
DELIVERY_ADAPTERS = {"manual", "facebook", "x", "push", "instagram", "youtube"}
DIGITAL_PLAYBOOKS = {
    "breaking_alert": {
        "key": "breaking_alert",
        "label": "Breaking Alert",
        "objective": "breaking",
        "platforms": ["x", "facebook", "push"],
        "max_length_hint": {"x": 280, "facebook": 1200, "push": 180},
        "cta_style": "urgent",
        "include_hashtags": True,
        "include_media_slot": False,
    },
    "pre_show_teaser": {
        "key": "pre_show_teaser",
        "label": "Pre-show Teaser",
        "objective": "teaser",
        "platforms": ["facebook", "x", "instagram"],
        "max_length_hint": {"x": 240, "facebook": 1000, "instagram": 1800},
        "cta_style": "tune_in",
        "include_hashtags": True,
        "include_media_slot": True,
    },
    "live_now": {
        "key": "live_now",
        "label": "Live Now",
        "objective": "live",
        "platforms": ["x", "facebook", "push"],
        "max_length_hint": {"x": 260, "facebook": 900, "push": 140},
        "cta_style": "watch_now",
        "include_hashtags": True,
        "include_media_slot": False,
    },
    "post_show_recap": {
        "key": "post_show_recap",
        "label": "Post-show Recap",
        "objective": "recap",
        "platforms": ["facebook", "x", "youtube"],
        "max_length_hint": {"x": 260, "facebook": 1800, "youtube": 3000},
        "cta_style": "read_more",
        "include_hashtags": True,
        "include_media_slot": True,
    },
    "event_reminder": {
        "key": "event_reminder",
        "label": "Event Reminder",
        "objective": "reminder",
        "platforms": ["facebook", "x"],
        "max_length_hint": {"x": 220, "facebook": 1200},
        "cta_style": "reminder",
        "include_hashtags": True,
        "include_media_slot": False,
    },
}


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

    def list_playbooks(self) -> list[dict]:
        return list(DIGITAL_PLAYBOOKS.values())

    def get_playbook(self, key: str | None) -> dict:
        normalized = (key or "breaking_alert").strip().lower()
        return DIGITAL_PLAYBOOKS.get(normalized, DIGITAL_PLAYBOOKS["breaking_alert"])

    async def create_post_version(
        self,
        db: AsyncSession,
        *,
        post: SocialPost,
        version_type: str,
        note: str | None = None,
        actor: User | None = None,
    ) -> SocialPostVersion:
        row = await db.execute(
            select(func.coalesce(func.max(SocialPostVersion.version_no), 0)).where(SocialPostVersion.post_id == post.id)
        )
        next_no = int(row.scalar() or 0) + 1
        version = SocialPostVersion(
            post_id=post.id,
            version_no=next_no,
            version_type=(version_type or "edited")[:32],
            content_text=post.content_text or "",
            hashtags=list(post.hashtags or []),
            media_urls=list(post.media_urls or []),
            note=_clean_text(note, max_len=4000),
            created_by_user_id=actor.id if actor else post.updated_by_user_id,
            created_by_username=actor.username if actor else post.updated_by_username,
        )
        db.add(version)
        await db.flush()
        return version

    async def list_post_versions(self, db: AsyncSession, *, post_id: int) -> list[SocialPostVersion]:
        rows = await db.execute(
            select(SocialPostVersion)
            .where(SocialPostVersion.post_id == post_id)
            .order_by(SocialPostVersion.version_no.desc(), SocialPostVersion.created_at.desc())
        )
        return rows.scalars().all()

    async def duplicate_post_version(
        self,
        db: AsyncSession,
        *,
        post: SocialPost,
        source_version_no: int | None = None,
        version_type: str = "duplicated",
        note: str | None = None,
        actor: User | None = None,
    ) -> SocialPostVersion:
        source: SocialPostVersion | None = None
        if source_version_no is not None:
            row = await db.execute(
                select(SocialPostVersion).where(
                    SocialPostVersion.post_id == post.id,
                    SocialPostVersion.version_no == source_version_no,
                )
            )
            source = row.scalar_one_or_none()
        if source is None:
            row = await db.execute(
                select(SocialPostVersion)
                .where(SocialPostVersion.post_id == post.id)
                .order_by(SocialPostVersion.version_no.desc())
                .limit(1)
            )
            source = row.scalar_one_or_none()

        if source is None:
            source_text = post.content_text
            source_tags = list(post.hashtags or [])
            source_media = list(post.media_urls or [])
        else:
            source_text = source.content_text
            source_tags = list(source.hashtags or [])
            source_media = list(source.media_urls or [])

        post.content_text = source_text or ""
        post.hashtags = source_tags
        post.media_urls = source_media
        post.updated_at = datetime.utcnow()
        if actor:
            post.updated_by_user_id = actor.id
            post.updated_by_username = actor.username

        version = await self.create_post_version(
            db,
            post=post,
            version_type=version_type,
            note=note or f"Duplicated from version {source.version_no}" if source else note,
            actor=actor,
        )
        return version

    def compare_versions(self, *, base: SocialPostVersion, target: SocialPostVersion) -> dict:
        base_tags = {str(tag).strip() for tag in (base.hashtags or []) if str(tag).strip()}
        target_tags = {str(tag).strip() for tag in (target.hashtags or []) if str(tag).strip()}
        base_media = {str(url).strip() for url in (base.media_urls or []) if str(url).strip()}
        target_media = {str(url).strip() for url in (target.media_urls or []) if str(url).strip()}
        base_text = (base.content_text or "").strip()
        target_text = (target.content_text or "").strip()
        return {
            "base_version_no": base.version_no,
            "target_version_no": target.version_no,
            "base_length": len(base_text),
            "target_length": len(target_text),
            "length_delta": len(target_text) - len(base_text),
            "hashtags_added": sorted(target_tags - base_tags),
            "hashtags_removed": sorted(base_tags - target_tags),
            "media_added": sorted(target_media - base_media),
            "media_removed": sorted(base_media - target_media),
            "changed": bool(
                base_text != target_text
                or base_tags != target_tags
                or base_media != target_media
            ),
        }

    def score_engagement(
        self,
        *,
        platform: str,
        content_text: str,
        hashtags: list[str] | None = None,
        scheduled_at: datetime | None = None,
    ) -> dict:
        text = (content_text or "").strip()
        tags = hashtags or []
        platform_key = (platform or "").strip().lower()
        limits = {"x": 280, "facebook": 5000, "instagram": 2200, "tiktok": 2200, "youtube": 5000, "push": 180}
        limit = limits.get(platform_key, 5000)

        hook = 0
        if "؟" in text or "!" in text:
            hook += 20
        if len(text) >= 40:
            hook += 15
        if any(term in text for term in ["عاجل", "الآن", "مباشر", "حصري"]):
            hook += 15
        hook = min(30, hook)

        length_score = 30
        ratio = (len(text) / limit) if limit else 0
        if ratio > 1:
            length_score = 0
        elif ratio > 0.9:
            length_score = 12
        elif ratio < 0.08:
            length_score = 10
        elif ratio < 0.2:
            length_score = 18

        cta_score = 20 if any(term in text for term in ["تابع", "اقرأ", "شاهد", "اضغط", "المزيد"]) else 10
        hashtag_score = 20 if 1 <= len(tags) <= 5 else (10 if len(tags) <= 8 else 4)

        timing_score = 10
        if scheduled_at:
            hour = scheduled_at.hour
            if 8 <= hour <= 11 or 18 <= hour <= 22:
                timing_score = 20
            elif 0 <= hour <= 5:
                timing_score = 6
            else:
                timing_score = 14
        total = min(100, max(0, hook + length_score + cta_score + hashtag_score + timing_score))

        recommendations: list[str] = []
        if length_score <= 12:
            recommendations.append("اختصر النص ليتناسب أكثر مع المنصة.")
        if cta_score < 20:
            recommendations.append("أضف دعوة إجراء واضحة (CTA).")
        if hashtag_score < 15:
            recommendations.append("حسّن عدد الوسوم بين 1 و5.")
        if hook < 20:
            recommendations.append("قوِّ الجملة الافتتاحية بهوك أو سؤال مباشر.")

        return {
            "score": int(total),
            "signals": {
                "hook": int(hook),
                "length_fit": int(length_score),
                "cta": int(cta_score),
                "hashtags_fit": int(hashtag_score),
                "timing_fit": int(timing_score),
            },
            "recommendations": recommendations[:4],
        }

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
            owner_user_id, owner_username = await self._pick_owner_for_channel(db, channel)
            story_title = None
            if getattr(event, "story_id", None):
                story_row = await db.execute(select(Story).where(Story.id == event.story_id))
                story = story_row.scalar_one_or_none()
                story_title = story.title if story else None

            phases = [
                ("event_t24", "T-24 | تجهيز تغطية الحدث", event.starts_at - timedelta(hours=24), 4),
                ("event_t6", "T-6 | متابعة قبل الحدث", event.starts_at - timedelta(hours=6), 5),
                ("event_live", "Live | تغطية مباشرة", event.starts_at, 5),
                ("event_post", "Post | خلاصة بعد الحدث", event.starts_at + timedelta(hours=1), 3),
            ]

            for task_type, phase_label, due_at, phase_priority in phases:
                dedupe_key = f"event:{event.id}:{event.starts_at.isoformat()}:{task_type}"
                task = SocialTask(
                    channel=channel,
                    platform="all",
                    task_type=task_type,
                    title=f"{event.title} | {phase_label}",
                    brief=_build_event_brief(event) + (f"\nStory: {story_title}" if story_title else ""),
                    status="todo",
                    priority=max(phase_priority, max(1, min(5, int(event.priority or 3)))),
                    due_at=due_at,
                    scheduled_at=event.starts_at,
                    dedupe_key=dedupe_key,
                    event_id=event.id,
                    story_id=getattr(event, "story_id", None),
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

    async def compose_for_task(
        self,
        db: AsyncSession,
        *,
        task_id: int,
        platform: str = "facebook",
        max_hashtags: int = 6,
    ) -> dict:
        task_row = await db.execute(select(SocialTask).where(SocialTask.id == task_id))
        task = task_row.scalar_one_or_none()
        if not task:
            raise ValueError("Task not found")

        source_type = "task"
        source_id: int | None = task.id
        source_title = task.title
        draft_title = task.title
        draft_html = task.brief or ""
        source_text = task.brief or task.title
        candidate_tags: list[str] = []

        if task.article_id:
            article_row = await db.execute(select(Article).where(Article.id == task.article_id))
            article = article_row.scalar_one_or_none()
            if article:
                source_type = "article"
                source_id = article.id
                source_title = article.title_ar or article.original_title or task.title
                draft_title = source_title
                draft_html = (
                    article.body_html
                    or article.original_content
                    or article.summary
                    or task.brief
                    or task.title
                )
                source_text = (
                    article.summary
                    or article.original_content
                    or article.body_html
                    or task.brief
                    or task.title
                )
                candidate_tags.extend([str(x).strip() for x in (article.keywords or []) if str(x).strip()])

        elif task.event_id:
            event_row = await db.execute(select(EventMemoItem).where(EventMemoItem.id == task.event_id))
            event = event_row.scalar_one_or_none()
            if event:
                source_type = "event"
                source_id = event.id
                source_title = event.title
                draft_title = event.title
                draft_html = "\n".join(
                    part for part in [event.summary or "", event.coverage_plan or "", task.brief or ""] if part
                )
                source_text = "\n".join(
                    part for part in [event.summary or "", event.coverage_plan or "", event.title] if part
                )
                candidate_tags.extend([str(x).strip() for x in (event.tags or []) if str(x).strip()])

        elif task.program_slot_id:
            slot_row = await db.execute(select(ProgramSlot).where(ProgramSlot.id == task.program_slot_id))
            slot = slot_row.scalar_one_or_none()
            if slot:
                source_type = "program"
                source_id = slot.id
                source_title = slot.program_title
                draft_title = slot.program_title
                draft_html = "\n".join(
                    part
                    for part in [
                        slot.description or "",
                        slot.social_focus or "",
                        task.brief or "",
                        f"وقت العرض: {slot.start_time}",
                    ]
                    if part
                )
                source_text = "\n".join(
                    part
                    for part in [slot.program_title, slot.description or "", slot.social_focus or ""]
                    if part
                )
                candidate_tags.extend([str(x).strip() for x in (slot.tags or []) if str(x).strip()])

        if task.story_id:
            story_row = await db.execute(select(Story).where(Story.id == task.story_id))
            story = story_row.scalar_one_or_none()
            if story:
                if source_type == "task":
                    source_type = "story"
                    source_id = story.id
                    source_title = story.title or source_title
                    draft_title = story.title or draft_title
                story_context = "\n".join(
                    part for part in [story.summary or "", story.geography or ""] if part
                )
                if story_context:
                    source_text = "\n".join(part for part in [source_text, story_context] if part)

        variants: dict[str, str] = {}
        try:
            variants = await smart_editor_service.social_variants(
                source_text=source_text or draft_title,
                draft_title=draft_title,
                draft_html=draft_html or source_text or draft_title,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("digital_compose_ai_failed", task_id=task_id, error=str(exc))
            variants = {}

        platform_key = (platform or "").strip().lower()
        if platform_key in {"twitter", "x"}:
            platform_key = "x"
        if platform_key in {"notification", "mobile_push"}:
            platform_key = "push"

        recommended_text = (
            variants.get(platform_key)
            or variants.get("facebook")
            or variants.get("x")
            or _fallback_social_text(task=task, source_title=source_title, source_text=source_text)
        )

        hashtags = _build_hashtag_list(
            source_title=source_title,
            tags=candidate_tags,
            channel=task.channel,
            max_items=max_hashtags,
        )

        return {
            "task_id": task.id,
            "platform": platform_key or "facebook",
            "recommended_text": recommended_text.strip(),
            "hashtags": hashtags,
            "variants": {k: (v or "").strip() for k, v in variants.items() if (v or "").strip()},
            "source": {
                "type": source_type,
                "id": source_id,
                "title": source_title,
            },
        }

    async def generate_bundle_for_task(
        self,
        db: AsyncSession,
        *,
        task: SocialTask,
        playbook_key: str,
        save_as_posts: bool,
        actor: User | None = None,
    ) -> dict:
        playbook = self.get_playbook(playbook_key)
        platforms = list(playbook.get("platforms") or ["facebook", "x"])
        variants: dict[str, str] = {}
        hashtags: list[str] = []
        created_post_ids: list[int] = []

        for platform in platforms:
            composed = await self.compose_for_task(
                db,
                task_id=task.id,
                platform=platform,
                max_hashtags=6,
            )
            variants[platform] = composed.get("recommended_text", "")
            if not hashtags and composed.get("hashtags"):
                hashtags = list(composed["hashtags"])
            if save_as_posts:
                post = SocialPost(
                    task_id=task.id,
                    channel=task.channel,
                    platform=platform,
                    content_text=(composed.get("recommended_text") or "").strip(),
                    hashtags=list(composed.get("hashtags") or []),
                    media_urls=[],
                    status="ready",
                    created_by_user_id=actor.id if actor else None,
                    created_by_username=actor.username if actor else "system",
                    updated_by_user_id=actor.id if actor else None,
                    updated_by_username=actor.username if actor else "system",
                )
                db.add(post)
                await db.flush()
                created_post_ids.append(post.id)
                await self.create_post_version(
                    db,
                    post=post,
                    version_type="generated",
                    note=f"bundle:{playbook['key']}",
                    actor=actor,
                )

        await self.refresh_task_post_stats(db, task.id)
        return {
            "task_id": task.id,
            "playbook_key": playbook["key"],
            "generated_count": len(variants),
            "created_post_ids": created_post_ids,
            "variants": variants,
            "hashtags": hashtags,
        }

    async def dispatch_post(
        self,
        db: AsyncSession,
        *,
        post: SocialPost,
        adapter: str,
        action: str,
        scheduled_at: datetime | None,
        published_url: str | None,
        external_post_id: str | None,
        actor: User | None = None,
    ) -> dict:
        adapter_key = (adapter or "manual").strip().lower()
        if adapter_key not in DELIVERY_ADAPTERS:
            adapter_key = "manual"

        if action == "schedule":
            post.status = "scheduled"
            post.scheduled_at = scheduled_at or datetime.utcnow() + timedelta(minutes=5)
            message = f"Scheduled via {adapter_key}"
        else:
            post.status = "published"
            post.published_at = datetime.utcnow()
            post.published_url = _clean_text(published_url, max_len=2048)
            post.external_post_id = _clean_text(external_post_id, max_len=128)
            message = f"Published via {adapter_key}"

        post.updated_at = datetime.utcnow()
        if actor:
            post.updated_by_user_id = actor.id
            post.updated_by_username = actor.username

        await self.create_post_version(
            db,
            post=post,
            version_type="delivery",
            note=message,
            actor=actor,
        )
        await self.refresh_task_post_stats(db, post.task_id)
        return {
            "post_id": post.id,
            "adapter": adapter_key,
            "action": action,
            "status": post.status,
            "dispatched_at": datetime.utcnow(),
            "message": message,
        }

    async def scope_performance(self, db: AsyncSession) -> list[dict]:
        scope_rows = await db.execute(
            select(DigitalTeamScope, User)
            .join(User, User.id == DigitalTeamScope.user_id)
            .order_by(User.username.asc())
        )
        scopes = scope_rows.all()
        if not scopes:
            return []

        now = datetime.utcnow()
        out: list[dict] = []
        for scope, user in scopes:
            channels: list[str] = []
            if scope.can_manage_news:
                channels.append("news")
            if scope.can_manage_tv:
                channels.append("tv")
            if not channels:
                channels = ["news", "tv"]

            task_rows = await db.execute(
                select(SocialTask).where(
                    SocialTask.channel.in_(channels),
                    or_(SocialTask.owner_user_id == user.id, SocialTask.owner_user_id.is_(None)),
                )
            )
            tasks = task_rows.scalars().all()
            task_ids = [task.id for task in tasks]
            post_rows = await db.execute(select(SocialPost).where(SocialPost.task_id.in_(task_ids))) if task_ids else None
            posts = post_rows.scalars().all() if post_rows else []

            total_tasks = len(tasks)
            active_tasks = sum(1 for task in tasks if task.status in ACTIVE_TASK_STATUSES)
            overdue_tasks = sum(
                1
                for task in tasks
                if task.status in ACTIVE_TASK_STATUSES and task.due_at and task.due_at < now
            )
            done_tasks = sum(1 for task in tasks if task.status == "done")
            failed_posts = sum(1 for post in posts if post.status == "failed")
            published_posts = sum(1 for post in posts if post.status == "published")

            on_time_total = 0
            on_time_done = 0
            for task in tasks:
                if task.status == "done" and task.due_at and task.completed_at:
                    on_time_total += 1
                    if task.completed_at <= task.due_at:
                        on_time_done += 1
            on_time_rate = round((on_time_done / on_time_total) * 100, 1) if on_time_total else 0.0

            out.append(
                {
                    "user_id": user.id,
                    "username": user.username,
                    "can_manage_news": bool(scope.can_manage_news),
                    "can_manage_tv": bool(scope.can_manage_tv),
                    "total_tasks": total_tasks,
                    "active_tasks": active_tasks,
                    "overdue_tasks": overdue_tasks,
                    "done_tasks": done_tasks,
                    "failed_posts": failed_posts,
                    "published_posts": published_posts,
                    "on_time_rate": on_time_rate,
                }
            )
        return out


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


def _fallback_social_text(*, task: SocialTask, source_title: str, source_text: str) -> str:
    headline = source_title.strip() or task.title
    body = (source_text or task.brief or "").strip()
    if len(body) > 320:
        body = body[:317].rstrip() + "..."
    if body:
        return f"{headline}\n\n{body}\n\nتابعوا التغطية عبر منصات الشروق."
    return f"{headline}\n\nتابعوا التغطية عبر منصات الشروق."


def _build_hashtag_list(*, source_title: str, tags: list[str], channel: str, max_items: int) -> list[str]:
    seeds: list[str] = []
    if channel == "news":
        seeds.extend(["الشروق_نيوز", "الجزائر"])
    elif channel == "tv":
        seeds.extend(["الشروق_تي_في", "برامج_الشروق"])
    for tag in tags:
        clean = str(tag or "").strip().replace("#", "")
        if clean:
            seeds.append(clean)
    for token in str(source_title or "").split():
        token = token.strip().replace("#", "")
        if len(token) >= 3:
            seeds.append(token)

    out: list[str] = []
    seen: set[str] = set()
    for item in seeds:
        normalized = "".join(ch for ch in item if ch.isalnum() or ch == "_")
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(normalized)
        if len(out) >= max(1, min(max_items, 12)):
            break
    return out


digital_team_service = DigitalTeamService()
