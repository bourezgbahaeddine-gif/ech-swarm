"""MSI Monitor routes."""

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
from app.msi.service import msi_monitor_service
from app.schemas.msi import (
    MsiProfileInfo,
    MsiReportResponse,
    MsiRunRequest,
    MsiRunResponse,
    MsiRunStatusResponse,
    MsiTimeseriesPoint,
    MsiTimeseriesResponse,
    MsiTopEntityItem,
    MsiTopResponse,
    MsiWatchlistCreateRequest,
    MsiWatchlistItem,
    MsiWatchlistUpdateRequest,
)

router = APIRouter(prefix="/msi", tags=["MSI"])


RUN_ALLOWED = {UserRole.journalist, UserRole.editor_chief, UserRole.director}
VIEW_ALLOWED = {UserRole.journalist, UserRole.editor_chief, UserRole.director, UserRole.social_media, UserRole.print_editor}
WATCHLIST_ALLOWED = {UserRole.director, UserRole.editor_chief}


def _require_view(user: User) -> None:
    if user.role not in VIEW_ALLOWED:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="غير مصرح")


def _require_run(user: User) -> None:
    if user.role not in RUN_ALLOWED:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="تشغيل MSI متاح للمحرر/رئيس التحرير/المدير فقط")


def _require_watchlist_manage(user: User) -> None:
    if user.role not in WATCHLIST_ALLOWED:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="إدارة قائمة المراقبة متاحة للمدير/رئيس التحرير فقط")


@router.get("/profiles", response_model=list[MsiProfileInfo])
async def get_profiles(current_user: User = Depends(get_current_user)):
    _require_view(current_user)
    profiles = await msi_monitor_service.list_profiles()
    return [MsiProfileInfo(**p) for p in profiles]


@router.post("/run", response_model=MsiRunResponse, status_code=status.HTTP_202_ACCEPTED)
async def run_msi(
    payload: MsiRunRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_run(current_user)
    run = await msi_monitor_service.create_run(
        db,
        profile_id=payload.profile_id,
        entity=payload.entity,
        mode=payload.mode,
        actor=current_user,
        start=payload.start,
        end=payload.end,
    )
    await msi_monitor_service.start_run_task(run.run_id)
    return MsiRunResponse(
        run_id=run.run_id,
        status=run.status,
        profile_id=run.profile_id,
        entity=run.entity,
        mode=run.mode,
        start=run.period_start,
        end=run.period_end,
    )


@router.get("/runs/{run_id}", response_model=MsiRunStatusResponse)
async def get_run_status(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_view(current_user)
    run = await msi_monitor_service.get_run_status(db, run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run غير موجود")
    return MsiRunStatusResponse(
        run_id=run.run_id,
        status=run.status,
        error=run.error,
        created_at=run.created_at,
        finished_at=run.finished_at,
    )


@router.get("/report", response_model=MsiReportResponse)
async def get_report(
    run_id: str = Query(..., min_length=8, max_length=64),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_view(current_user)
    report = await msi_monitor_service.get_report(db, run_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="التقرير غير متاح بعد")
    return MsiReportResponse.model_validate(report)


@router.get("/timeseries", response_model=MsiTimeseriesResponse)
async def get_timeseries(
    profile_id: str = Query(..., min_length=2, max_length=64),
    entity: str = Query(..., min_length=2, max_length=255),
    mode: str = Query("daily", pattern="^(daily|weekly)$"),
    limit: int = Query(30, ge=1, le=180),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_view(current_user)
    points = await msi_monitor_service.get_timeseries(db, profile_id=profile_id, entity=entity, mode=mode, limit=limit)
    return MsiTimeseriesResponse(
        profile_id=profile_id,
        entity=entity,
        mode=mode,
        points=[
            MsiTimeseriesPoint(ts=p.period_end, msi=p.msi, level=p.level, components=p.components_json or {})
            for p in points
        ],
    )


@router.get("/top", response_model=MsiTopResponse)
async def get_top(
    mode: str = Query("daily", pattern="^(daily|weekly)$"),
    limit: int = Query(5, ge=1, le=30),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_view(current_user)
    rows = await msi_monitor_service.get_top_entities(db, mode=mode, limit=limit)
    return MsiTopResponse(
        mode=mode,
        items=[
            MsiTopEntityItem(
                profile_id=row.profile_id,
                entity=row.entity,
                mode=row.mode,
                msi=row.msi,
                level=row.level,
                period_end=row.period_end,
            )
            for row in rows
        ],
    )


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
                events = await msi_monitor_service.get_events_since(db, run_id=run_id, last_id=last_id, limit=100)
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

                run = await msi_monitor_service.get_run_status(db, run_id)
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


@router.get("/watchlist", response_model=list[MsiWatchlistItem])
async def get_watchlist(
    enabled_only: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_view(current_user)
    rows = await msi_monitor_service.list_watchlist(db, enabled_only=enabled_only)
    return [MsiWatchlistItem.model_validate(r) for r in rows]


@router.post("/watchlist", response_model=MsiWatchlistItem, status_code=status.HTTP_201_CREATED)
async def add_watchlist(
    payload: MsiWatchlistCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_watchlist_manage(current_user)
    item = await msi_monitor_service.create_watchlist_item(
        db,
        profile_id=payload.profile_id,
        entity=payload.entity,
        run_daily=payload.run_daily,
        run_weekly=payload.run_weekly,
        enabled=payload.enabled,
        actor=current_user,
    )
    return MsiWatchlistItem.model_validate(item)


@router.patch("/watchlist/{item_id}", response_model=MsiWatchlistItem)
async def patch_watchlist(
    item_id: int,
    payload: MsiWatchlistUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_watchlist_manage(current_user)
    item = await msi_monitor_service.update_watchlist_item(
        db,
        item_id,
        run_daily=payload.run_daily,
        run_weekly=payload.run_weekly,
        enabled=payload.enabled,
    )
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="العنصر غير موجود")
    return MsiWatchlistItem.model_validate(item)


@router.delete("/watchlist/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_watchlist(
    item_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_watchlist_manage(current_user)
    ok = await msi_monitor_service.delete_watchlist_item(db, item_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="العنصر غير موجود")
    return None
