"""MSI Monitor routes."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.auth import get_current_user
from app.core.correlation import get_correlation_id, get_request_id
from app.core.database import async_session, get_db
from app.models.user import User, UserRole
from app.msi.profiles import load_profile
from app.msi.service import msi_monitor_service
from app.services.job_queue_service import job_queue_service
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


RUN_ALLOWED = {UserRole.director}
VIEW_ALLOWED = {UserRole.director}
WATCHLIST_ALLOWED = {UserRole.director}


def _require_view(user: User) -> None:
    if user.role not in VIEW_ALLOWED:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="MSI is available for director only")


def _require_run(user: User) -> None:
    if user.role not in RUN_ALLOWED:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="MSI run is available for director only")


def _require_watchlist_manage(user: User) -> None:
    if user.role not in WATCHLIST_ALLOWED:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="MSI watchlist management is available for director only")


def _map_watchlist_item(item) -> MsiWatchlistItem:
    return MsiWatchlistItem(
        id=item.id,
        profile_id=item.profile_id,
        entity=item.entity,
        enabled=item.enabled,
        run_daily=item.run_daily,
        run_weekly=item.run_weekly,
        aliases=item.aliases_json or [],
        created_by_username=item.created_by_username,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


@router.get("/profiles", response_model=list[MsiProfileInfo])
async def get_profiles(current_user: User = Depends(get_current_user)):
    _require_view(current_user)
    profiles = await msi_monitor_service.list_profiles()
    return [MsiProfileInfo(**p) for p in profiles]


@router.post("/run", response_model=MsiRunResponse, status_code=status.HTTP_202_ACCEPTED)
async def run_msi(
    payload: MsiRunRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_run(current_user)
    try:
        load_profile(payload.profile_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ملف Profile غير موجود") from exc

    run = await msi_monitor_service.create_run(
        db,
        profile_id=payload.profile_id,
        entity=payload.entity,
        mode=payload.mode,
        actor=current_user,
        start=payload.start,
        end=payload.end,
    )
    allowed, depth, limit_depth = await job_queue_service.check_backpressure("ai_msi")
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"MSI queue is busy ({depth}/{limit_depth}). Retry in a moment.",
        )
    job = await job_queue_service.create_job(
        db,
        job_type="msi_run",
        queue_name="ai_msi",
        payload={"run_id": run.run_id},
        entity_id=run.run_id,
        request_id=request.headers.get("x-request-id") or get_request_id(),
        correlation_id=request.headers.get("x-correlation-id") or get_correlation_id(),
        actor_user_id=current_user.id,
        actor_username=current_user.username,
    )
    try:
        await job_queue_service.enqueue_by_job_type(job_type="msi_run", job_id=str(job.id))
    except Exception as exc:  # noqa: BLE001
        await job_queue_service.mark_failed(db, job, f"queue_unavailable:{exc}")
        run.status = "failed"
        run.error = f"queue_unavailable:{exc}"[:2000]
        run.finished_at = datetime.utcnow()
        await db.commit()
        return MsiRunResponse(
            run_id=run.run_id,
            status="failed",
            profile_id=run.profile_id,
            entity=run.entity,
            mode=run.mode,
            start=run.period_start,
            end=run.period_end,
            job_id=str(job.id),
        )
    return MsiRunResponse(
        run_id=run.run_id,
        status=run.status,
        profile_id=run.profile_id,
        entity=run.entity,
        mode=run.mode,
        start=run.period_start,
        end=run.period_end,
        job_id=str(job.id),
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
    return [_map_watchlist_item(r) for r in rows]


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
        aliases=payload.aliases,
        actor=current_user,
    )
    return _map_watchlist_item(item)


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
        aliases=payload.aliases,
    )
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="العنصر غير موجود")
    return _map_watchlist_item(item)


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


@router.post("/watchlist/seed", response_model=dict)
async def seed_watchlist(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_watchlist_manage(current_user)
    return await msi_monitor_service.seed_default_watchlist(db, actor=current_user)
