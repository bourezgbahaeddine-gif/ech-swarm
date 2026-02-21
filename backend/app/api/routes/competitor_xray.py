"""Competitor X-Ray routes."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.auth import get_current_user
from app.core.database import async_session, get_db
from app.models.user import User, UserRole
from app.schemas.competitor_xray import (
    CompetitorXrayBriefRequest,
    CompetitorXrayBriefResponse,
    CompetitorXrayItemResponse,
    CompetitorXrayRunRequest,
    CompetitorXrayRunResponse,
    CompetitorXrayRunStatusResponse,
    CompetitorXraySourceCreate,
    CompetitorXraySourceResponse,
    CompetitorXraySourceUpdate,
)
from app.services.competitor_xray_service import competitor_xray_service

router = APIRouter(prefix="/competitor-xray", tags=["Competitor X-Ray"])

RUN_ALLOWED = {
    UserRole.journalist,
    UserRole.editor_chief,
    UserRole.director,
    UserRole.social_media,
    UserRole.print_editor,
}
VIEW_ALLOWED = RUN_ALLOWED
MANAGE_ALLOWED = {UserRole.editor_chief, UserRole.director}


def _require_run(user: User) -> None:
    if user.role not in RUN_ALLOWED:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Competitor X-Ray run is not available for your role")


def _require_view(user: User) -> None:
    if user.role not in VIEW_ALLOWED:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")


def _require_manage(user: User) -> None:
    if user.role not in MANAGE_ALLOWED:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Source management is available for chief editor/director only")


@router.post("/sources/seed")
async def seed_sources(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_manage(current_user)
    return await competitor_xray_service.seed_default_sources(db)


@router.get("/sources", response_model=list[CompetitorXraySourceResponse])
async def list_sources(
    enabled_only: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_view(current_user)
    rows = await competitor_xray_service.list_sources(db, enabled_only=enabled_only)
    return [
        CompetitorXraySourceResponse(
            id=s.id,
            name=s.name,
            feed_url=s.feed_url,
            domain=s.domain,
            language=s.language,
            weight=s.weight,
            enabled=bool(s.enabled),
            created_at=s.created_at,
            updated_at=s.updated_at,
        )
        for s in rows
    ]


@router.post("/sources", response_model=CompetitorXraySourceResponse, status_code=status.HTTP_201_CREATED)
async def create_source(
    payload: CompetitorXraySourceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_manage(current_user)
    source = await competitor_xray_service.create_source(
        db,
        name=payload.name,
        feed_url=payload.feed_url,
        domain=payload.domain,
        language=payload.language,
        weight=payload.weight,
        enabled=payload.enabled,
    )
    return CompetitorXraySourceResponse(
        id=source.id,
        name=source.name,
        feed_url=source.feed_url,
        domain=source.domain,
        language=source.language,
        weight=source.weight,
        enabled=bool(source.enabled),
        created_at=source.created_at,
        updated_at=source.updated_at,
    )


@router.patch("/sources/{source_id}", response_model=CompetitorXraySourceResponse)
async def update_source(
    source_id: int,
    payload: CompetitorXraySourceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_manage(current_user)
    source = await competitor_xray_service.update_source(
        db,
        source_id,
        name=payload.name,
        language=payload.language,
        weight=payload.weight,
        enabled=payload.enabled,
    )
    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")
    return CompetitorXraySourceResponse(
        id=source.id,
        name=source.name,
        feed_url=source.feed_url,
        domain=source.domain,
        language=source.language,
        weight=source.weight,
        enabled=bool(source.enabled),
        created_at=source.created_at,
        updated_at=source.updated_at,
    )


@router.post("/run", response_model=CompetitorXrayRunResponse, status_code=status.HTTP_202_ACCEPTED)
async def run_xray(
    payload: CompetitorXrayRunRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_run(current_user)
    run = await competitor_xray_service.create_run(
        db,
        limit_per_source=payload.limit_per_source,
        hours_window=payload.hours_window,
        actor=current_user,
        idempotency_key=payload.idempotency_key,
    )
    if run.status in {"queued", "running"}:
        await competitor_xray_service.start_run_task(
            run.run_id,
            limit_per_source=payload.limit_per_source,
            hours_window=payload.hours_window,
        )
    return CompetitorXrayRunResponse(run_id=run.run_id, status=run.status, created_at=run.created_at)


@router.get("/runs/{run_id}", response_model=CompetitorXrayRunStatusResponse)
async def run_status(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_view(current_user)
    row = await competitor_xray_service.get_run_status(db, run_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return CompetitorXrayRunStatusResponse(
        run_id=row.run_id,
        status=row.status,
        total_scanned=row.total_scanned,
        total_gaps=row.total_gaps,
        created_at=row.created_at,
        finished_at=row.finished_at,
        error=row.error,
    )


@router.get("/items/latest", response_model=list[CompetitorXrayItemResponse])
async def latest_items(
    limit: int = Query(20, ge=1, le=100),
    status_filter: str | None = Query(default=None),
    q: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_view(current_user)
    items = await competitor_xray_service.get_items_latest(db, limit=limit, status_filter=status_filter, query=q)
    return [
        CompetitorXrayItemResponse(
            id=i.id,
            run_id=i.run_id,
            source_id=i.source_id,
            competitor_title=i.competitor_title,
            competitor_url=i.competitor_url,
            competitor_summary=i.competitor_summary,
            published_at=i.published_at,
            priority_score=i.priority_score,
            status=i.status,
            angle_title=i.angle_title,
            angle_rationale=i.angle_rationale,
            angle_questions_json=i.angle_questions_json or [],
            starter_sources_json=i.starter_sources_json or [],
            matched_article_id=i.matched_article_id,
            created_at=i.created_at,
            updated_at=i.updated_at,
        )
        for i in items
    ]


@router.post("/items/{item_id}/mark-used")
async def mark_item_used(
    item_id: int,
    status_value: str = Query("used"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_run(current_user)
    if status_value not in {"used", "ignored", "new"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid status")
    item = await competitor_xray_service.mark_item_status(db, item_id, status_value=status_value)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    return {"id": item.id, "status": item.status}


@router.post("/brief", response_model=CompetitorXrayBriefResponse)
async def build_brief(
    payload: CompetitorXrayBriefRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_run(current_user)
    brief = await competitor_xray_service.build_brief(db, payload.item_id, tone=payload.tone)
    if not brief:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    return CompetitorXrayBriefResponse.model_validate(brief)


@router.get("/live")
async def live_events(
    run_id: str = Query(..., min_length=8, max_length=64),
    poll_ms: int = Query(1200, ge=500, le=5000),
    current_user: User = Depends(get_current_user),
):
    _require_view(current_user)

    async def _stream():
        last_id = 0
        keep_alive_every = 15
        counter = 0
        while True:
            async with async_session() as db:
                events = await competitor_xray_service.get_events_since(db, run_id=run_id, last_id=last_id, limit=100)
                for ev in events:
                    last_id = ev.id
                    payload = {
                        "id": ev.id,
                        "run_id": ev.run_id,
                        "node": ev.node,
                        "event_type": ev.event_type,
                        "payload": ev.payload_json or {},
                        "ts": ev.ts.isoformat(),
                    }
                    yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

                run = await competitor_xray_service.get_run_status(db, run_id)
                if run and run.status in {"completed", "failed"} and not events:
                    terminal = {
                        "id": last_id,
                        "run_id": run_id,
                        "node": "runner",
                        "event_type": "terminal",
                        "payload": {"status": run.status, "error": run.error},
                        "ts": datetime.utcnow().isoformat(),
                    }
                    yield f"data: {json.dumps(terminal, ensure_ascii=False)}\n\n"
                    break

            counter += 1
            if counter % keep_alive_every == 0:
                yield "event: ping\ndata: {}\n\n"
            await asyncio.sleep(poll_ms / 1000)

    return StreamingResponse(_stream(), media_type="text/event-stream")
