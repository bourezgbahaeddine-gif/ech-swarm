"""Background jobs API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.rbac import enforce_roles
from app.api.routes.auth import get_current_user
from app.core.database import get_db
from app.models import DeadLetterJob
from app.models.user import User, UserRole
from app.services.job_queue_service import job_queue_service
from app.services.provider_manager import provider_manager

router = APIRouter(prefix="/jobs", tags=["Jobs"])

VIEW_ROLES = {
    UserRole.director,
    UserRole.editor_chief,
    UserRole.journalist,
    UserRole.social_media,
    UserRole.print_editor,
}
RETRY_ROLES = {UserRole.director, UserRole.editor_chief}
MAINTAIN_ROLES = {UserRole.director, UserRole.editor_chief}


def _require_view(user: User) -> None:
    enforce_roles(user, VIEW_ROLES, message="Not allowed")


def _require_retry(user: User) -> None:
    enforce_roles(user, RETRY_ROLES, message="Not allowed")


def _require_maintain(user: User) -> None:
    enforce_roles(user, MAINTAIN_ROLES, message="Not allowed")


@router.get("")
async def list_jobs(
    limit: int = Query(50, ge=1, le=200),
    status_filter: str | None = Query(default=None),
    job_type: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_view(current_user)
    jobs = await job_queue_service.list_jobs(db, limit=limit, status=status_filter, job_type=job_type)
    return {
        "items": [
            {
                "id": str(j.id),
                "job_type": j.job_type,
                "queue_name": j.queue_name,
                "entity_id": j.entity_id,
                "status": j.status,
                "attempt": j.attempt,
                "max_attempts": j.max_attempts,
                "error": j.error,
                "queued_at": j.queued_at,
                "started_at": j.started_at,
                "finished_at": j.finished_at,
            }
            for j in jobs
        ],
        "total": len(jobs),
    }


@router.get("/queues/depth")
async def get_queue_depths(current_user: User = Depends(get_current_user)):
    _require_view(current_user)
    return {"queues": await job_queue_service.queue_depths()}


@router.get("/providers/health")
async def providers_health(current_user: User = Depends(get_current_user)):
    _require_view(current_user)
    return {"providers": provider_manager.health()}


@router.get("/dead-letter")
async def list_dead_letter_jobs(
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_view(current_user)
    rows = await db.execute(select(DeadLetterJob).order_by(desc(DeadLetterJob.failed_at)).limit(limit))
    items = rows.scalars().all()
    return {
        "items": [
            {
                "id": str(item.id),
                "original_job_id": str(item.original_job_id),
                "job_type": item.job_type,
                "queue_name": item.queue_name,
                "failed_at": item.failed_at,
                "error": item.error,
            }
            for item in items
        ],
        "total": len(items),
    }


@router.get("/{job_id}")
async def get_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_view(current_user)
    job = await job_queue_service.get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return {
        "id": str(job.id),
        "job_type": job.job_type,
        "queue_name": job.queue_name,
        "entity_id": job.entity_id,
        "status": job.status,
        "attempt": job.attempt,
        "max_attempts": job.max_attempts,
        "error": job.error,
        "result": job.result_json or {},
        "payload": job.payload_json or {},
        "request_id": job.request_id,
        "correlation_id": job.correlation_id,
        "queued_at": job.queued_at,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
    }


@router.post("/{job_id}/retry", status_code=status.HTTP_202_ACCEPTED)
async def retry_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_retry(current_user)
    job = await job_queue_service.get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if job.status not in {"failed", "dead_lettered"}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only failed jobs can be retried")
    job.status = "queued"
    job.error = None
    job.finished_at = None
    await db.commit()
    await job_queue_service.enqueue_by_job_type(job_type=job.job_type, job_id=str(job.id))
    return {"job_id": str(job.id), "status": "queued", "message": "Retry enqueued"}


@router.post("/recover/stale", status_code=status.HTTP_200_OK)
async def recover_stale_jobs(
    stale_running_minutes: int = Query(15, ge=1, le=1440),
    stale_queued_minutes: int = Query(30, ge=1, le=1440),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_maintain(current_user)
    result = await job_queue_service.mark_stale_jobs_failed(
        db,
        stale_running_minutes=stale_running_minutes,
        stale_queued_minutes=stale_queued_minutes,
    )
    return {
        "status": "ok",
        "stale_running_minutes": stale_running_minutes,
        "stale_queued_minutes": stale_queued_minutes,
        **result,
    }
