from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.rbac import enforce_roles
from app.api.routes.auth import get_current_user
from app.core.database import get_db
from app.models.user import User, UserRole
from app.services.echorouk_archive_service import echorouk_archive_service
from app.services.job_queue_service import job_queue_service

router = APIRouter(prefix="/archive", tags=["Archive"])

VIEW_ROLES = {
    UserRole.director,
    UserRole.editor_chief,
    UserRole.journalist,
    UserRole.social_media,
    UserRole.print_editor,
}
RUN_ROLES = {UserRole.director, UserRole.editor_chief}


def _require_view(user: User) -> None:
    enforce_roles(user, VIEW_ROLES, message="Not allowed")


def _require_run(user: User) -> None:
    enforce_roles(user, RUN_ROLES, message="Not allowed")


@router.get("/echorouk/status")
async def echorouk_archive_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_view(current_user)
    return await echorouk_archive_service.archive_status(db)


@router.get("/echorouk/search")
async def echorouk_archive_search(
    q: str = Query(..., min_length=2),
    limit: int = Query(5, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_view(current_user)
    return {
        "items": await echorouk_archive_service.semantic_search(db, q=q, limit=limit),
        "query": q,
        "limit": limit,
    }


@router.post("/echorouk/run", status_code=status.HTTP_202_ACCEPTED)
async def run_echorouk_archive_backfill(
    listing_pages: int = Query(3, ge=1, le=20),
    article_pages: int = Query(12, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_run(current_user)
    active = await job_queue_service.find_active_job(
        db,
        job_type="echorouk_archive_backfill",
        entity_id="echorouk_archive",
        max_age_minutes=240,
    )
    if active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "job_id": str(active.id),
                "status": active.status,
                "message": "Archive crawl job already active.",
            },
        )

    job = await job_queue_service.create_job(
        db,
        job_type="echorouk_archive_backfill",
        queue_name="ai_scripts",
        payload={
            "listing_pages": listing_pages,
            "article_pages": article_pages,
            "idempotency_key": f"echorouk_archive:{listing_pages}:{article_pages}",
        },
        entity_id="echorouk_archive",
        actor_user_id=current_user.id,
        actor_username=current_user.username,
        max_attempts=3,
    )
    await job_queue_service.enqueue_by_job_type(job_type="echorouk_archive_backfill", job_id=str(job.id))
    return {
        "job_id": str(job.id),
        "job_type": job.job_type,
        "queue_name": job.queue_name,
        "status": "queued",
        "listing_pages": listing_pages,
        "article_pages": article_pages,
    }
