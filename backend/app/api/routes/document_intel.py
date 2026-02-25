"""Document Intelligence routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.auth import get_current_user
from app.core.database import get_db
from app.models.user import User, UserRole
from app.schemas.document_intel import (
    DocumentExtractJobStatusResponse,
    DocumentExtractResponse,
    DocumentExtractSubmitResponse,
)
from app.services.document_intel_job_storage import document_intel_job_storage
from app.services.document_intel_service import document_intel_service
from app.services.job_queue_service import job_queue_service

router = APIRouter(prefix="/document-intel", tags=["Document Intelligence"])

ALLOWED_ROLES = {
    UserRole.journalist,
    UserRole.editor_chief,
    UserRole.director,
    UserRole.social_media,
    UserRole.print_editor,
}

DOCUMENT_INTEL_JOB_TYPE = "document_intel_extract"
DOCUMENT_INTEL_QUEUE = "ai_quality"


def _require_access(user: User) -> None:
    if user.role not in ALLOWED_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized for document extraction")


@router.post("/extract/submit", response_model=DocumentExtractSubmitResponse, status_code=status.HTTP_202_ACCEPTED)
async def submit_extract_document(
    file: UploadFile = File(...),
    language_hint: str = Form("ar"),
    max_news_items: int = Form(8, ge=1, le=20),
    max_data_points: int = Form(30, ge=1, le=120),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_access(current_user)
    payload = await file.read()
    try:
        safe_name = document_intel_service.validate_upload(
            filename=file.filename or "document.pdf",
            payload=payload,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    allowed, depth, limit_depth = await job_queue_service.check_backpressure(DOCUMENT_INTEL_QUEUE)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Queue overloaded ({depth}/{limit_depth}). Please retry shortly.",
        )

    blob_key = await document_intel_job_storage.save_payload(payload)
    job = await job_queue_service.create_job(
        db,
        job_type=DOCUMENT_INTEL_JOB_TYPE,
        queue_name=DOCUMENT_INTEL_QUEUE,
        payload={
            "blob_key": blob_key,
            "filename": safe_name,
            "language_hint": language_hint,
            "max_news_items": max_news_items,
            "max_data_points": max_data_points,
        },
        actor_user_id=current_user.id,
        actor_username=current_user.username,
        entity_id=safe_name,
        max_attempts=2,
    )
    await job_queue_service.enqueue_by_job_type(job_type=DOCUMENT_INTEL_JOB_TYPE, job_id=str(job.id))
    return DocumentExtractSubmitResponse(
        job_id=str(job.id),
        status="queued",
        filename=safe_name,
        message="Document extraction queued",
    )


@router.get("/extract/{job_id}", response_model=DocumentExtractJobStatusResponse)
async def get_extract_document_status(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_access(current_user)
    job = await job_queue_service.get_job(db, job_id)
    if not job or job.job_type != DOCUMENT_INTEL_JOB_TYPE:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document extraction job not found")

    result_payload = None
    if isinstance(job.result_json, dict) and job.result_json:
        result_payload = DocumentExtractResponse.model_validate(job.result_json)

    return DocumentExtractJobStatusResponse(
        job_id=str(job.id),
        status=job.status,
        error=job.error,
        result=result_payload,
        queued_at=job.queued_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
    )


@router.post("/extract", response_model=DocumentExtractResponse)
async def extract_document(
    file: UploadFile = File(...),
    language_hint: str = Form("ar"),
    max_news_items: int = Form(8, ge=1, le=20),
    max_data_points: int = Form(30, ge=1, le=120),
    current_user: User = Depends(get_current_user),
):
    _require_access(current_user)
    payload = await file.read()
    try:
        result = await document_intel_service.extract_pdf(
            filename=file.filename or "document.pdf",
            payload=payload,
            language_hint=language_hint,
            max_news_items=max_news_items,
            max_data_points=max_data_points,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    return DocumentExtractResponse.model_validate(result)
