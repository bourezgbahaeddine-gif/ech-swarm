"""
Events memo board API.
Planning board for upcoming coverage-worthy events.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.auth import get_current_user
from app.core.database import get_db
from app.models import EventMemoItem
from app.models.user import User, UserRole
from app.schemas.events import (
    EventMemoCreateRequest,
    EventMemoListResponse,
    EventMemoOverviewResponse,
    EventMemoResponse,
    EventMemoUpdateRequest,
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
EVENT_DB_PATH = Path(__file__).resolve().parents[2] / "data" / "events" / "event_db.json"


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


def _as_response(item: EventMemoItem, now: datetime | None = None) -> EventMemoResponse:
    now = now or datetime.utcnow()
    prep_starts_at = item.starts_at - timedelta(hours=max(1, int(item.lead_time_hours or 24)))
    is_due_soon = item.status in ACTIVE_STATUSES and prep_starts_at <= now
    is_overdue = item.status in ACTIVE_STATUSES and item.starts_at < now
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
        source_url=item.source_url,
        tags=item.tags or [],
        prep_starts_at=prep_starts_at,
        is_due_soon=is_due_soon,
        is_overdue=is_overdue,
        created_by_user_id=item.created_by_user_id,
        created_by_username=item.created_by_username,
        updated_by_user_id=item.updated_by_user_id,
        updated_by_username=item.updated_by_username,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


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

    return EventMemoOverviewResponse(
        window_days=window_days,
        total=total,
        upcoming_24h=upcoming_24h,
        upcoming_7d=upcoming_7d,
        overdue=overdue,
        by_scope=by_scope,
        by_status=by_status,
    )


@router.get("/", response_model=EventMemoListResponse)
async def list_events(
    q: str | None = Query(default=None),
    scope: str | None = Query(default=None, pattern="^(national|international|religious)$"),
    status_filter: str | None = Query(default=None, alias="status", pattern="^(planned|monitoring|covered|dismissed)$"),
    only_active: bool = Query(default=True),
    from_at: datetime | None = Query(default=None),
    to_at: datetime | None = Query(default=None),
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
        filters.append(or_(EventMemoItem.title.ilike(like), EventMemoItem.summary.ilike(like)))
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
    items = [_as_response(item, now=now) for item in rows.scalars().all()]
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
            EventMemoItem.starts_at <= window_end,
        )
        .order_by(EventMemoItem.starts_at.asc(), EventMemoItem.priority.desc())
        .limit(limit)
    )
    return [_as_response(item, now=now) for item in rows.scalars().all()]


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
        source_url=_normalize_text(payload.source_url),
        tags=_normalize_tags(payload.tags),
        created_by_user_id=current_user.id,
        created_by_username=current_user.username,
        updated_by_user_id=current_user.id,
        updated_by_username=current_user.username,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return _as_response(item)


@router.patch("/{event_id:int}", response_model=EventMemoResponse)
async def update_event(
    event_id: int,
    payload: EventMemoUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _assert_write(current_user)
    await _ensure_events_table(db)
    row = await db.execute(select(EventMemoItem).where(EventMemoItem.id == event_id))
    item = row.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="الحدث غير موجود.")

    data = payload.model_dump(exclude_unset=True)
    if not data:
        return _as_response(item)

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
    if "source_url" in data:
        item.source_url = _normalize_text(data["source_url"])
    if "tags" in data:
        item.tags = _normalize_tags(data["tags"])

    item.updated_by_user_id = current_user.id
    item.updated_by_username = current_user.username
    item.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(item)
    return _as_response(item)


@router.delete("/{event_id:int}")
async def delete_event(
    event_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _assert_manage(current_user)
    await _ensure_events_table(db)
    row = await db.execute(select(EventMemoItem).where(EventMemoItem.id == event_id))
    item = row.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="الحدث غير موجود.")
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
                "source_url": _normalize_text(item.get("source_url")),
                "tags": _normalize_tags(item.get("tags") if isinstance(item.get("tags"), list) else []),
            }
            if record["status"] not in {"planned", "monitoring", "covered", "dismissed"}:
                record["status"] = "planned"
            record["lead_time_hours"] = max(1, min(336, record["lead_time_hours"]))
            record["priority"] = max(1, min(5, record["priority"]))

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
