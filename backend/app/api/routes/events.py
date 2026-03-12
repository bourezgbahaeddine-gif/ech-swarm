"""
Events memo board API.
Planning board for upcoming coverage-worthy events.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.auth import get_current_user
from app.core.database import get_db
from app.models import EventMemoItem, ScriptProject, SocialPost, SocialTask, Story, StoryItem
from app.models.user import User, UserRole
from app.schemas.events import (
    EventActionItem,
    EventActionItemsResponse,
    EventAutomationRunResponse,
    EventCoverageResponse,
    EventLinkStoryRequest,
    EventMemoCreateRequest,
    EventMemoListResponse,
    EventMemoOverviewResponse,
    EventMemoRemindersResponse,
    EventMemoResponse,
    EventMemoUpdateRequest,
    EventPlaybookTemplate,
)

router = APIRouter(prefix="/events", tags=["Events Memo"])

READ_ROLES = {
    UserRole.director,
    UserRole.editor_chief,
    UserRole.journalist,
    UserRole.social_media,
    UserRole.print_editor,
}
WRITE_ROLES = {
    UserRole.director,
    UserRole.editor_chief,
    UserRole.journalist,
    UserRole.social_media,
    UserRole.print_editor,
}
MANAGE_ROLES = {
    UserRole.director,
    UserRole.editor_chief,
}
ACTIVE_STATUSES = {"planned", "monitoring"}
READINESS_STATES = {"idea", "assigned", "prepared", "ready", "covered"}
ACTION_SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}
EVENT_DB_PATH = Path(__file__).resolve().parents[2] / "data" / "events" / "event_db.json"
PLAYBOOKS: dict[str, dict[str, list[str] | str]] = {
    "general": {
        "label": "تغطية عامة",
        "checklist": [
            "تحديد الزاوية",
            "تجميع المصادر",
            "تأكيد المسؤول",
            "تجهيز فقرة خلفية",
            "خطة المتابعة",
        ],
        "timeline": [
            "T-24 تجهيز الخلفية",
            "T-6 تحديث المعطيات",
            "T-1 تجهيز قالب سريع",
            "T+1 متابعة ما بعد الحدث",
        ],
    },
    "election": {
        "label": "تغطية انتخابات",
        "checklist": [
            "خلفية الدائرة",
            "ملف المرشحين",
            "بيانات رسمية",
            "نسب المشاركة",
            "تحليل النتائج",
        ],
        "timeline": [
            "T-48 ملف الخلفية",
            "T-24 تجهيز فريق المتابعة",
            "T-6 قوالب النتائج",
            "T+1 تحليل أولي",
        ],
    },
    "summit": {
        "label": "تغطية قمة دولية",
        "checklist": [
            "أجندة القمة",
            "ملف العلاقات الثنائية",
            "التصريحات المتوقعة",
            "البيان الختامي",
            "الأثر الإقليمي",
        ],
        "timeline": [
            "T-24 خلفية دبلوماسية",
            "T-6 نقاط النقاش",
            "T-1 قالب خبر عاجل",
            "T+1 تحليل مخرجات",
        ],
    },
    "religious": {
        "label": "تغطية حدث ديني",
        "checklist": [
            "الخلفية الدينية",
            "الجهات الرسمية",
            "الإجراءات التنظيمية",
            "الأثر الاجتماعي",
            "متابعة ميدانية",
        ],
        "timeline": [
            "T-24 تجهيز الخلفية",
            "T-6 تأكيد التغطية",
            "T-1 تجهيز القالب",
            "T+1 حصيلة وتفاعل",
        ],
    },
}


def _assert_read(user: User) -> None:
    if user.role not in READ_ROLES:
        raise HTTPException(status_code=403, detail="غير مسموح لك بالوصول إلى لوحة الأحداث.")


def _assert_write(user: User) -> None:
    if user.role not in WRITE_ROLES:
        raise HTTPException(status_code=403, detail="غير مسموح لك بإضافة أو تعديل الأحداث.")


def _assert_manage(user: User) -> None:
    if user.role not in MANAGE_ROLES:
        raise HTTPException(status_code=403, detail="غير مسموح لك بإدارة هذا الإجراء.")


def _normalize_dt(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _normalize_text(value: str | None) -> str | None:
    if value is None:
        return None
    clean = value.strip()
    return clean or None


def _normalize_playbook_key(value: str | None) -> str:
    raw = (value or "").strip().lower()
    return raw if raw in PLAYBOOKS else "general"


def _playbook_checklist(value: str | None) -> list[str]:
    key = _normalize_playbook_key(value)
    configured = PLAYBOOKS.get(key, {})
    return [str(item) for item in configured.get("checklist", [])]


def _playbook_timeline(value: str | None) -> list[str]:
    key = _normalize_playbook_key(value)
    configured = PLAYBOOKS.get(key, {})
    return [str(item) for item in configured.get("timeline", [])]


def _clean_title(value: str) -> str:
    clean = (value or "").strip()
    if len(clean) < 3:
        raise HTTPException(status_code=400, detail="عنوان الحدث يجب أن يكون أوضح (3 أحرف على الأقل).")
    return clean


def _parse_seed_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    raw = value.strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    parsed = datetime.fromisoformat(raw)
    return _normalize_dt(parsed)


def _normalize_tags(values: list[str] | None) -> list[str]:
    if not values:
        return []
    items: list[str] = []
    seen = set()
    for value in values:
        clean = (value or "").strip()
        if not clean:
            continue
        clean = clean[:48]
        key = clean.lower()
        if key in seen:
            continue
        seen.add(key)
        items.append(clean)
    return items


def _normalize_string_list(values: list[str] | None, max_items: int = 20, max_len: int = 140) -> list[str]:
    if not values:
        return []
    items: list[str] = []
    seen = set()
    for value in values[:max_items]:
        clean = (value or "").strip()
        if not clean:
            continue
        clean = clean[:max_len]
        key = clean.lower()
        if key in seen:
            continue
        seen.add(key)
        items.append(clean)
    return items


async def _resolve_owner(db: AsyncSession, owner_user_id: int | None) -> tuple[int | None, str | None]:
    if owner_user_id is None:
        return None, None
    row = await db.execute(select(User).where(User.id == owner_user_id))
    user = row.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=400, detail="المستخدم المسؤول غير موجود.")
    return user.id, user.username


async def _load_story_lookup(db: AsyncSession, items: list[EventMemoItem]) -> dict[int, Story]:
    story_ids = sorted({int(item.story_id) for item in items if item.story_id})
    if not story_ids:
        return {}
    rows = await db.execute(select(Story).where(Story.id.in_(story_ids)))
    return {int(story.id): story for story in rows.scalars().all()}


def _compute_readiness_breakdown(item: EventMemoItem) -> tuple[int, dict[str, int]]:
    sources = 100 if _normalize_text(item.source_url) else 20
    ownership = 100 if item.owner_user_id else 0
    background = 100 if _normalize_text(item.summary) or _normalize_text(item.coverage_plan) else 30
    checklist_size = len(item.checklist or [])
    planning = 100 if checklist_size >= 4 else (70 if checklist_size >= 2 else 30)
    story_link = 100 if item.story_id else 20
    workflow = {
        "idea": 20,
        "assigned": 50,
        "prepared": 75,
        "ready": 100,
        "covered": 100,
    }.get(item.readiness_status, 20)

    breakdown = {
        "sources": int(sources),
        "ownership": int(ownership),
        "background": int(background),
        "planning": int(planning),
        "story_link": int(story_link),
        "workflow": int(workflow),
    }
    score = round(
        (sources * 0.18)
        + (ownership * 0.20)
        + (background * 0.18)
        + (planning * 0.16)
        + (story_link * 0.14)
        + (workflow * 0.14)
    )
    return int(max(0, min(100, score))), breakdown


def _next_best_action(item: EventMemoItem, now: datetime) -> str:
    if not item.story_id and item.starts_at <= now + timedelta(hours=24):
        return "create_story"
    if not item.owner_user_id:
        return "assign_owner"
    if item.readiness_status not in {"prepared", "ready", "covered"} and item.starts_at <= now + timedelta(hours=6):
        return "prepare_now"
    if item.status == "planned" and item.starts_at <= now + timedelta(hours=6):
        return "set_monitoring"
    if item.status in ACTIVE_STATUSES and item.starts_at <= now:
        return "publish_followup"
    return "open_event"


def _as_response(
    item: EventMemoItem,
    *,
    now: datetime,
    story_lookup: dict[int, Story] | None = None,
) -> EventMemoResponse:
    prep_starts_at = item.starts_at - timedelta(hours=max(1, int(item.lead_time_hours or 24)))
    is_due_soon = item.status in ACTIVE_STATUSES and prep_starts_at <= now
    is_overdue = item.status in ACTIVE_STATUSES and item.starts_at < now
    readiness_score, readiness_breakdown = _compute_readiness_breakdown(item)
    story = (story_lookup or {}).get(item.story_id) if item.story_id else None
    return EventMemoResponse(
        id=item.id,
        scope=item.scope,
        title=item.title,
        summary=item.summary,
        coverage_plan=item.coverage_plan,
        starts_at=item.starts_at,
        ends_at=item.ends_at,
        timezone=item.timezone,
        country_code=item.country_code,
        is_all_day=item.is_all_day,
        lead_time_hours=item.lead_time_hours,
        priority=item.priority,
        status=item.status,
        readiness_status=item.readiness_status,
        source_url=item.source_url,
        tags=item.tags or [],
        checklist=item.checklist or [],
        playbook_key=_normalize_playbook_key(item.playbook_key),
        story_id=item.story_id,
        story_key=story.story_key if story else None,
        story_title=story.title if story else None,
        prep_starts_at=prep_starts_at,
        is_due_soon=is_due_soon,
        is_overdue=is_overdue,
        readiness_score=readiness_score,
        readiness_breakdown=readiness_breakdown,
        preparation_started_at=item.preparation_started_at,
        owner_user_id=item.owner_user_id,
        owner_username=item.owner_username,
        created_by_user_id=item.created_by_user_id,
        created_by_username=item.created_by_username,
        updated_by_user_id=item.updated_by_user_id,
        updated_by_username=item.updated_by_username,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


async def _as_responses(db: AsyncSession, items: list[EventMemoItem], *, now: datetime) -> list[EventMemoResponse]:
    story_lookup = await _load_story_lookup(db, items)
    return [_as_response(item, now=now, story_lookup=story_lookup) for item in items]


def _validate_dates(starts_at: datetime, ends_at: datetime | None) -> None:
    if ends_at is not None and ends_at < starts_at:
        raise HTTPException(status_code=400, detail="تاريخ نهاية الحدث يجب أن يكون بعد تاريخ البداية.")


async def _ensure_events_table(db: AsyncSession) -> None:
    checks = await db.execute(
        text(
            """
            SELECT to_regclass('public.event_memo_items') AS events_tbl
            """
        )
    )
    row = checks.mappings().first()
    if not row or not row["events_tbl"]:
        raise HTTPException(
            status_code=503,
            detail="جدول لوحة الأحداث غير جاهز. نفّذ ترحيل قاعدة البيانات: alembic upgrade head",
        )


async def _load_event_or_404(db: AsyncSession, event_id: int) -> EventMemoItem:
    row = await db.execute(select(EventMemoItem).where(EventMemoItem.id == event_id))
    item = row.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="الحدث غير موجود.")
    return item


async def _create_story_from_event(
    db: AsyncSession,
    item: EventMemoItem,
    *,
    actor: User,
    title: str | None = None,
    summary: str | None = None,
    category: str | None = None,
    geography: str | None = None,
) -> Story:
    story = Story(
        story_key=f"STY-{datetime.utcnow():%Y%m%d}-{uuid4().hex[:8].upper()}",
        title=_clean_title(title or item.title),
        summary=_normalize_text(summary) or _normalize_text(item.summary),
        category=_normalize_text(category) or _normalize_text(item.scope),
        geography=_normalize_text(geography) or ("DZ" if item.scope == "national" else None),
        priority=max(1, min(10, int(item.priority or 3) + 2)),
        created_by=actor.username,
        updated_by=actor.username,
    )
    db.add(story)
    await db.flush()
    return story


def _build_preparation_timeline(item: EventMemoItem) -> list[dict]:
    checkpoints = [
        ("t48", "T-48h", item.starts_at - timedelta(hours=48), "فتح القصة أو تحديثها"),
        ("t24", "T-24h", item.starts_at - timedelta(hours=24), "تجهيز الخلفية والمصادر"),
        ("t6", "T-6h", item.starts_at - timedelta(hours=6), "متابعة تنفيذ التغطية"),
        ("t1", "T-1h", item.starts_at - timedelta(hours=1), "تجهيز قالب التحديث السريع"),
        ("event", "Event", item.starts_at, "لحظة الحدث"),
        ("tplus1", "T+1h", item.starts_at + timedelta(hours=1), "نشر متابعة ما بعد الحدث"),
    ]
    now = datetime.utcnow()
    readiness_score, _ = _compute_readiness_breakdown(item)
    rows: list[dict] = []
    for code, label, dt, action in checkpoints:
        if code in {"event", "tplus1"}:
            done = item.status == "covered"
        elif code == "t1":
            done = item.readiness_status in {"ready", "covered"}
        elif code == "t6":
            done = item.readiness_status in {"prepared", "ready", "covered"}
        elif code == "t24":
            done = bool(item.owner_user_id) and readiness_score >= 45
        else:
            done = bool(item.story_id)
        rows.append(
            {
                "code": code,
                "label": label,
                "due_at": dt,
                "is_due": dt <= now,
                "done": done,
                "action": action,
            }
        )
    return rows


async def _build_coverage_payload(db: AsyncSession, item: EventMemoItem) -> EventCoverageResponse:
    now = datetime.utcnow()
    story = None
    if item.story_id:
        story_row = await db.execute(select(Story).where(Story.id == item.story_id))
        story = story_row.scalar_one_or_none()

    articles_count = 0
    drafts_count = 0
    scripts_count = 0
    social_tasks_count = 0
    social_posts_count = 0

    if item.story_id:
        article_count_row = await db.execute(
            select(func.count(StoryItem.id)).where(StoryItem.story_id == item.story_id, StoryItem.article_id.is_not(None))
        )
        draft_count_row = await db.execute(
            select(func.count(StoryItem.id)).where(StoryItem.story_id == item.story_id, StoryItem.draft_id.is_not(None))
        )
        script_count_row = await db.execute(select(func.count(ScriptProject.id)).where(ScriptProject.story_id == item.story_id))
        articles_count = int(article_count_row.scalar() or 0)
        drafts_count = int(draft_count_row.scalar() or 0)
        scripts_count = int(script_count_row.scalar() or 0)

    social_tasks_row = await db.execute(select(func.count(SocialTask.id)).where(SocialTask.event_id == item.id))
    social_posts_row = await db.execute(
        select(func.count(SocialPost.id))
        .select_from(SocialPost)
        .join(SocialTask, SocialTask.id == SocialPost.task_id)
        .where(SocialTask.event_id == item.id)
    )
    social_tasks_count = int(social_tasks_row.scalar() or 0)
    social_posts_count = int(social_posts_row.scalar() or 0)

    readiness_score, readiness_breakdown = _compute_readiness_breakdown(item)
    has_story = 100 if item.story_id else 0
    article_stage = 100 if articles_count > 0 else 20
    script_stage = 100 if scripts_count > 0 else 20
    social_stage = 100 if social_posts_count > 0 else (60 if social_tasks_count > 0 else 20)
    workflow_stage = 100 if item.status == "covered" else (70 if item.status == "monitoring" else 30)
    coverage_score = round(
        (has_story * 0.22)
        + (article_stage * 0.26)
        + (script_stage * 0.16)
        + (social_stage * 0.18)
        + (workflow_stage * 0.18)
    )

    timeline_payload = [
        {
            **step,
            "due_at": step["due_at"].isoformat() if isinstance(step["due_at"], datetime) else None,
        }
        for step in _build_preparation_timeline(item)
    ]

    return EventCoverageResponse(
        event_id=item.id,
        story_id=item.story_id,
        story_key=story.story_key if story else None,
        story_title=story.title if story else None,
        coverage_score=int(max(0, min(100, coverage_score))),
        readiness_score=readiness_score,
        readiness_breakdown=readiness_breakdown,
        metrics={
            "articles": articles_count,
            "drafts": drafts_count,
            "scripts": scripts_count,
            "social_tasks": social_tasks_count,
            "social_posts": social_posts_count,
        },
        timeline=timeline_payload,
        next_action=_next_best_action(item, now),
    )


@router.get("/playbooks", response_model=list[EventPlaybookTemplate])
async def list_playbooks(
    current_user: User = Depends(get_current_user),
):
    _assert_read(current_user)
    return [
        EventPlaybookTemplate(
            key=key,
            label=str(config.get("label") or key),
            checklist=[str(item) for item in config.get("checklist", [])],
            timeline=[str(item) for item in config.get("timeline", [])],
        )
        for key, config in PLAYBOOKS.items()
    ]


@router.get("/overview", response_model=EventMemoOverviewResponse)
async def overview(
    window_days: int = Query(default=14, ge=1, le=90),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _assert_read(current_user)
    await _ensure_events_table(db)
    now = datetime.utcnow()
    window_end = now + timedelta(days=window_days)

    rows = await db.execute(
        select(EventMemoItem).where(EventMemoItem.starts_at <= window_end).order_by(EventMemoItem.starts_at.asc())
    )
    items = rows.scalars().all()

    by_scope: dict[str, int] = {"national": 0, "international": 0, "religious": 0}
    by_status: dict[str, int] = {"planned": 0, "monitoring": 0, "covered": 0, "dismissed": 0}
    upcoming_24h = 0
    upcoming_7d = 0
    overdue = 0
    total = 0
    reminder_t24 = 0
    reminder_t6 = 0
    due_total = 0
    covered_due = 0
    prep_eligible = 0
    prep_on_time = 0
    for item in items:
        by_scope[item.scope] = by_scope.get(item.scope, 0) + 1
        by_status[item.status] = by_status.get(item.status, 0) + 1
        if item.status in ACTIVE_STATUSES:
            total += 1
            if item.starts_at < now:
                overdue += 1
            elif item.starts_at <= now + timedelta(hours=24):
                upcoming_24h += 1
            if now <= item.starts_at <= now + timedelta(days=7):
                upcoming_7d += 1
            if now < item.starts_at <= now + timedelta(hours=24):
                reminder_t24 += 1
            if now < item.starts_at <= now + timedelta(hours=6):
                reminder_t6 += 1

        if item.starts_at <= now:
            due_total += 1
            if item.status == "covered":
                covered_due += 1
            if item.status != "dismissed":
                prep_eligible += 1
                if item.preparation_started_at:
                    prep_deadline = item.starts_at - timedelta(hours=max(1, int(item.lead_time_hours or 24)))
                    if item.preparation_started_at <= prep_deadline:
                        prep_on_time += 1

    coverage_rate = round((covered_due / due_total) * 100, 1) if due_total else 0.0
    on_time_preparation_rate = round((prep_on_time / prep_eligible) * 100, 1) if prep_eligible else 0.0

    return EventMemoOverviewResponse(
        window_days=window_days,
        total=total,
        upcoming_24h=upcoming_24h,
        upcoming_7d=upcoming_7d,
        overdue=overdue,
        by_scope=by_scope,
        by_status=by_status,
        reminders={"t24_due": reminder_t24, "t6_due": reminder_t6},
        kpi={
            "due_total": due_total,
            "covered_due": covered_due,
            "coverage_rate": coverage_rate,
            "missed_events": overdue,
            "prep_eligible": prep_eligible,
            "prep_on_time": prep_on_time,
            "on_time_preparation_rate": on_time_preparation_rate,
        },
    )


@router.get("/action-items", response_model=EventActionItemsResponse)
async def action_items(
    limit: int = Query(default=40, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _assert_read(current_user)
    await _ensure_events_table(db)
    now = datetime.utcnow()
    rows = await db.execute(
        select(EventMemoItem)
        .where(EventMemoItem.status.in_(list(ACTIVE_STATUSES)))
        .where(EventMemoItem.starts_at <= now + timedelta(days=5))
        .order_by(EventMemoItem.starts_at.asc(), EventMemoItem.priority.desc())
        .limit(max(limit * 2, 50))
    )
    raw_items = rows.scalars().all()
    responses = await _as_responses(db, raw_items, now=now)
    response_by_id = {event.id: event for event in responses}

    payload: list[EventActionItem] = []
    for item in raw_items:
        event = response_by_id[item.id]
        if item.starts_at <= now + timedelta(hours=6) and item.readiness_status not in {"prepared", "ready", "covered"}:
            payload.append(
                EventActionItem(
                    code="prep_due_6h",
                    severity="high",
                    title="حدث خلال 6 ساعات بدون جاهزية كافية",
                    recommendation="شغّل وضع السرعة أو ارفع الجاهزية إلى prepared على الأقل.",
                    action="prepare_now",
                    event=event,
                )
            )
        if item.starts_at <= now + timedelta(hours=24) and not item.owner_user_id:
            payload.append(
                EventActionItem(
                    code="owner_missing_24h",
                    severity="high",
                    title="حدث خلال 24 ساعة بدون مالك",
                    recommendation="عيّن صحفياً مسؤولاً لتفادي ضياع التغطية.",
                    action="assign_owner",
                    event=event,
                )
            )
        if item.starts_at <= now + timedelta(hours=24) and not item.story_id:
            payload.append(
                EventActionItem(
                    code="story_missing_24h",
                    severity="medium",
                    title="لا توجد قصة تحريرية مرتبطة",
                    recommendation="أنشئ قصة مرتبطة ثم اربط مواد المتابعة بها.",
                    action="create_story",
                    event=event,
                )
            )
        if item.starts_at <= now and item.status != "covered":
            payload.append(
                EventActionItem(
                    code="coverage_missing_after_start",
                    severity="high",
                    title="الحدث بدأ ولم يتم إغلاق التغطية",
                    recommendation="انشر متابعة سريعة ثم حدّث الحالة إلى covered عند الإنهاء.",
                    action="publish_followup",
                    event=event,
                )
            )
        if item.starts_at <= now + timedelta(hours=48) and event.readiness_score < 60:
            payload.append(
                EventActionItem(
                    code="readiness_low",
                    severity="medium",
                    title="درجة الجاهزية أقل من المطلوب",
                    recommendation="أكمل checklist واربط الحدث بالقصة لرفع الجاهزية.",
                    action="raise_readiness",
                    event=event,
                )
            )

    payload.sort(
        key=lambda action: (
            ACTION_SEVERITY_ORDER.get(action.severity, 9),
            action.event.starts_at,
            -int(action.event.priority),
        )
    )
    payload = payload[:limit]
    high = sum(1 for item in payload if item.severity == "high")
    medium = sum(1 for item in payload if item.severity == "medium")
    low = sum(1 for item in payload if item.severity == "low")
    return EventActionItemsResponse(total=len(payload), high=high, medium=medium, low=low, items=payload)


@router.get("/reminders", response_model=EventMemoRemindersResponse)
async def reminders(
    limit: int = Query(default=50, ge=1, le=300),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _assert_read(current_user)
    await _ensure_events_table(db)
    now = datetime.utcnow()
    window_end = now + timedelta(hours=24)
    rows = await db.execute(
        select(EventMemoItem)
        .where(
            EventMemoItem.status.in_(list(ACTIVE_STATUSES)),
            EventMemoItem.starts_at > now,
            EventMemoItem.starts_at <= window_end,
        )
        .order_by(EventMemoItem.starts_at.asc(), EventMemoItem.priority.desc())
        .limit(limit)
    )
    raw_items = rows.scalars().all()
    responses = await _as_responses(db, raw_items, now=now)
    response_map = {item.id: item for item in responses}
    t24: list[EventMemoResponse] = []
    t6: list[EventMemoResponse] = []
    for item in raw_items:
        response = response_map[item.id]
        if item.starts_at <= now + timedelta(hours=6):
            t6.append(response)
        else:
            t24.append(response)
    return EventMemoRemindersResponse(t24=t24, t6=t6)


@router.get("/", response_model=EventMemoListResponse)
async def list_events(
    q: str | None = Query(default=None),
    scope: str | None = Query(default=None, pattern="^(national|international|religious)$"),
    status_filter: str | None = Query(default=None, alias="status", pattern="^(planned|monitoring|covered|dismissed)$"),
    only_active: bool = Query(default=True),
    from_at: datetime | None = Query(default=None),
    to_at: datetime | None = Query(default=None),
    story_id: int | None = Query(default=None, ge=1),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=300),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _assert_read(current_user)
    await _ensure_events_table(db)

    query = select(EventMemoItem)
    count_query = select(func.count(EventMemoItem.id))
    filters = []
    if q:
        like = f"%{q.strip()}%"
        filters.append(or_(EventMemoItem.title.ilike(like), EventMemoItem.summary.ilike(like), EventMemoItem.coverage_plan.ilike(like)))
    if scope:
        filters.append(EventMemoItem.scope == scope)
    if status_filter:
        filters.append(EventMemoItem.status == status_filter)
    elif only_active:
        filters.append(EventMemoItem.status.in_(list(ACTIVE_STATUSES)))
    if from_at:
        filters.append(EventMemoItem.starts_at >= _normalize_dt(from_at))
    if to_at:
        filters.append(EventMemoItem.starts_at <= _normalize_dt(to_at))
    if story_id:
        filters.append(EventMemoItem.story_id == story_id)

    if filters:
        predicate = and_(*filters)
        query = query.where(predicate)
        count_query = count_query.where(predicate)

    total_result = await db.execute(count_query)
    total = int(total_result.scalar() or 0)
    pages = (total + per_page - 1) // per_page
    query = query.order_by(EventMemoItem.starts_at.asc(), EventMemoItem.priority.desc(), EventMemoItem.id.desc())
    query = query.offset((page - 1) * per_page).limit(per_page)

    rows = await db.execute(query)
    now = datetime.utcnow()
    items = await _as_responses(db, rows.scalars().all(), now=now)
    return EventMemoListResponse(items=items, total=total, page=page, per_page=per_page, pages=pages)


@router.get("/upcoming", response_model=list[EventMemoResponse])
async def upcoming_events(
    hours: int = Query(default=72, ge=1, le=24 * 60),
    limit: int = Query(default=200, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _assert_read(current_user)
    await _ensure_events_table(db)
    now = datetime.utcnow()
    window_end = now + timedelta(hours=hours)
    rows = await db.execute(
        select(EventMemoItem)
        .where(
            EventMemoItem.status.in_(list(ACTIVE_STATUSES)),
            EventMemoItem.starts_at >= now,
            EventMemoItem.starts_at <= window_end,
        )
        .order_by(EventMemoItem.starts_at.asc(), EventMemoItem.priority.desc())
        .limit(limit)
    )
    return await _as_responses(db, rows.scalars().all(), now=now)


@router.get("/{event_id:int}/coverage", response_model=EventCoverageResponse)
async def event_coverage(
    event_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _assert_read(current_user)
    await _ensure_events_table(db)
    item = await _load_event_or_404(db, event_id)
    return await _build_coverage_payload(db, item)


@router.post("/", response_model=EventMemoResponse, status_code=status.HTTP_201_CREATED)
async def create_event(
    payload: EventMemoCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _assert_write(current_user)
    await _ensure_events_table(db)

    starts_at = _normalize_dt(payload.starts_at)
    ends_at = _normalize_dt(payload.ends_at)
    assert starts_at is not None
    _validate_dates(starts_at, ends_at)
    owner_user_id, owner_username = await _resolve_owner(db, payload.owner_user_id)
    readiness_status = payload.readiness_status if payload.readiness_status in READINESS_STATES else "idea"
    preparation_started_at = None
    if readiness_status in {"prepared", "ready", "covered"}:
        preparation_started_at = datetime.utcnow()
    if payload.status == "covered":
        readiness_status = "covered"
    story_id = payload.story_id
    if story_id is not None:
        story_row = await db.execute(select(Story.id).where(Story.id == story_id))
        if story_row.scalar_one_or_none() is None:
            raise HTTPException(status_code=400, detail="القصة المحددة غير موجودة.")
    playbook_key = _normalize_playbook_key(payload.playbook_key)
    checklist = _normalize_string_list(payload.checklist, max_items=30)
    if not checklist:
        checklist = _playbook_checklist(playbook_key)

    item = EventMemoItem(
        scope=payload.scope,
        title=_clean_title(payload.title),
        summary=_normalize_text(payload.summary),
        coverage_plan=_normalize_text(payload.coverage_plan),
        starts_at=starts_at,
        ends_at=ends_at,
        timezone=payload.timezone.strip(),
        country_code=_normalize_text(payload.country_code),
        is_all_day=payload.is_all_day,
        lead_time_hours=payload.lead_time_hours,
        priority=payload.priority,
        status=payload.status,
        readiness_status=readiness_status,
        source_url=_normalize_text(payload.source_url),
        tags=_normalize_tags(payload.tags),
        checklist=checklist,
        playbook_key=playbook_key,
        story_id=story_id,
        preparation_started_at=preparation_started_at,
        owner_user_id=owner_user_id,
        owner_username=owner_username,
        created_by_user_id=current_user.id,
        created_by_username=current_user.username,
        updated_by_user_id=current_user.id,
        updated_by_username=current_user.username,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    story_lookup = await _load_story_lookup(db, [item])
    return _as_response(item, now=datetime.utcnow(), story_lookup=story_lookup)


@router.patch("/{event_id:int}", response_model=EventMemoResponse)
async def update_event(
    event_id: int,
    payload: EventMemoUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _assert_write(current_user)
    await _ensure_events_table(db)
    item = await _load_event_or_404(db, event_id)

    data = payload.model_dump(exclude_unset=True)
    if not data:
        story_lookup = await _load_story_lookup(db, [item])
        return _as_response(item, now=datetime.utcnow(), story_lookup=story_lookup)

    if data.get("status") == "dismissed":
        _assert_manage(current_user)

    starts_at = _normalize_dt(data["starts_at"]) if "starts_at" in data else item.starts_at
    ends_at = _normalize_dt(data["ends_at"]) if "ends_at" in data else item.ends_at
    assert starts_at is not None
    _validate_dates(starts_at, ends_at)

    if "scope" in data:
        item.scope = data["scope"]
    if "title" in data:
        item.title = _clean_title(data["title"])
    if "summary" in data:
        item.summary = _normalize_text(data["summary"])
    if "coverage_plan" in data:
        item.coverage_plan = _normalize_text(data["coverage_plan"])
    if "starts_at" in data:
        item.starts_at = starts_at
    if "ends_at" in data:
        item.ends_at = ends_at
    if "timezone" in data:
        item.timezone = data["timezone"].strip()
    if "country_code" in data:
        item.country_code = _normalize_text(data["country_code"])
    if "is_all_day" in data:
        item.is_all_day = bool(data["is_all_day"])
    if "lead_time_hours" in data:
        item.lead_time_hours = int(data["lead_time_hours"])
    if "priority" in data:
        item.priority = int(data["priority"])
    if "status" in data:
        item.status = data["status"]
        if item.status == "covered":
            item.readiness_status = "covered"
            if item.preparation_started_at is None:
                item.preparation_started_at = datetime.utcnow()
    if "source_url" in data:
        item.source_url = _normalize_text(data["source_url"])
    if "tags" in data:
        item.tags = _normalize_tags(data["tags"])
    if "checklist" in data:
        item.checklist = _normalize_string_list(data["checklist"], max_items=30)
    if "playbook_key" in data:
        item.playbook_key = _normalize_playbook_key(data["playbook_key"])
        if not item.checklist:
            item.checklist = _playbook_checklist(item.playbook_key)
    if "owner_user_id" in data:
        owner_user_id, owner_username = await _resolve_owner(db, data["owner_user_id"])
        item.owner_user_id = owner_user_id
        item.owner_username = owner_username
    if "story_id" in data:
        if data["story_id"] is None:
            item.story_id = None
        else:
            story_row = await db.execute(select(Story.id).where(Story.id == data["story_id"]))
            if story_row.scalar_one_or_none() is None:
                raise HTTPException(status_code=400, detail="القصة المحددة غير موجودة.")
            item.story_id = int(data["story_id"])
    if "readiness_status" in data:
        item.readiness_status = data["readiness_status"]
        if item.readiness_status in {"prepared", "ready", "covered"} and item.preparation_started_at is None:
            item.preparation_started_at = datetime.utcnow()
        if item.readiness_status == "covered":
            item.status = "covered"
    if "preparation_started_at" in data:
        item.preparation_started_at = _normalize_dt(data["preparation_started_at"])

    item.updated_by_user_id = current_user.id
    item.updated_by_username = current_user.username
    item.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(item)
    story_lookup = await _load_story_lookup(db, [item])
    return _as_response(item, now=datetime.utcnow(), story_lookup=story_lookup)


@router.post("/{event_id:int}/story", response_model=EventMemoResponse)
async def link_event_story(
    event_id: int,
    payload: EventLinkStoryRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _assert_write(current_user)
    await _ensure_events_table(db)
    item = await _load_event_or_404(db, event_id)

    if payload.story_id is not None:
        story_row = await db.execute(select(Story).where(Story.id == payload.story_id))
        story = story_row.scalar_one_or_none()
        if not story:
            raise HTTPException(status_code=404, detail="القصة غير موجودة.")
        item.story_id = story.id
    elif payload.create_if_missing or item.story_id is None:
        story = await _create_story_from_event(
            db,
            item,
            actor=current_user,
            title=payload.title,
            summary=payload.summary,
            category=payload.category,
            geography=payload.geography,
        )
        item.story_id = story.id
    else:
        story_lookup = await _load_story_lookup(db, [item])
        return _as_response(item, now=datetime.utcnow(), story_lookup=story_lookup)

    item.updated_by_user_id = current_user.id
    item.updated_by_username = current_user.username
    item.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(item)
    story_lookup = await _load_story_lookup(db, [item])
    return _as_response(item, now=datetime.utcnow(), story_lookup=story_lookup)


@router.post("/{event_id:int}/automation/run", response_model=EventAutomationRunResponse)
async def run_event_automation(
    event_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _assert_write(current_user)
    await _ensure_events_table(db)
    item = await _load_event_or_404(db, event_id)

    now = datetime.utcnow()
    actions: list[str] = []
    story_created = False
    story_linked = False
    status_updated = False
    readiness_updated = False

    if item.story_id is None and item.starts_at <= now + timedelta(hours=24):
        story = await _create_story_from_event(db, item, actor=current_user)
        item.story_id = story.id
        story_created = True
        story_linked = True
        actions.append("create_story_t24")

    if item.status == "planned" and item.starts_at <= now + timedelta(hours=6):
        item.status = "monitoring"
        status_updated = True
        actions.append("set_monitoring_t6")

    if item.readiness_status in {"idea", "assigned"} and item.starts_at <= now + timedelta(hours=6):
        item.readiness_status = "prepared"
        if item.preparation_started_at is None:
            item.preparation_started_at = now
        readiness_updated = True
        actions.append("set_prepared_t6")

    if not item.checklist:
        item.checklist = _playbook_checklist(item.playbook_key)
        if item.checklist:
            readiness_updated = True
            actions.append("apply_playbook_checklist")

    item.updated_by_user_id = current_user.id
    item.updated_by_username = current_user.username
    item.updated_at = now
    await db.commit()

    return EventAutomationRunResponse(
        event_id=item.id,
        story_created=story_created,
        story_linked=story_linked,
        status_updated=status_updated,
        readiness_updated=readiness_updated,
        actions=actions,
    )


@router.delete("/{event_id:int}")
async def delete_event(
    event_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _assert_manage(current_user)
    await _ensure_events_table(db)
    item = await _load_event_or_404(db, event_id)
    await db.delete(item)
    await db.commit()
    return {"message": "تم حذف الحدث."}


@router.post("/import-db")
async def import_events_db(
    overwrite: bool = Query(default=False),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _assert_manage(current_user)
    await _ensure_events_table(db)
    if not EVENT_DB_PATH.exists():
        raise HTTPException(status_code=404, detail=f"ملف قاعدة الأحداث غير موجود: {EVENT_DB_PATH}")

    try:
        payload = json.loads(EVENT_DB_PATH.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"تعذر قراءة ملف قاعدة الأحداث: {exc}") from exc

    if not isinstance(payload, list):
        raise HTTPException(status_code=400, detail="ملف قاعدة الأحداث يجب أن يكون مصفوفة JSON.")

    created = 0
    updated = 0
    skipped = 0
    errors: list[dict] = []
    for idx, item in enumerate(payload, start=1):
        try:
            if not isinstance(item, dict):
                raise ValueError("record must be an object")
            scope = str(item.get("scope") or "").strip().lower()
            if scope not in {"national", "international", "religious"}:
                raise ValueError("invalid scope")
            title = _clean_title(str(item.get("title") or ""))
            starts_at = _parse_seed_datetime(str(item.get("starts_at") or ""))
            if starts_at is None:
                raise ValueError("missing starts_at")
            ends_at = _parse_seed_datetime(item.get("ends_at"))
            _validate_dates(starts_at, ends_at)

            existing_row = await db.execute(
                select(EventMemoItem).where(
                    EventMemoItem.scope == scope,
                    EventMemoItem.title == title,
                    EventMemoItem.starts_at == starts_at,
                )
            )
            existing = existing_row.scalar_one_or_none()
            record = {
                "scope": scope,
                "title": title,
                "summary": _normalize_text(item.get("summary")),
                "coverage_plan": _normalize_text(item.get("coverage_plan")),
                "starts_at": starts_at,
                "ends_at": ends_at,
                "timezone": str(item.get("timezone") or "Africa/Algiers").strip() or "Africa/Algiers",
                "country_code": _normalize_text(item.get("country_code")),
                "is_all_day": bool(item.get("is_all_day", True)),
                "lead_time_hours": int(item.get("lead_time_hours", 24)),
                "priority": int(item.get("priority", 3)),
                "status": str(item.get("status") or "planned").strip().lower() or "planned",
                "readiness_status": str(item.get("readiness_status") or "idea").strip().lower() or "idea",
                "source_url": _normalize_text(item.get("source_url")),
                "tags": _normalize_tags(item.get("tags") if isinstance(item.get("tags"), list) else []),
                "checklist": _normalize_string_list(item.get("checklist") if isinstance(item.get("checklist"), list) else [], max_items=30),
                "playbook_key": _normalize_playbook_key(item.get("playbook_key")),
            }
            if not record["checklist"]:
                record["checklist"] = _playbook_checklist(record["playbook_key"])
            if record["status"] not in {"planned", "monitoring", "covered", "dismissed"}:
                record["status"] = "planned"
            if record["readiness_status"] not in READINESS_STATES:
                record["readiness_status"] = "idea"
            if record["status"] == "covered":
                record["readiness_status"] = "covered"
            record["lead_time_hours"] = max(1, min(336, record["lead_time_hours"]))
            record["priority"] = max(1, min(5, record["priority"]))
            prep_started_raw = _parse_seed_datetime(item.get("preparation_started_at"))
            if prep_started_raw is None and record["readiness_status"] in {"prepared", "ready", "covered"}:
                prep_started_raw = datetime.utcnow()
            record["preparation_started_at"] = prep_started_raw

            if existing is None:
                created += 1
                db.add(
                    EventMemoItem(
                        **record,
                        created_by_user_id=current_user.id,
                        created_by_username=current_user.username,
                        updated_by_user_id=current_user.id,
                        updated_by_username=current_user.username,
                    )
                )
                continue

            if not overwrite:
                skipped += 1
                continue

            for key, value in record.items():
                setattr(existing, key, value)
            existing.updated_by_user_id = current_user.id
            existing.updated_by_username = current_user.username
            existing.updated_at = datetime.utcnow()
            updated += 1
        except Exception as exc:  # noqa: BLE001
            errors.append({"index": idx, "error": str(exc)})

    await db.commit()
    return {
        "message": "تم استيراد ملف قاعدة الأحداث.",
        "file": str(EVENT_DB_PATH),
        "total_records": len(payload),
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "errors_count": len(errors),
        "errors": errors[:50],
    }
