"""Document Intelligence routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app.api.routes.auth import get_current_user
from app.models.user import User, UserRole
from app.schemas.document_intel import DocumentExtractResponse
from app.services.document_intel_service import document_intel_service

router = APIRouter(prefix="/document-intel", tags=["Document Intelligence"])

ALLOWED_ROLES = {
    UserRole.journalist,
    UserRole.editor_chief,
    UserRole.director,
    UserRole.social_media,
    UserRole.print_editor,
}


def _require_access(user: User) -> None:
    if user.role not in ALLOWED_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized for document extraction")


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
