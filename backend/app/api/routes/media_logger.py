"""Media Logger routes (/media-logger)."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.auth import get_current_user
from app.core.database import async_session, get_db
from app.models.user import User, UserRole
from app.schemas.media_logger import (
    MediaLoggerAskRequest,
    MediaLoggerAskResponse,
    MediaLoggerResultResponse,
    MediaLoggerRunFromUrlRequest,
    MediaLoggerRunResponse,
    MediaLoggerRunStatusResponse,
)
from app.services.media_logger_service import media_logger_service

router = APIRouter(prefix="/media-logger", tags=["Media Logger"])

RUN_ALLOWED = {
    UserRole.journalist,
    UserRole.editor_chief,
    UserRole.director,
    UserRole.social_media,
    UserRole.print_editor,
}
VIEW_ALLOWED = RUN_ALLOWED


def _require_run(user: User) -> None:
    if user.role not in RUN_ALLOWED:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Media Logger is not available for your role")


def _require_view(user: User) -> None:
    if user.role not in VIEW_ALLOWED:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")


@router.post("/run/url", response_model=MediaLoggerRunResponse, status_code=status.HTTP_202_ACCEPTED)
async def run_from_url(
    payload: MediaLoggerRunFromUrlRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_run(current_user)
    try:
        run = await media_logger_service.create_run_from_url(
            db,
            media_url=payload.media_url,
            language_hint=payload.language_hint,
            actor=current_user,
            idempotency_key=payload.idempotency_key,
        )
    except SQLAlchemyError as exc:
        text = str(exc).lower()
        if "media_logger_runs" in text and ("does not exist" in text or "undefinedtable" in text):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Media Logger tables are missing. Run migration: alembic upgrade head",
            ) from exc
        raise

    if run.status in {"queued", "running"}:
        await media_logger_service.start_run_task(run.run_id)
    return MediaLoggerRunResponse(
        run_id=run.run_id,
        status=run.status,
        source_type=run.source_type,
        source_label=run.source_label,
        language_hint=run.language_hint,
        created_at=run.created_at,
    )


@router.post("/run/upload", response_model=MediaLoggerRunResponse, status_code=status.HTTP_202_ACCEPTED)
async def run_from_upload(
    file: UploadFile = File(...),
    language_hint: str = Form("ar"),
    idempotency_key: str | None = Form(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_run(current_user)
    payload = await file.read()
    if not payload:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty")
    if len(payload) > 400 * 1024 * 1024:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File is larger than 400MB")
    run = await media_logger_service.create_run_from_upload(
        db,
        filename=file.filename or "upload.bin",
        payload=payload,
        language_hint=language_hint,
        actor=current_user,
        idempotency_key=idempotency_key,
    )
    if run.status in {"queued", "running"}:
        await media_logger_service.start_run_task(run.run_id)
    return MediaLoggerRunResponse(
        run_id=run.run_id,
        status=run.status,
        source_type=run.source_type,
        source_label=run.source_label,
        language_hint=run.language_hint,
        created_at=run.created_at,
    )


@router.get("/runs/{run_id}", response_model=MediaLoggerRunStatusResponse)
async def run_status(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_view(current_user)
    row = await media_logger_service.get_run_status(db, run_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return MediaLoggerRunStatusResponse(
        run_id=row.run_id,
        status=row.status,
        transcript_language=row.transcript_language,
        segments_count=row.segments_count,
        highlights_count=row.highlights_count,
        duration_seconds=row.duration_seconds,
        error=row.error,
        created_at=row.created_at,
        finished_at=row.finished_at,
    )


@router.get("/result", response_model=MediaLoggerResultResponse)
async def run_result(
    run_id: str = Query(..., min_length=8, max_length=64),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_view(current_user)
    result = await media_logger_service.get_result(db, run_id)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Result not available yet")
    return MediaLoggerResultResponse.model_validate(result)


@router.get("/runs")
async def recent_runs(
    limit: int = Query(20, ge=1, le=100),
    status_filter: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_view(current_user)
    items = await media_logger_service.get_recent_runs(db, limit=limit, status=status_filter)
    return {"items": items, "total": len(items)}


@router.post("/ask", response_model=MediaLoggerAskResponse)
async def ask_quote(
    payload: MediaLoggerAskRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_view(current_user)
    try:
        answer = await media_logger_service.ask_question(db, payload.run_id, payload.question)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if not answer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return MediaLoggerAskResponse.model_validate(answer)


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
                events = await media_logger_service.get_events_since(db, run_id=run_id, last_id=last_id, limit=100)
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

                run = await media_logger_service.get_run_status(db, run_id)
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
