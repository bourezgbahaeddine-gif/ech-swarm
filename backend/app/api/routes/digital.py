"""
Digital Team API routes.
Operational board for social-media workflows across Echorouk News and TV.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.auth import get_current_user
from app.core.database import get_db
from app.models import EventMemoItem
from app.models.digital_team import ProgramSlot, SocialPost, SocialTask
from app.models.user import User, UserRole
from app.schemas.digital import (
    DigitalCalendarItem,
    DigitalCalendarResponse,
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
                to_regclass('public.social_posts') AS posts_tbl
            """
        )
    )
    row = checks.mappings().first()
    if not row or not (row["scopes_tbl"] and row["slots_tbl"] and row["tasks_tbl"] and row["posts_tbl"]):
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
        owner_user_id=task.owner_user_id,
        owner_username=task.owner_username,
        published_posts_count=task.published_posts_count,
        last_published_at=task.last_published_at,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


def _post_response(post: SocialPost) -> SocialPostResponse:
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
    )


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
    items = [_post_response(post) for post in rows.scalars().all()]
    return SocialPostListResponse(items=items, total=len(items))


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

    await digital_team_service.refresh_task_post_stats(db, post.task_id)
    await db.commit()
    await db.refresh(post)
    return _post_response(post)


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
