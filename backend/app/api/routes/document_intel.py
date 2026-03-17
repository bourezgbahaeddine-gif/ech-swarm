"""Document Intelligence routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.auth import get_current_user
from app.core.database import get_db
from app.models.user import User, UserRole
from app.schemas.document_intel import (
    DocumentIntelActionLogItem,
    DocumentIntelActionResponse,
    DocumentIntelCreateDraftRequest,
    DocumentIntelCreateStoryRequest,
    DocumentExtractJobStatusResponse,
    DocumentExtractResponse,
    DocumentExtractSubmitResponse,
)
from app.services.document_intel_job_storage import document_intel_job_storage
from app.services.document_intel_service import document_intel_service
from app.services.document_intel_workspace_service import document_intel_workspace_service
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


async def _ensure_document_intel_tables(db: AsyncSession) -> None:
    checks = await db.execute(
        text(
            """
            SELECT
                to_regclass('public.document_intel_documents') AS documents_tbl,
                to_regclass('public.document_intel_claims') AS claims_tbl,
                to_regclass('public.document_intel_actions') AS actions_tbl
            """
        )
    )
    row = checks.mappings().first()
    if not row or not row["documents_tbl"] or not row["claims_tbl"] or not row["actions_tbl"]:
        raise HTTPException(
            status_code=503,
            detail="Document Intel tables are not ready. Run: alembic upgrade head",
        )


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
        raise job_queue_service.backpressure_exception(
            queue_name=DOCUMENT_INTEL_QUEUE,
            current_depth=depth,
            depth_limit=limit_depth,
            message="Document extraction queue overloaded. Please retry shortly.",
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
    db: AsyncSession = Depends(get_db),
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

    await _ensure_document_intel_tables(db)
    document = await document_intel_workspace_service.save_document_result(
        db,
        result=result,
        actor=current_user,
        source_job_id=None,
    )
    await db.commit()
    result["document_id"] = document.id
    return DocumentExtractResponse.model_validate(result)


@router.get("/documents/{document_id}", response_model=DocumentExtractResponse)
async def get_document(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_access(current_user)
    await _ensure_document_intel_tables(db)
    document = await document_intel_workspace_service.get_document(db, document_id)
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document Intel document not found")
    claims = await document_intel_workspace_service.load_claims(db, document.id)
    payload = {
        "document_id": document.id,
        "filename": document.filename,
        "parser_used": document.parser_used,
        "language_hint": document.language_hint,
        "detected_language": document.detected_language,
        "stats": document.stats or {},
        "document_summary": document.document_summary or "",
        "document_type": document.document_type,
        "headings": document.headings or [],
        "news_candidates": document.news_candidates or [],
        "claims": [
            {
                "text": claim.text,
                "type": claim.claim_type,
                "confidence": claim.confidence,
                "risk_level": claim.risk_level,
            }
            for claim in claims
        ],
        "entities": document.entities or [],
        "story_angles": document.story_angles or [],
        "data_points": document.data_points or [],
        "warnings": document.warnings or [],
        "preview_text": document.preview_text or "",
    }
    return DocumentExtractResponse.model_validate(payload)


@router.get("/documents/{document_id}/actions", response_model=list[DocumentIntelActionLogItem])
async def list_document_actions(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_access(current_user)
    await _ensure_document_intel_tables(db)
    document = await document_intel_workspace_service.get_document(db, document_id)
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document Intel document not found")
    actions = await document_intel_workspace_service.list_actions(db, document_id)
    return [
        DocumentIntelActionLogItem(
            id=action.id,
            action_type=action.action_type,
            target_type=action.target_type,
            target_id=action.target_id,
            note=action.note,
            payload=action.payload_json or {},
            actor_username=action.actor_username,
            created_at=action.created_at,
        )
        for action in actions
    ]


@router.post("/documents/{document_id}/create-story", response_model=DocumentIntelActionResponse)
async def create_story_from_document(
    document_id: int,
    payload: DocumentIntelCreateStoryRequest | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_access(current_user)
    await _ensure_document_intel_tables(db)
    document = await document_intel_workspace_service.get_document(db, document_id)
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document Intel document not found")
    story = await document_intel_workspace_service.create_story(
        db,
        document=document,
        actor=current_user,
        angle_title=(payload.angle_title if payload else None),
        angle_why_it_matters=(payload.angle_why_it_matters if payload else None),
    )
    await db.commit()
    return DocumentIntelActionResponse(
        document_id=document.id,
        action_type="create_story",
        target_type="story",
        target_id=str(story["story_id"]),
        message="تم إنشاء قصة من الوثيقة.",
        payload=story,
    )


@router.post("/documents/{document_id}/create-draft", response_model=DocumentIntelActionResponse)
async def create_draft_from_document(
    document_id: int,
    payload: DocumentIntelCreateDraftRequest | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_access(current_user)
    await _ensure_document_intel_tables(db)
    document = await document_intel_workspace_service.get_document(db, document_id)
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document Intel document not found")
    draft = await document_intel_workspace_service.create_workspace_draft(
        db,
        document=document,
        actor=current_user,
        angle_title=(payload.angle_title if payload else None),
        claim_indexes=(payload.claim_indexes if payload else None),
        category=(payload.category if payload else "international"),
        urgency=(payload.urgency if payload else "normal"),
    )
    await db.commit()
    return DocumentIntelActionResponse(
        document_id=document.id,
        action_type="create_draft",
        target_type="workspace_draft",
        target_id=str(draft["work_id"]),
        message="تم فتح الوثيقة داخل المحرر الذكي مع أهم الأدلة والادعاءات.",
        payload=draft,
    )


@router.post("/documents/{document_id}/save-memory", response_model=DocumentIntelActionResponse)
async def save_document_to_memory(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_access(current_user)
    await _ensure_document_intel_tables(db)
    document = await document_intel_workspace_service.get_document(db, document_id)
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document Intel document not found")
    item = await document_intel_workspace_service.save_memory(db, document=document, actor=current_user)
    await db.commit()
    return DocumentIntelActionResponse(
        document_id=document.id,
        action_type="save_memory",
        target_type="memory",
        target_id=str(item.id),
        message="تم حفظ خلاصة الوثيقة في الذاكرة التحريرية.",
        payload={"memory_id": item.id, "title": item.title},
    )


@router.post("/documents/{document_id}/send-to-factcheck", response_model=DocumentIntelActionResponse)
async def send_document_to_factcheck(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_access(current_user)
    await _ensure_document_intel_tables(db)
    document = await document_intel_workspace_service.get_document(db, document_id)
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document Intel document not found")
    payload = await document_intel_workspace_service.build_factcheck_packet(db, document=document, actor=current_user)
    await db.commit()
    return DocumentIntelActionResponse(
        document_id=document.id,
        action_type="send_to_factcheck",
        target_type="factcheck",
        target_id=None,
        message="تم تجهيز الوثيقة للتحقق.",
        payload=payload,
    )
