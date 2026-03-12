"""
Digital Team API routes.
Operational board for social-media workflows across Echorouk News and TV.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.auth import get_current_user
from app.core.database import get_db
from app.models import EventMemoItem, Story
from app.models.digital_team import ProgramSlot, SocialPost, SocialPostVersion, SocialTask
from app.models.user import User, UserRole
from app.schemas.digital import (
    DigitalComposeRequest,
    DigitalComposeResponse,
    DigitalCalendarItem,
    DigitalCalendarResponse,
    DigitalActionDeskResponse,
    DigitalTaskActionItem,
    DigitalBundleGenerateRequest,
    DigitalBundleGenerateResponse,
    DigitalDispatchRequest,
    DigitalDispatchResponse,
    DigitalEngagementScoreResponse,
    DigitalPlaybookTemplate,
    DigitalScopePerformanceItem,
    DigitalScopePerformanceResponse,
    DigitalGenerationResponse,
    DigitalOverviewResponse,
    DigitalTeamScopeResponse,
    DigitalTeamScopeUpsertRequest,
    ProgramSlotCreateRequest,
    ProgramSlotResponse,
    ProgramSlotUpdateRequest,
    SocialPostCreateRequest,
    SocialPostListResponse,
    SocialPostResponse,
    SocialPostCompareResponse,
    SocialPostVersionDuplicateRequest,
    SocialPostVersionListResponse,
    SocialPostVersionResponse,
    SocialPostUpdateRequest,
    SocialTaskCreateRequest,
    SocialTaskListResponse,
    SocialTaskResponse,
    SocialTaskUpdateRequest,
)
from app.services.digital_team_service import (
    ACTIVE_EVENT_STATUSES,
    ACTIVE_TASK_STATUSES,
    ChannelScope,
    digital_team_service,
)

router = APIRouter(prefix="/digital", tags=["Digital Team"])

READ_ROLES = {
    UserRole.director,
    UserRole.editor_chief,
    UserRole.social_media,
    UserRole.journalist,
    UserRole.print_editor,
}
WRITE_ROLES = {
    UserRole.director,
    UserRole.editor_chief,
    UserRole.social_media,
}
MANAGE_ROLES = {
    UserRole.director,
    UserRole.editor_chief,
}


def _assert_read(user: User) -> None:
    if user.role not in READ_ROLES:
        raise HTTPException(status_code=403, detail="Not allowed to access Digital Team board.")


def _assert_write(user: User) -> None:
    if user.role not in WRITE_ROLES:
        raise HTTPException(status_code=403, detail="Not allowed to modify Digital Team data.")


def _assert_manage(user: User) -> None:
    if user.role not in MANAGE_ROLES:
        raise HTTPException(status_code=403, detail="Not allowed to manage Digital Team settings.")


def _normalize_text(value: str | None, *, max_len: int) -> str | None:
    if value is None:
        return None
    clean = value.strip()
    if not clean:
        return None
    return clean[:max_len]


def _parse_hhmm(value: str) -> time:
    raw = (value or "").strip()
    if len(raw) != 5 or raw[2] != ":":
        raise HTTPException(status_code=400, detail="start_time must be HH:MM")
    try:
        hh = int(raw[:2])
        mm = int(raw[3:5])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="start_time must be HH:MM") from exc
    if hh < 0 or hh > 23 or mm < 0 or mm > 59:
        raise HTTPException(status_code=400, detail="start_time must be valid HH:MM")
    return time(hour=hh, minute=mm)


def _normalize_list(values: list[str] | None, *, max_items: int = 50, max_len: int = 80) -> list[str]:
    if not values:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for value in values[:max_items]:
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


def _scope_channels(scope: ChannelScope) -> set[str]:
    channels: set[str] = set()
    if scope.can_news:
        channels.add("news")
    if scope.can_tv:
        channels.add("tv")
    return channels


def _ensure_channel_allowed(channel: str, scope: ChannelScope) -> None:
    if not scope.allows(channel):
        raise HTTPException(status_code=403, detail=f"You do not have access to channel: {channel}")


async def _ensure_digital_tables(db: AsyncSession) -> None:
    checks = await db.execute(
        text(
            """
            SELECT
                to_regclass('public.digital_team_scopes') AS scopes_tbl,
                to_regclass('public.program_slots') AS slots_tbl,
                to_regclass('public.social_tasks') AS tasks_tbl,
                to_regclass('public.social_posts') AS posts_tbl,
                to_regclass('public.social_post_versions') AS versions_tbl
            """
        )
    )
    row = checks.mappings().first()
    if not row or not (row["scopes_tbl"] and row["slots_tbl"] and row["tasks_tbl"] and row["posts_tbl"] and row["versions_tbl"]):
        raise HTTPException(
            status_code=503,
            detail="Digital Team tables are not ready. Run: alembic upgrade head",
        )


async def _get_scope_for_user(db: AsyncSession, user: User) -> ChannelScope:
    if user.role in {UserRole.director, UserRole.editor_chief, UserRole.journalist, UserRole.print_editor}:
        return ChannelScope(can_news=True, can_tv=True)
    return await digital_team_service.resolve_scope(db, user)


def _slot_response(slot: ProgramSlot) -> ProgramSlotResponse:
    return ProgramSlotResponse(
        id=slot.id,
        channel=slot.channel,
        program_title=slot.program_title,
        program_type=slot.program_type,
        description=slot.description,
        day_of_week=slot.day_of_week,
        start_time=slot.start_time,
        duration_minutes=slot.duration_minutes,
        timezone=slot.timezone,
        priority=slot.priority,
        is_active=slot.is_active,
        social_focus=slot.social_focus,
        tags=slot.tags or [],
        source_ref=slot.source_ref,
        created_at=slot.created_at,
        updated_at=slot.updated_at,
    )


def _task_response(task: SocialTask) -> SocialTaskResponse:
    return SocialTaskResponse(
        id=task.id,
        channel=task.channel,
        platform=task.platform,
        task_type=task.task_type,
        title=task.title,
        brief=task.brief,
        status=task.status,
        priority=task.priority,
        due_at=task.due_at,
        scheduled_at=task.scheduled_at,
        started_at=task.started_at,
        completed_at=task.completed_at,
        dedupe_key=task.dedupe_key,
        program_slot_id=task.program_slot_id,
        event_id=task.event_id,
        article_id=task.article_id,
        story_id=task.story_id,
        owner_user_id=task.owner_user_id,
        owner_username=task.owner_username,
        published_posts_count=task.published_posts_count,
        last_published_at=task.last_published_at,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


def _post_response(post: SocialPost, *, versions_count: int = 0) -> SocialPostResponse:
    return SocialPostResponse(
        id=post.id,
        task_id=post.task_id,
        channel=post.channel,
        platform=post.platform,
        content_text=post.content_text,
        hashtags=post.hashtags or [],
        media_urls=post.media_urls or [],
        status=post.status,
        scheduled_at=post.scheduled_at,
        published_at=post.published_at,
        published_url=post.published_url,
        external_post_id=post.external_post_id,
        error_message=post.error_message,
        created_by_username=post.created_by_username,
        updated_by_username=post.updated_by_username,
        created_at=post.created_at,
        updated_at=post.updated_at,
        versions_count=versions_count,
    )


def _post_version_response(version: SocialPostVersion) -> SocialPostVersionResponse:
    return SocialPostVersionResponse(
        id=version.id,
        post_id=version.post_id,
        version_no=version.version_no,
        version_type=version.version_type,
        content_text=version.content_text,
        hashtags=version.hashtags or [],
        media_urls=version.media_urls or [],
        note=version.note,
        created_by_username=version.created_by_username,
        created_at=version.created_at,
    )


def _task_source_type(task: SocialTask) -> str:
    if task.event_id:
        return "event"
    if task.program_slot_id:
        return "program_slot"
    if task.story_id:
        return "story"
    if task.task_type == "breaking":
        return "breaking"
    if task.article_id:
        return "article"
    if task.task_type == "manual":
        return "manual"
    return task.task_type or "task"


def _task_source_ref(task: SocialTask, source_type: str) -> str | None:
    if source_type == "event" and task.event_id:
        return f"event:{task.event_id}"
    if source_type == "program_slot" and task.program_slot_id:
        return f"program_slot:{task.program_slot_id}"
    if source_type == "story" and task.story_id:
        return f"story:{task.story_id}"
    if task.article_id:
        return f"article:{task.article_id}"
    return None


def _is_auto_generated(task: SocialTask) -> bool:
    actor = (task.created_by_username or "").strip().lower()
    if actor in {"system", "auto", "scheduler"}:
        return True
    return task.created_by_user_id is None


def _post_stats_for_task(posts: list[SocialPost]) -> dict[str, Any]:
    counts = {
        "total": 0,
        "draft": 0,
        "ready": 0,
        "approved": 0,
        "scheduled": 0,
        "published": 0,
        "failed": 0,
    }
    next_scheduled_at: datetime | None = None
    for post in posts:
        counts["total"] += 1
        key = post.status if post.status in counts else None
        if key:
            counts[key] += 1
        if post.status == "scheduled" and post.scheduled_at:
            if next_scheduled_at is None or post.scheduled_at < next_scheduled_at:
                next_scheduled_at = post.scheduled_at
    counts["next_scheduled_at"] = next_scheduled_at
    return counts


def _task_trigger_window(task: SocialTask, *, source_type: str, now: datetime) -> str | None:
    if source_type == "breaking":
        if task.created_at >= now - timedelta(minutes=10):
            return "last_10m"
        return "breaking"
    if source_type == "event" and task.due_at:
        if task.due_at <= now + timedelta(hours=6):
            return "T-6"
        if task.due_at <= now + timedelta(hours=24):
            return "T-24"
        return "event_window"
    if source_type == "program_slot" and task.scheduled_at:
        delta_min = abs((task.scheduled_at - now).total_seconds()) / 60
        if delta_min <= 20:
            return "on_air"
        if task.scheduled_at > now and task.scheduled_at <= now + timedelta(hours=2):
            return "next_2h"
        return "program_window"
    return None


def _task_next_best_action(task: SocialTask, post_stats: dict[str, Any]) -> tuple[str, str]:
    if post_stats["failed"] > 0:
        return ("recover_failed", "استرجاع المنشور الفاشل")
    if task.owner_user_id is None:
        return ("assign_owner", "تعيين مسؤول للمهمة")
    if post_stats["total"] == 0:
        return ("generate_posts", "توليد منشورات")
    if post_stats["draft"] > 0 and post_stats["ready"] == 0 and post_stats["approved"] == 0:
        return ("review_drafts", "مراجعة وتحرير المسودات")
    if post_stats["ready"] > 0 and post_stats["approved"] == 0 and post_stats["published"] == 0:
        return ("approve_posts", "اعتماد المنشور الجاهز")
    if post_stats["approved"] > 0 and post_stats["scheduled"] == 0 and post_stats["published"] == 0:
        return ("publish_or_schedule", "نشر أو جدولة")
    if task.status == "todo":
        return ("start_task", "بدء التنفيذ")
    if task.status == "in_progress":
        return ("move_to_review", "نقل إلى المراجعة")
    return ("monitor", "متابعة الأداء")


def _task_why_now(task: SocialTask, *, source_type: str, now: datetime, post_stats: dict[str, Any]) -> str:
    if source_type == "breaking":
        return "تم إنشاء مهمة عاجلة لأن الخبر ضمن نافذة الدقائق الحرجة."
    if source_type == "program_slot" and task.scheduled_at:
        if task.scheduled_at <= now:
            return "البرنامج في نافذة البث الآن ويحتاج جاهزية النشر."
        minutes_left = int((task.scheduled_at - now).total_seconds() / 60)
        return f"البرنامج سيبدأ خلال {max(0, minutes_left)} دقيقة."
    if source_type == "event" and task.due_at:
        if task.due_at <= now + timedelta(hours=6):
            return "الحدث داخل نافذة T-6 ويحتاج تغطية سوشيال فورية."
        if task.due_at <= now + timedelta(hours=24):
            return "الحدث داخل نافذة T-24 ويحتاج تجهيز منشورات استباقية."
    if source_type == "story" and task.story_id:
        return "المهمة مرتبطة بقصة تحريرية نشطة وتحتاج تغطية رقمية."
    if post_stats["approved"] > 0 and post_stats["published"] == 0 and post_stats["scheduled"] == 0:
        return "يوجد منشور معتمد لكنه لم يُنشر أو يُجدول بعد."
    if task.due_at:
        return "المهمة مرتبطة بموعد استحقاق قريب."
    return "المهمة ضمن التشغيل اليومي لفريق الديجيتال."


def _task_risk_flags(task: SocialTask, *, post_stats: dict[str, Any], now: datetime) -> list[str]:
    flags: list[str] = []
    if task.owner_user_id is None:
        flags.append("بدون مسؤول")
    if post_stats["failed"] > 0:
        flags.append("يوجد منشور فاشل")
    if task.status in ACTIVE_TASK_STATUSES and post_stats["total"] == 0:
        flags.append("لا توجد منشورات بعد")
    if task.status == "review" and task.updated_at <= now - timedelta(hours=2):
        flags.append("معلّقة في المراجعة")
    if task.event_id and task.due_at and task.due_at <= now + timedelta(hours=6) and post_stats["total"] == 0:
        flags.append("حدث قريب بلا تغطية")
    return flags


@router.get("/overview", response_model=DigitalOverviewResponse)
async def overview(
    channel: str = Query(default="all", pattern="^(all|news|tv)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _assert_read(current_user)
    await _ensure_digital_tables(db)
    scope = await _get_scope_for_user(db, current_user)

    allowed_channels = _scope_channels(scope)
    if not allowed_channels:
        return DigitalOverviewResponse(
            total_tasks=0,
            due_today=0,
            overdue=0,
            in_progress=0,
            done_today=0,
            by_channel={},
            by_status={},
            scheduled_posts_next_24h=0,
            published_posts_24h=0,
            on_time_rate=0.0,
        )

    if channel != "all":
        _ensure_channel_allowed(channel, scope)
        effective_channels = {channel}
    else:
        effective_channels = allowed_channels

    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow_start = today_start + timedelta(days=1)

    task_rows = await db.execute(select(SocialTask).where(SocialTask.channel.in_(list(effective_channels))))
    tasks = task_rows.scalars().all()

    by_channel: dict[str, int] = {}
    by_status: dict[str, int] = {}
    total_tasks = len(tasks)
    due_today = 0
    overdue = 0
    in_progress = 0
    done_today = 0
    on_time_total = 0
    on_time_done = 0

    for task in tasks:
        by_channel[task.channel] = by_channel.get(task.channel, 0) + 1
        by_status[task.status] = by_status.get(task.status, 0) + 1
        if task.status == "in_progress":
            in_progress += 1
        if task.due_at and today_start <= task.due_at < tomorrow_start:
            due_today += 1
        if task.status in ACTIVE_TASK_STATUSES and task.due_at and task.due_at < now:
            overdue += 1
        if task.status == "done" and task.completed_at and task.completed_at >= today_start:
            done_today += 1
        if task.status == "done" and task.due_at and task.completed_at:
            on_time_total += 1
            if task.completed_at <= task.due_at:
                on_time_done += 1

    on_time_rate = round((on_time_done / on_time_total) * 100, 1) if on_time_total else 0.0

    scheduled_row = await db.execute(
        select(func.count(SocialPost.id))
        .join(SocialTask, SocialTask.id == SocialPost.task_id)
        .where(
            SocialTask.channel.in_(list(effective_channels)),
            SocialPost.status.in_(["scheduled", "approved"]),
            SocialPost.scheduled_at.isnot(None),
            SocialPost.scheduled_at >= now,
            SocialPost.scheduled_at <= now + timedelta(hours=24),
        )
    )
    scheduled_posts_next_24h = int(scheduled_row.scalar() or 0)

    published_row = await db.execute(
        select(func.count(SocialPost.id))
        .join(SocialTask, SocialTask.id == SocialPost.task_id)
        .where(
            SocialTask.channel.in_(list(effective_channels)),
            SocialPost.status == "published",
            SocialPost.published_at.isnot(None),
            SocialPost.published_at >= now - timedelta(hours=24),
        )
    )
    published_posts_24h = int(published_row.scalar() or 0)

    return DigitalOverviewResponse(
        total_tasks=total_tasks,
        due_today=due_today,
        overdue=overdue,
        in_progress=in_progress,
        done_today=done_today,
        by_channel=by_channel,
        by_status=by_status,
        scheduled_posts_next_24h=scheduled_posts_next_24h,
        published_posts_24h=published_posts_24h,
        on_time_rate=on_time_rate,
    )


@router.get("/action-desk", response_model=DigitalActionDeskResponse)
async def action_desk(
    channel: str = Query(default="all", pattern="^(all|news|tv)$"),
    limit_each: int = Query(default=10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _assert_read(current_user)
    await _ensure_digital_tables(db)

    scope = await _get_scope_for_user(db, current_user)
    allowed_channels = _scope_channels(scope)
    if channel != "all":
        _ensure_channel_allowed(channel, scope)
        effective_channels = {channel}
    else:
        effective_channels = allowed_channels
    if not effective_channels:
        return DigitalActionDeskResponse()

    now = datetime.utcnow()
    tasks_row = await db.execute(
        select(SocialTask)
        .where(
            SocialTask.channel.in_(list(effective_channels)),
            SocialTask.status != "cancelled",
        )
        .order_by(
            SocialTask.due_at.asc().nullslast(),
            SocialTask.priority.desc(),
            SocialTask.id.desc(),
        )
        .limit(600)
    )
    tasks = tasks_row.scalars().all()
    if not tasks:
        return DigitalActionDeskResponse()

    task_ids = [task.id for task in tasks]
    posts_row = await db.execute(
        select(SocialPost)
        .where(SocialPost.task_id.in_(task_ids))
        .order_by(SocialPost.created_at.desc())
    )
    posts_by_task: dict[int, list[SocialPost]] = {}
    for post in posts_row.scalars().all():
        posts_by_task.setdefault(post.task_id, []).append(post)

    now_items: list[DigitalTaskActionItem] = []
    next_items: list[DigitalTaskActionItem] = []
    risk_items: list[DigitalTaskActionItem] = []

    for task in tasks:
        task_posts = posts_by_task.get(task.id, [])
        post_stats = _post_stats_for_task(task_posts)
        source_type = _task_source_type(task)
        source_ref = _task_source_ref(task, source_type)
        trigger_window = _task_trigger_window(task, source_type=source_type, now=now)
        action_code, action_label = _task_next_best_action(task, post_stats)
        why_now = _task_why_now(task, source_type=source_type, now=now, post_stats=post_stats)
        risk_flags = _task_risk_flags(task, post_stats=post_stats, now=now)

        item = DigitalTaskActionItem(
            task=_task_response(task),
            next_best_action_code=action_code,
            next_best_action=action_label,
            why_now=why_now,
            source_type=source_type,
            source_ref=source_ref,
            auto_generated=_is_auto_generated(task),
            trigger_window=trigger_window,
            risk_flags=risk_flags,
        )

        is_now = False
        if source_type == "breaking" and task.created_at >= now - timedelta(minutes=10):
            is_now = True
        if task.program_slot_id and task.scheduled_at and abs((task.scheduled_at - now).total_seconds()) <= 20 * 60 and post_stats["total"] == 0:
            is_now = True
        if task.event_id and task.due_at and task.due_at <= now + timedelta(hours=24) and task.status in ACTIVE_TASK_STATUSES:
            is_now = True
        if post_stats["approved"] > 0 and post_stats["published"] == 0 and post_stats["scheduled"] == 0:
            is_now = True

        is_next = False
        if task.scheduled_at and now <= task.scheduled_at <= now + timedelta(hours=2):
            is_next = True
        if task.due_at and now <= task.due_at <= now + timedelta(hours=2):
            is_next = True
        if post_stats["next_scheduled_at"] and now <= post_stats["next_scheduled_at"] <= now + timedelta(hours=2):
            is_next = True

        if risk_flags:
            risk_items.append(item)
        if is_now:
            now_items.append(item)
        elif is_next:
            next_items.append(item)

    def _due_rank(value: datetime | str | None) -> float:
        if not value:
            return float("inf")
        if isinstance(value, datetime):
            return value.timestamp()
        try:
            return datetime.fromisoformat(value).timestamp()
        except Exception:  # noqa: BLE001
            return float("inf")

    now_items.sort(key=lambda x: (_due_rank(x.task.due_at), -x.task.priority, -x.task.id))
    next_items.sort(key=lambda x: (_due_rank(x.task.due_at), -x.task.priority, -x.task.id))
    risk_items.sort(key=lambda x: (-len(x.risk_flags), -x.task.priority, _due_rank(x.task.due_at), -x.task.id))

    return DigitalActionDeskResponse(
        now=now_items[:limit_each],
        next=next_items[:limit_each],
        at_risk=risk_items[:limit_each],
        now_count=len(now_items),
        next_count=len(next_items),
        at_risk_count=len(risk_items),
    )


@router.get("/scopes", response_model=list[DigitalTeamScopeResponse])
async def list_scopes(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _assert_manage(current_user)
    await _ensure_digital_tables(db)
    rows = await digital_team_service.list_scopes(db)
    return [DigitalTeamScopeResponse(**item) for item in rows]


@router.put("/scopes/{user_id:int}", response_model=DigitalTeamScopeResponse)
async def upsert_scope(
    user_id: int,
    payload: DigitalTeamScopeUpsertRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _assert_manage(current_user)
    await _ensure_digital_tables(db)
    try:
        scope = await digital_team_service.upsert_scope(
            db,
            user_id=user_id,
            can_manage_news=payload.can_manage_news,
            can_manage_tv=payload.can_manage_tv,
            platforms=payload.platforms,
            notes=payload.notes,
            actor=current_user,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    await db.commit()
    row = await db.execute(select(User).where(User.id == user_id))
    user = row.scalar_one_or_none()
    return DigitalTeamScopeResponse(
        id=scope.id,
        user_id=scope.user_id,
        username=user.username if user else None,
        full_name_ar=user.full_name_ar if user else None,
        can_manage_news=scope.can_manage_news,
        can_manage_tv=scope.can_manage_tv,
        platforms=scope.platforms or [],
        notes=scope.notes,
        created_at=scope.created_at,
        updated_at=scope.updated_at,
    )


@router.post("/program-slots/import", response_model=dict)
async def import_program_slots(
    overwrite: bool = Query(default=False),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _assert_manage(current_user)
    await _ensure_digital_tables(db)
    try:
        result = await digital_team_service.import_program_grid(
            db,
            actor=current_user,
            overwrite=overwrite,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    await db.commit()
    return {"message": "Program grid imported successfully.", **result}


@router.get("/program-slots", response_model=list[ProgramSlotResponse])
async def list_program_slots(
    channel: str = Query(default="all", pattern="^(all|news|tv)$"),
    is_active: bool | None = Query(default=None),
    day_of_week: int | None = Query(default=None, ge=0, le=6),
    limit: int = Query(default=500, ge=1, le=1000),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _assert_read(current_user)
    await _ensure_digital_tables(db)
    scope = await _get_scope_for_user(db, current_user)
    allowed_channels = _scope_channels(scope)

    if channel != "all":
        _ensure_channel_allowed(channel, scope)
        channels = {channel}
    else:
        channels = allowed_channels

    if not channels:
        return []

    query = select(ProgramSlot).where(ProgramSlot.channel.in_(list(channels)))
    if is_active is not None:
        query = query.where(ProgramSlot.is_active == is_active)
    if day_of_week is not None:
        query = query.where(ProgramSlot.day_of_week == day_of_week)

    query = query.order_by(
        ProgramSlot.channel.asc(),
        ProgramSlot.day_of_week.asc().nullsfirst(),
        ProgramSlot.start_time.asc(),
    ).limit(limit)
    rows = await db.execute(query)
    return [_slot_response(slot) for slot in rows.scalars().all()]


@router.post("/program-slots", response_model=ProgramSlotResponse, status_code=status.HTTP_201_CREATED)
async def create_program_slot(
    payload: ProgramSlotCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _assert_manage(current_user)
    await _ensure_digital_tables(db)

    start_time = _parse_hhmm(payload.start_time)
    slot = ProgramSlot(
        channel=payload.channel,
        program_title=payload.program_title.strip(),
        program_type=_normalize_text(payload.program_type, max_len=64),
        description=_normalize_text(payload.description, max_len=4000),
        day_of_week=payload.day_of_week,
        start_time=start_time,
        duration_minutes=payload.duration_minutes,
        timezone=payload.timezone.strip(),
        priority=payload.priority,
        is_active=payload.is_active,
        social_focus=_normalize_text(payload.social_focus, max_len=4000),
        tags=_normalize_list(payload.tags, max_items=40, max_len=48),
        source_ref=_normalize_text(payload.source_ref, max_len=2048),
        created_by_user_id=current_user.id,
        updated_by_user_id=current_user.id,
    )
    db.add(slot)

    try:
        await db.commit()
    except Exception as exc:  # noqa: BLE001
        await db.rollback()
        raise HTTPException(status_code=400, detail=f"Failed to create program slot: {exc}") from exc

    await db.refresh(slot)
    return _slot_response(slot)


@router.patch("/program-slots/{slot_id:int}", response_model=ProgramSlotResponse)
async def update_program_slot(
    slot_id: int,
    payload: ProgramSlotUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _assert_manage(current_user)
    await _ensure_digital_tables(db)

    row = await db.execute(select(ProgramSlot).where(ProgramSlot.id == slot_id))
    slot = row.scalar_one_or_none()
    if not slot:
        raise HTTPException(status_code=404, detail="Program slot not found")

    data = payload.model_dump(exclude_unset=True)
    if "program_title" in data:
        slot.program_title = data["program_title"].strip()
    if "program_type" in data:
        slot.program_type = _normalize_text(data["program_type"], max_len=64)
    if "description" in data:
        slot.description = _normalize_text(data["description"], max_len=4000)
    if "day_of_week" in data:
        slot.day_of_week = data["day_of_week"]
    if "start_time" in data and data["start_time"] is not None:
        slot.start_time = _parse_hhmm(data["start_time"])
    if "duration_minutes" in data:
        slot.duration_minutes = int(data["duration_minutes"])
    if "timezone" in data and data["timezone"] is not None:
        slot.timezone = data["timezone"].strip()
    if "priority" in data:
        slot.priority = int(data["priority"])
    if "is_active" in data:
        slot.is_active = bool(data["is_active"])
    if "social_focus" in data:
        slot.social_focus = _normalize_text(data["social_focus"], max_len=4000)
    if "tags" in data:
        slot.tags = _normalize_list(data["tags"], max_items=40, max_len=48)
    if "source_ref" in data:
        slot.source_ref = _normalize_text(data["source_ref"], max_len=2048)

    slot.updated_by_user_id = current_user.id
    slot.updated_at = datetime.utcnow()

    try:
        await db.commit()
    except Exception as exc:  # noqa: BLE001
        await db.rollback()
        raise HTTPException(status_code=400, detail=f"Failed to update program slot: {exc}") from exc

    await db.refresh(slot)
    return _slot_response(slot)


@router.delete("/program-slots/{slot_id:int}")
async def delete_program_slot(
    slot_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _assert_manage(current_user)
    await _ensure_digital_tables(db)

    row = await db.execute(select(ProgramSlot).where(ProgramSlot.id == slot_id))
    slot = row.scalar_one_or_none()
    if not slot:
        raise HTTPException(status_code=404, detail="Program slot not found")

    await db.delete(slot)
    await db.commit()
    return {"message": "Program slot deleted."}


@router.post("/generate", response_model=DigitalGenerationResponse)
async def generate_tasks(
    hours_ahead: int = Query(default=48, ge=1, le=168),
    include_events: bool = Query(default=True),
    include_breaking: bool = Query(default=True),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _assert_manage(current_user)
    await _ensure_digital_tables(db)

    stats = await digital_team_service.generate_all(
        db,
        actor=current_user,
        hours_ahead=hours_ahead,
        include_events=include_events,
        include_breaking=include_breaking,
    )
    await db.commit()
    return DigitalGenerationResponse(**stats)


@router.get("/playbooks", response_model=list[DigitalPlaybookTemplate])
async def list_playbooks(
    current_user: User = Depends(get_current_user),
):
    _assert_read(current_user)
    templates = digital_team_service.list_playbooks()
    return [DigitalPlaybookTemplate(**item) for item in templates]


@router.post("/tasks/{task_id:int}/bundle", response_model=DigitalBundleGenerateResponse)
async def generate_task_bundle(
    task_id: int,
    payload: DigitalBundleGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _assert_write(current_user)
    await _ensure_digital_tables(db)

    task_row = await db.execute(select(SocialTask).where(SocialTask.id == task_id))
    task = task_row.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    scope = await _get_scope_for_user(db, current_user)
    _ensure_channel_allowed(task.channel, scope)

    result = await digital_team_service.generate_bundle_for_task(
        db,
        task=task,
        playbook_key=payload.playbook_key,
        save_as_posts=payload.save_as_posts,
        actor=current_user,
    )
    await db.commit()
    return DigitalBundleGenerateResponse(**result)


@router.get("/tasks", response_model=SocialTaskListResponse)
async def list_tasks(
    q: str | None = Query(default=None),
    channel: str = Query(default="all", pattern="^(all|news|tv)$"),
    status_filter: str | None = Query(default=None, alias="status", pattern="^(todo|in_progress|review|done|cancelled)$"),
    owner_user_id: int | None = Query(default=None, ge=1),
    due_before: datetime | None = Query(default=None),
    only_active: bool = Query(default=False),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=60, ge=1, le=300),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _assert_read(current_user)
    await _ensure_digital_tables(db)

    scope = await _get_scope_for_user(db, current_user)
    allowed_channels = _scope_channels(scope)

    if channel != "all":
        _ensure_channel_allowed(channel, scope)
        channels = {channel}
    else:
        channels = allowed_channels

    if not channels:
        return SocialTaskListResponse(items=[], total=0, page=page, per_page=per_page, pages=0)

    filters = [SocialTask.channel.in_(list(channels))]
    if q:
        like = f"%{q.strip()}%"
        filters.append(or_(SocialTask.title.ilike(like), SocialTask.brief.ilike(like)))
    if status_filter:
        filters.append(SocialTask.status == status_filter)
    elif only_active:
        filters.append(SocialTask.status.in_(list(ACTIVE_TASK_STATUSES)))
    if owner_user_id is not None:
        filters.append(SocialTask.owner_user_id == owner_user_id)
    if due_before is not None:
        filters.append(SocialTask.due_at.isnot(None))
        filters.append(SocialTask.due_at <= due_before)

    predicate = and_(*filters)
    count_row = await db.execute(select(func.count(SocialTask.id)).where(predicate))
    total = int(count_row.scalar() or 0)
    pages = (total + per_page - 1) // per_page if total else 0

    rows = await db.execute(
        select(SocialTask)
        .where(predicate)
        .order_by(SocialTask.due_at.asc().nullslast(), SocialTask.priority.desc(), SocialTask.id.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    items = [_task_response(task) for task in rows.scalars().all()]
    return SocialTaskListResponse(items=items, total=total, page=page, per_page=per_page, pages=pages)


@router.post("/tasks", response_model=SocialTaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    payload: SocialTaskCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _assert_write(current_user)
    await _ensure_digital_tables(db)

    scope = await _get_scope_for_user(db, current_user)
    _ensure_channel_allowed(payload.channel, scope)

    owner_username = None
    if payload.owner_user_id is not None:
        owner_row = await db.execute(select(User).where(User.id == payload.owner_user_id))
        owner = owner_row.scalar_one_or_none()
        if not owner:
            raise HTTPException(status_code=400, detail="Owner user not found")
        owner_username = owner.username

    if payload.story_id is not None:
        story_row = await db.execute(select(Story).where(Story.id == payload.story_id))
        story = story_row.scalar_one_or_none()
        if not story:
            raise HTTPException(status_code=400, detail="Story not found")

    task = SocialTask(
        channel=payload.channel,
        platform=payload.platform,
        task_type=payload.task_type,
        title=payload.title.strip(),
        brief=_normalize_text(payload.brief, max_len=8000),
        status="todo",
        priority=payload.priority,
        due_at=payload.due_at,
        scheduled_at=payload.scheduled_at,
        owner_user_id=payload.owner_user_id,
        owner_username=owner_username,
        program_slot_id=payload.program_slot_id,
        event_id=payload.event_id,
        article_id=payload.article_id,
        story_id=payload.story_id,
        created_by_user_id=current_user.id,
        created_by_username=current_user.username,
        updated_by_user_id=current_user.id,
        updated_by_username=current_user.username,
    )
    db.add(task)

    try:
        await db.commit()
    except Exception as exc:  # noqa: BLE001
        await db.rollback()
        raise HTTPException(status_code=400, detail=f"Failed to create task: {exc}") from exc

    await db.refresh(task)
    return _task_response(task)


@router.patch("/tasks/{task_id:int}", response_model=SocialTaskResponse)
async def update_task(
    task_id: int,
    payload: SocialTaskUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _assert_write(current_user)
    await _ensure_digital_tables(db)

    row = await db.execute(select(SocialTask).where(SocialTask.id == task_id))
    task = row.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    scope = await _get_scope_for_user(db, current_user)
    _ensure_channel_allowed(task.channel, scope)

    data = payload.model_dump(exclude_unset=True)
    if "platform" in data and data["platform"] is not None:
        task.platform = data["platform"]
    if "task_type" in data and data["task_type"] is not None:
        task.task_type = data["task_type"]
    if "title" in data and data["title"] is not None:
        task.title = data["title"].strip()
    if "brief" in data:
        task.brief = _normalize_text(data["brief"], max_len=8000)
    if "priority" in data and data["priority"] is not None:
        task.priority = int(data["priority"])
    if "due_at" in data:
        task.due_at = data["due_at"]
    if "scheduled_at" in data:
        task.scheduled_at = data["scheduled_at"]

    if "owner_user_id" in data:
        owner_user_id = data["owner_user_id"]
        if owner_user_id is None:
            task.owner_user_id = None
            task.owner_username = None
        else:
            owner_row = await db.execute(select(User).where(User.id == owner_user_id))
            owner = owner_row.scalar_one_or_none()
            if not owner:
                raise HTTPException(status_code=400, detail="Owner user not found")
            task.owner_user_id = owner_user_id
            task.owner_username = owner.username

    if "story_id" in data:
        story_id = data["story_id"]
        if story_id is None:
            task.story_id = None
        else:
            story_row = await db.execute(select(Story).where(Story.id == story_id))
            story = story_row.scalar_one_or_none()
            if not story:
                raise HTTPException(status_code=400, detail="Story not found")
            task.story_id = story_id

    if "status" in data and data["status"] is not None:
        new_status = data["status"]
        task.status = new_status
        if new_status == "in_progress" and task.started_at is None:
            task.started_at = datetime.utcnow()
        if new_status in {"done", "cancelled"}:
            task.completed_at = task.completed_at or datetime.utcnow()
        if new_status in {"todo", "in_progress", "review"}:
            task.completed_at = None

    task.updated_by_user_id = current_user.id
    task.updated_by_username = current_user.username
    task.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(task)
    return _task_response(task)


@router.post("/tasks/{task_id:int}/compose", response_model=DigitalComposeResponse)
async def compose_task_post(
    task_id: int,
    payload: DigitalComposeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _assert_read(current_user)
    await _ensure_digital_tables(db)

    row = await db.execute(select(SocialTask).where(SocialTask.id == task_id))
    task = row.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    scope = await _get_scope_for_user(db, current_user)
    _ensure_channel_allowed(task.channel, scope)

    try:
        data = await digital_team_service.compose_for_task(
            db,
            task_id=task_id,
            platform=payload.platform,
            max_hashtags=payload.max_hashtags,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return DigitalComposeResponse(**data)


@router.get("/tasks/{task_id:int}/posts", response_model=SocialPostListResponse)
async def list_task_posts(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _assert_read(current_user)
    await _ensure_digital_tables(db)

    task_row = await db.execute(select(SocialTask).where(SocialTask.id == task_id))
    task = task_row.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    scope = await _get_scope_for_user(db, current_user)
    _ensure_channel_allowed(task.channel, scope)

    rows = await db.execute(select(SocialPost).where(SocialPost.task_id == task_id).order_by(SocialPost.created_at.desc()))
    posts = rows.scalars().all()
    post_ids = [post.id for post in posts]
    version_counts: dict[int, int] = {}
    if post_ids:
        version_rows = await db.execute(
            select(SocialPostVersion.post_id, func.count(SocialPostVersion.id))
            .where(SocialPostVersion.post_id.in_(post_ids))
            .group_by(SocialPostVersion.post_id)
        )
        version_counts = {int(post_id): int(count or 0) for post_id, count in version_rows.all()}
    items = [_post_response(post, versions_count=version_counts.get(post.id, 0)) for post in posts]
    return SocialPostListResponse(items=items, total=len(items))


@router.get("/posts/{post_id:int}/versions", response_model=SocialPostVersionListResponse)
async def list_post_versions(
    post_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _assert_read(current_user)
    await _ensure_digital_tables(db)

    row = await db.execute(select(SocialPost).where(SocialPost.id == post_id))
    post = row.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    task_row = await db.execute(select(SocialTask).where(SocialTask.id == post.task_id))
    task = task_row.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    scope = await _get_scope_for_user(db, current_user)
    _ensure_channel_allowed(task.channel, scope)

    versions = await digital_team_service.list_post_versions(db, post_id=post_id)
    return SocialPostVersionListResponse(
        items=[_post_version_response(version) for version in versions],
        total=len(versions),
    )


@router.post("/posts/{post_id:int}/versions/duplicate", response_model=SocialPostVersionResponse)
async def duplicate_post_version(
    post_id: int,
    payload: SocialPostVersionDuplicateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _assert_write(current_user)
    await _ensure_digital_tables(db)

    row = await db.execute(select(SocialPost).where(SocialPost.id == post_id))
    post = row.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    task_row = await db.execute(select(SocialTask).where(SocialTask.id == post.task_id))
    task = task_row.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    scope = await _get_scope_for_user(db, current_user)
    _ensure_channel_allowed(task.channel, scope)

    version = await digital_team_service.duplicate_post_version(
        db,
        post=post,
        source_version_no=payload.source_version_no,
        version_type=payload.version_type,
        note=payload.note,
        actor=current_user,
    )
    await digital_team_service.refresh_task_post_stats(db, post.task_id)
    await db.commit()
    return _post_version_response(version)


@router.get("/posts/{post_id:int}/compare", response_model=SocialPostCompareResponse)
async def compare_post_versions(
    post_id: int,
    base_version_no: int = Query(..., ge=1),
    target_version_no: int = Query(..., ge=1),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _assert_read(current_user)
    await _ensure_digital_tables(db)

    post_row = await db.execute(select(SocialPost).where(SocialPost.id == post_id))
    post = post_row.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    task_row = await db.execute(select(SocialTask).where(SocialTask.id == post.task_id))
    task = task_row.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    scope = await _get_scope_for_user(db, current_user)
    _ensure_channel_allowed(task.channel, scope)

    versions = await digital_team_service.list_post_versions(db, post_id=post_id)
    lookup = {version.version_no: version for version in versions}
    base = lookup.get(base_version_no)
    target = lookup.get(target_version_no)
    if not base or not target:
        raise HTTPException(status_code=404, detail="Requested versions were not found")

    diff = digital_team_service.compare_versions(base=base, target=target)
    return SocialPostCompareResponse(post_id=post_id, **diff)


@router.get("/posts/{post_id:int}/engagement-score", response_model=DigitalEngagementScoreResponse)
async def score_post_engagement(
    post_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _assert_read(current_user)
    await _ensure_digital_tables(db)

    row = await db.execute(select(SocialPost).where(SocialPost.id == post_id))
    post = row.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    task_row = await db.execute(select(SocialTask).where(SocialTask.id == post.task_id))
    task = task_row.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    scope = await _get_scope_for_user(db, current_user)
    _ensure_channel_allowed(task.channel, scope)

    score = digital_team_service.score_engagement(
        platform=post.platform,
        content_text=post.content_text,
        hashtags=post.hashtags or [],
        scheduled_at=post.scheduled_at,
    )
    return DigitalEngagementScoreResponse(
        post_id=post.id,
        platform=post.platform,
        score=score["score"],
        signals=score["signals"],
        recommendations=score["recommendations"],
    )


@router.post("/posts/{post_id:int}/regenerate", response_model=SocialPostResponse)
async def regenerate_post(
    post_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _assert_write(current_user)
    await _ensure_digital_tables(db)

    row = await db.execute(select(SocialPost).where(SocialPost.id == post_id))
    post = row.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    task_row = await db.execute(select(SocialTask).where(SocialTask.id == post.task_id))
    task = task_row.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    scope = await _get_scope_for_user(db, current_user)
    _ensure_channel_allowed(task.channel, scope)

    composed = await digital_team_service.compose_for_task(
        db,
        task_id=task.id,
        platform=post.platform,
        max_hashtags=6,
    )
    post.content_text = (composed.get("recommended_text") or post.content_text or "").strip()
    post.hashtags = list(composed.get("hashtags") or post.hashtags or [])
    post.status = "draft"
    post.updated_by_user_id = current_user.id
    post.updated_by_username = current_user.username
    post.updated_at = datetime.utcnow()

    await digital_team_service.create_post_version(
        db,
        post=post,
        version_type="regenerated",
        note="AI regenerate",
        actor=current_user,
    )
    await db.commit()

    count_row = await db.execute(
        select(func.count(SocialPostVersion.id)).where(SocialPostVersion.post_id == post.id)
    )
    versions_count = int(count_row.scalar() or 0)
    await db.refresh(post)
    return _post_response(post, versions_count=versions_count)


@router.post("/tasks/{task_id:int}/posts", response_model=SocialPostResponse, status_code=status.HTTP_201_CREATED)
async def create_task_post(
    task_id: int,
    payload: SocialPostCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _assert_write(current_user)
    await _ensure_digital_tables(db)

    task_row = await db.execute(select(SocialTask).where(SocialTask.id == task_id))
    task = task_row.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    scope = await _get_scope_for_user(db, current_user)
    _ensure_channel_allowed(task.channel, scope)

    post = SocialPost(
        task_id=task.id,
        channel=task.channel,
        platform=payload.platform,
        content_text=payload.content_text.strip(),
        hashtags=_normalize_list(payload.hashtags, max_items=30, max_len=48),
        media_urls=_normalize_list(payload.media_urls, max_items=15, max_len=2048),
        status=payload.status,
        scheduled_at=payload.scheduled_at,
        published_at=datetime.utcnow() if payload.status == "published" else None,
        published_url=_normalize_text(payload.published_url, max_len=2048),
        external_post_id=_normalize_text(payload.external_post_id, max_len=128),
        created_by_user_id=current_user.id,
        created_by_username=current_user.username,
        updated_by_user_id=current_user.id,
        updated_by_username=current_user.username,
    )
    db.add(post)
    await db.flush()
    await digital_team_service.create_post_version(
        db,
        post=post,
        version_type="generated" if (current_user.username or "").lower() == "system" else "edited",
        note="Initial version",
        actor=current_user,
    )
    await digital_team_service.refresh_task_post_stats(db, task.id)
    await db.commit()
    await db.refresh(post)
    return _post_response(post)


@router.patch("/posts/{post_id:int}", response_model=SocialPostResponse)
async def update_post(
    post_id: int,
    payload: SocialPostUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _assert_write(current_user)
    await _ensure_digital_tables(db)

    row = await db.execute(select(SocialPost).where(SocialPost.id == post_id))
    post = row.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    task_row = await db.execute(select(SocialTask).where(SocialTask.id == post.task_id))
    task = task_row.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    scope = await _get_scope_for_user(db, current_user)
    _ensure_channel_allowed(task.channel, scope)

    data = payload.model_dump(exclude_unset=True)
    if "content_text" in data and data["content_text"] is not None:
        post.content_text = data["content_text"].strip()
    if "hashtags" in data and data["hashtags"] is not None:
        post.hashtags = _normalize_list(data["hashtags"], max_items=30, max_len=48)
    if "media_urls" in data and data["media_urls"] is not None:
        post.media_urls = _normalize_list(data["media_urls"], max_items=15, max_len=2048)
    if "status" in data and data["status"] is not None:
        post.status = data["status"]
        if post.status == "published" and post.published_at is None:
            post.published_at = datetime.utcnow()
    if "scheduled_at" in data:
        post.scheduled_at = data["scheduled_at"]
    if "published_at" in data:
        post.published_at = data["published_at"]
    if "published_url" in data:
        post.published_url = _normalize_text(data["published_url"], max_len=2048)
    if "external_post_id" in data:
        post.external_post_id = _normalize_text(data["external_post_id"], max_len=128)
    if "error_message" in data:
        post.error_message = _normalize_text(data["error_message"], max_len=4000)

    post.updated_by_user_id = current_user.id
    post.updated_by_username = current_user.username
    post.updated_at = datetime.utcnow()

    version_note = _normalize_text(data.get("version_note"), max_len=4000) if isinstance(data, dict) else None
    version_type = "approved" if post.status == "approved" else "edited"
    await digital_team_service.create_post_version(
        db,
        post=post,
        version_type=version_type,
        note=version_note or f"Update status:{post.status}",
        actor=current_user,
    )
    await digital_team_service.refresh_task_post_stats(db, post.task_id)
    await db.commit()
    await db.refresh(post)
    return _post_response(post)


@router.post("/posts/{post_id:int}/mark-published", response_model=SocialPostResponse)
async def mark_post_published(
    post_id: int,
    published_url: str | None = Query(default=None),
    external_post_id: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _assert_write(current_user)
    await _ensure_digital_tables(db)

    row = await db.execute(select(SocialPost).where(SocialPost.id == post_id))
    post = row.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    task_row = await db.execute(select(SocialTask).where(SocialTask.id == post.task_id))
    task = task_row.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    scope = await _get_scope_for_user(db, current_user)
    _ensure_channel_allowed(task.channel, scope)

    post.status = "published"
    post.published_at = datetime.utcnow()
    post.published_url = _normalize_text(published_url, max_len=2048)
    post.external_post_id = _normalize_text(external_post_id, max_len=128)
    post.updated_by_user_id = current_user.id
    post.updated_by_username = current_user.username
    post.updated_at = datetime.utcnow()

    await digital_team_service.create_post_version(
        db,
        post=post,
        version_type="published",
        note="Marked as published",
        actor=current_user,
    )
    await digital_team_service.refresh_task_post_stats(db, post.task_id)
    await db.commit()
    await db.refresh(post)
    return _post_response(post)


@router.post("/posts/{post_id:int}/dispatch", response_model=DigitalDispatchResponse)
async def dispatch_post(
    post_id: int,
    payload: DigitalDispatchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _assert_write(current_user)
    await _ensure_digital_tables(db)

    row = await db.execute(select(SocialPost).where(SocialPost.id == post_id))
    post = row.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    task_row = await db.execute(select(SocialTask).where(SocialTask.id == post.task_id))
    task = task_row.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    scope = await _get_scope_for_user(db, current_user)
    _ensure_channel_allowed(task.channel, scope)

    result = await digital_team_service.dispatch_post(
        db,
        post=post,
        adapter=payload.adapter,
        action=payload.action,
        scheduled_at=payload.scheduled_at,
        published_url=payload.published_url,
        external_post_id=payload.external_post_id,
        actor=current_user,
    )
    await db.commit()
    return DigitalDispatchResponse(**result)


@router.get("/scopes/performance", response_model=DigitalScopePerformanceResponse)
async def scope_performance(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _assert_manage(current_user)
    await _ensure_digital_tables(db)
    rows = await digital_team_service.scope_performance(db)
    return DigitalScopePerformanceResponse(
        items=[DigitalScopePerformanceItem(**row) for row in rows],
        total=len(rows),
    )


@router.get("/calendar", response_model=DigitalCalendarResponse)
async def calendar(
    from_date: date = Query(default_factory=date.today),
    days: int = Query(default=7, ge=1, le=31),
    channel: str = Query(default="all", pattern="^(all|news|tv)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _assert_read(current_user)
    await _ensure_digital_tables(db)

    scope = await _get_scope_for_user(db, current_user)
    allowed_channels = _scope_channels(scope)
    if channel != "all":
        _ensure_channel_allowed(channel, scope)
        effective_channels = {channel}
    else:
        effective_channels = allowed_channels

    if not effective_channels:
        return DigitalCalendarResponse(from_date=from_date, days=days, items=[])

    window_start = datetime.combine(from_date, time.min)
    window_end = window_start + timedelta(days=days)

    items: list[DigitalCalendarItem] = []

    task_rows = await db.execute(
        select(SocialTask)
        .where(
            SocialTask.channel.in_(list(effective_channels)),
            SocialTask.scheduled_at.isnot(None),
            SocialTask.scheduled_at >= window_start,
            SocialTask.scheduled_at < window_end,
        )
        .order_by(SocialTask.scheduled_at.asc())
    )
    for task in task_rows.scalars().all():
        items.append(
            DigitalCalendarItem(
                item_type="task",
                channel=task.channel,
                title=task.title,
                starts_at=task.scheduled_at or task.due_at or task.created_at,
                ends_at=task.due_at,
                reference_id=task.id,
                status=task.status,
                priority=task.priority,
                source="social_tasks",
            )
        )

    event_rows = await db.execute(
        select(EventMemoItem).where(
            EventMemoItem.status.in_(list(ACTIVE_EVENT_STATUSES)),
            EventMemoItem.starts_at >= window_start,
            EventMemoItem.starts_at < window_end,
        )
    )
    for event in event_rows.scalars().all():
        mapped_channel = "tv" if event.scope == "religious" else "news"
        if mapped_channel not in effective_channels:
            continue
        items.append(
            DigitalCalendarItem(
                item_type="event",
                channel=mapped_channel,
                title=event.title,
                starts_at=event.starts_at,
                ends_at=event.ends_at,
                reference_id=event.id,
                status=event.status,
                priority=event.priority,
                source="event_memo_items",
            )
        )

    slot_rows = await db.execute(
        select(ProgramSlot)
        .where(
            ProgramSlot.channel.in_(list(effective_channels)),
            ProgramSlot.is_active == True,
        )
        .order_by(ProgramSlot.channel.asc(), ProgramSlot.start_time.asc())
    )
    slots = slot_rows.scalars().all()

    current_day = from_date
    final_day = from_date + timedelta(days=days)
    while current_day < final_day:
        for slot in slots:
            if slot.day_of_week is not None and current_day.weekday() != slot.day_of_week:
                continue
            starts_at = datetime.combine(current_day, slot.start_time)
            if not (window_start <= starts_at < window_end):
                continue
            items.append(
                DigitalCalendarItem(
                    item_type="program",
                    channel=slot.channel,
                    title=slot.program_title,
                    starts_at=starts_at,
                    ends_at=starts_at + timedelta(minutes=max(5, int(slot.duration_minutes or 60))),
                    reference_id=slot.id,
                    status="active" if slot.is_active else "inactive",
                    priority=slot.priority,
                    source="program_slots",
                )
            )
        current_day += timedelta(days=1)

    items.sort(key=lambda item: item.starts_at)
    return DigitalCalendarResponse(from_date=from_date, days=days, items=items)
