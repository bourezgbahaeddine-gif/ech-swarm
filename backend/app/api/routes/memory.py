"""
Project Memory API.
Shared memory for operational decisions, knowledge, and session lessons.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.auth import get_current_user
from app.core.database import get_db
from app.models import Article, ProjectMemoryEvent, ProjectMemoryItem
from app.models.user import User, UserRole
from app.schemas.memory import (
    MemoryCreateRequest,
    MemoryEventResponse,
    MemoryItemResponse,
    MemoryListResponse,
    MemoryOverviewResponse,
    MemoryUpdateRequest,
)
from app.services.project_memory_service import project_memory_service

router = APIRouter(prefix="/memory", tags=["Project Memory"])


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


class MemoryUseRequest(BaseModel):
    note: str | None = None


def _assert_read(user: User) -> None:
    if user.role not in READ_ROLES:
        raise HTTPException(status_code=403, detail="غير مسموح لك بالوصول إلى ذاكرة المشروع.")


def _assert_write(user: User) -> None:
    if user.role not in WRITE_ROLES:
        raise HTTPException(status_code=403, detail="غير مسموح لك بإضافة أو تعديل ذاكرة المشروع.")


def _assert_manage(user: User) -> None:
    if user.role not in MANAGE_ROLES:
        raise HTTPException(status_code=403, detail="غير مسموح لك بإدارة حالة ذاكرة المشروع.")


async def _ensure_memory_tables(db: AsyncSession) -> None:
    checks = await db.execute(
        text(
            """
            SELECT
                to_regclass('public.project_memory_items') AS items_tbl,
                to_regclass('public.project_memory_events') AS events_tbl
            """
        )
    )
    row = checks.mappings().first()
    if not row or not row["items_tbl"] or not row["events_tbl"]:
        raise HTTPException(
            status_code=503,
            detail="جداول ذاكرة المشروع غير جاهزة. نفّذ ترحيل قاعدة البيانات: alembic upgrade head",
        )


@router.get("/overview", response_model=MemoryOverviewResponse)
async def overview(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _assert_read(current_user)
    await _ensure_memory_tables(db)
    data = await project_memory_service.overview(db)
    return MemoryOverviewResponse(**data)


@router.get("/items", response_model=MemoryListResponse)
async def list_items(
    q: str | None = Query(default=None),
    memory_type: str | None = Query(default=None, pattern="^(operational|knowledge|session)$"),
    status_filter: str = Query(default="active", alias="status", pattern="^(active|archived)$"),
    tag: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _assert_read(current_user)
    await _ensure_memory_tables(db)
    items, total = await project_memory_service.search_items(
        db,
        q=q,
        memory_type=memory_type,
        status=status_filter,
        tag=tag,
        page=page,
        per_page=per_page,
    )
    pages = (total + per_page - 1) // per_page
    return MemoryListResponse(
        items=[MemoryItemResponse.model_validate(i) for i in items],
        total=total,
        page=page,
        per_page=per_page,
        pages=pages,
    )


@router.post("/items", response_model=MemoryItemResponse, status_code=status.HTTP_201_CREATED)
async def create_item(
    payload: MemoryCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _assert_write(current_user)
    await _ensure_memory_tables(db)
    if payload.article_id is not None:
        article_exists = await db.execute(select(Article.id).where(Article.id == payload.article_id))
        if article_exists.scalar_one_or_none() is None:
            raise HTTPException(status_code=404, detail="المقال المرتبط غير موجود.")

    item = await project_memory_service.create_item(
        db,
        actor=current_user,
        memory_type=payload.memory_type,
        title=payload.title,
        content=payload.content,
        tags=payload.tags,
        source_type=payload.source_type,
        source_ref=payload.source_ref,
        article_id=payload.article_id,
        importance=payload.importance,
    )
    await db.commit()
    await db.refresh(item)
    return MemoryItemResponse.model_validate(item)


@router.get("/items/{item_id}", response_model=MemoryItemResponse)
async def get_item(
    item_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _assert_read(current_user)
    await _ensure_memory_tables(db)
    row = await db.execute(select(ProjectMemoryItem).where(ProjectMemoryItem.id == item_id))
    item = row.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="عنصر الذاكرة غير موجود.")
    return MemoryItemResponse.model_validate(item)


@router.patch("/items/{item_id}", response_model=MemoryItemResponse)
async def update_item(
    item_id: int,
    payload: MemoryUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _assert_write(current_user)
    await _ensure_memory_tables(db)
    row = await db.execute(select(ProjectMemoryItem).where(ProjectMemoryItem.id == item_id))
    item = row.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="عنصر الذاكرة غير موجود.")

    data = payload.model_dump(exclude_unset=True)
    if not data:
        return MemoryItemResponse.model_validate(item)

    if "status" in data and data["status"] == "archived":
        _assert_manage(current_user)
    if "status" in data and data["status"] == "active" and item.status == "archived":
        _assert_manage(current_user)

    if "article_id" in data and data["article_id"] is not None:
        article_exists = await db.execute(select(Article.id).where(Article.id == data["article_id"]))
        if article_exists.scalar_one_or_none() is None:
            raise HTTPException(status_code=404, detail="المقال المرتبط غير موجود.")

    if "memory_type" in data:
        item.memory_type = data["memory_type"]
    if "title" in data:
        item.title = project_memory_service._normalize_text(data["title"])[:512]
    if "content" in data:
        item.content = project_memory_service._normalize_text(data["content"])
    if "tags" in data:
        item.tags = project_memory_service._normalize_tags(data["tags"])
    if "source_type" in data:
        item.source_type = project_memory_service._normalize_text(data["source_type"])[:64] if data["source_type"] else None
    if "source_ref" in data:
        item.source_ref = project_memory_service._normalize_text(data["source_ref"])[:512] if data["source_ref"] else None
    if "article_id" in data:
        item.article_id = data["article_id"]
    if "importance" in data:
        item.importance = data["importance"]
    if "status" in data:
        item.status = data["status"]

    item.updated_by_user_id = current_user.id
    item.updated_by_username = current_user.username
    await db.flush()
    await project_memory_service.log_event(
        db,
        memory_id=item.id,
        event_type="updated",
        actor=current_user,
        note="updated fields",
    )
    await db.commit()
    await db.refresh(item)
    return MemoryItemResponse.model_validate(item)


@router.post("/items/{item_id}/use", response_model=MemoryEventResponse)
async def mark_item_used(
    item_id: int,
    payload: MemoryUseRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _assert_read(current_user)
    await _ensure_memory_tables(db)
    row = await db.execute(select(ProjectMemoryItem).where(ProjectMemoryItem.id == item_id))
    item = row.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="عنصر الذاكرة غير موجود.")
    await project_memory_service.log_event(
        db,
        memory_id=item.id,
        event_type="used",
        actor=current_user,
        note=payload.note,
    )
    await db.commit()
    event_row = await db.execute(
        select(ProjectMemoryEvent)
        .where(ProjectMemoryEvent.memory_id == item.id, ProjectMemoryEvent.event_type == "used")
        .order_by(ProjectMemoryEvent.id.desc())
        .limit(1)
    )
    event = event_row.scalar_one()
    return MemoryEventResponse.model_validate(event)


@router.get("/items/{item_id}/events", response_model=list[MemoryEventResponse])
async def get_item_events(
    item_id: int,
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _assert_read(current_user)
    await _ensure_memory_tables(db)
    row = await db.execute(select(ProjectMemoryItem.id).where(ProjectMemoryItem.id == item_id))
    if row.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="عنصر الذاكرة غير موجود.")

    rows = await db.execute(
        select(ProjectMemoryEvent)
        .where(ProjectMemoryEvent.memory_id == item_id)
        .order_by(ProjectMemoryEvent.created_at.desc(), ProjectMemoryEvent.id.desc())
        .limit(limit)
    )
    return [MemoryEventResponse.model_validate(ev) for ev in rows.scalars().all()]
