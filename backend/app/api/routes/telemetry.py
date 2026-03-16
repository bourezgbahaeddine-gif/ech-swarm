from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.rbac import enforce_roles
from app.api.envelope import success_envelope
from app.api.routes.auth import get_current_user
from app.core.database import get_db
from app.models.user import User, UserRole
from app.services.audit_service import audit_service

router = APIRouter(prefix="/telemetry", tags=["UX Telemetry"])

ALLOWED_ROLES = {
    UserRole.director,
    UserRole.editor_chief,
    UserRole.journalist,
    UserRole.social_media,
    UserRole.print_editor,
}


class UxTelemetryEventRequest(BaseModel):
    event_name: str = Field(..., min_length=2, max_length=64)
    surface: str = Field(..., min_length=2, max_length=64)
    target_surface: str | None = Field(default=None, max_length=64)
    entity_type: str | None = Field(default=None, max_length=64)
    entity_id: str | int | None = None
    action_label: str | None = Field(default=None, max_length=120)
    page_path: str | None = Field(default=None, max_length=255)
    details: dict[str, Any] = Field(default_factory=dict)


@router.post("/ux", status_code=status.HTTP_202_ACCEPTED)
async def log_ux_event(
    payload: UxTelemetryEventRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    enforce_roles(current_user, ALLOWED_ROLES, message="Not allowed")

    details = {
        **payload.details,
        "surface": payload.surface,
        "target_surface": payload.target_surface,
        "entity_type": payload.entity_type,
        "entity_id": str(payload.entity_id) if payload.entity_id is not None else None,
        "action_label": payload.action_label,
        "page_path": payload.page_path,
        "actor_role": current_user.role.value if current_user.role else None,
    }

    await audit_service.log_action(
        db,
        action="ux_event",
        entity_type="ux_surface",
        entity_id=payload.surface,
        actor=current_user,
        reason=payload.event_name,
        details=details,
    )
    await db.commit()

    return success_envelope(
        {
            "logged": True,
            "surface": payload.surface,
            "event_name": payload.event_name,
        },
        status_code=status.HTTP_202_ACCEPTED,
    )
