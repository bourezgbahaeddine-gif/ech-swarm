"""Audience simulator routes (/sim)."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.auth import get_current_user
from app.core.database import async_session, get_db
from app.models.user import User, UserRole
from app.schemas.simulator import (
    SimHistoryItem,
    SimHistoryResponse,
    SimResultResponse,
    SimRunRequest,
    SimRunResponse,
    SimRunStatusResponse,
)
from app.simulator.service import audience_simulation_service

router = APIRouter(prefix="/sim", tags=["Audience Simulator"])

RUN_ALLOWED = {UserRole.journalist, UserRole.editor_chief, UserRole.director}
VIEW_ALLOWED = {
    UserRole.journalist,
    UserRole.editor_chief,
    UserRole.director,
    UserRole.social_media,
    UserRole.print_editor,
}


def _require_run(user: User) -> None:
    if user.role not in RUN_ALLOWED:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="تشغيل المحاكي متاح للمحرر ورئيس التحرير والمدير فقط")


def _require_view(user: User) -> None:
    if user.role not in VIEW_ALLOWED:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="غير مصرح")


@router.post("/run", response_model=SimRunResponse, status_code=status.HTTP_202_ACCEPTED)
async def run_simulation(
    payload: SimRunRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_run(current_user)
    try:
        run = await audience_simulation_service.create_run(
            db,
            headline=payload.headline,
            body_excerpt=payload.excerpt,
            platform=payload.platform,
            mode=payload.mode,
            actor=current_user,
            article_id=payload.article_id,
            draft_id=payload.draft_id,
            idempotency_key=payload.idempotency_key,
        )
    except SQLAlchemyError as exc:
        text = str(exc).lower()
        if "sim_runs" in text and ("does not exist" in text or "undefinedtable" in text):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="جداول محاكي الجمهور غير موجودة. نفّذ migration: alembic upgrade head",
            ) from exc
        raise
    if run.status in {"queued", "running"}:
        await audience_simulation_service.start_run_task(run.run_id)
    return SimRunResponse(
        run_id=run.run_id,
        status=run.status,
        platform=run.platform,
        mode=run.mode,
        headline=run.headline,
    )


@router.get("/runs/{run_id}", response_model=SimRunStatusResponse)
async def sim_run_status(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_view(current_user)
    row = await audience_simulation_service.get_run_status(db, run_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run غير موجود")
    return SimRunStatusResponse(
        run_id=row.run_id,
        status=row.status,
        error=row.error,
        created_at=row.created_at,
        finished_at=row.finished_at,
    )


@router.get("/result", response_model=SimResultResponse)
async def sim_result(
    run_id: str = Query(..., min_length=8, max_length=64),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_view(current_user)
    result = await audience_simulation_service.get_result(db, run_id)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="النتيجة غير متاحة بعد")
    return SimResultResponse.model_validate(result)


@router.get("/history", response_model=SimHistoryResponse)
async def sim_history(
    article_id: int | None = Query(default=None),
    draft_id: int | None = Query(default=None),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_view(current_user)
    rows = await audience_simulation_service.get_history(db, article_id=article_id, draft_id=draft_id, limit=limit)
    return SimHistoryResponse(items=[SimHistoryItem.model_validate(r) for r in rows], total=len(rows))


@router.get("/live")
async def sim_live_events(
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
                events = await audience_simulation_service.get_events_since(db, run_id=run_id, last_id=last_id, limit=100)
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

                run = await audience_simulation_service.get_run_status(db, run_id)
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
