from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import desc, select

from app.api.deps.rbac import enforce_roles
from app.api.envelope import success_envelope
from app.api.routes.auth import get_current_user
from app.core.database import get_db
from app.models import ActionAuditLog
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
VIEW_ROLES = {UserRole.director, UserRole.editor_chief}


class UxTelemetryEventRequest(BaseModel):
    event_name: str = Field(..., min_length=2, max_length=64)
    surface: str = Field(..., min_length=2, max_length=64)
    target_surface: str | None = Field(default=None, max_length=64)
    entity_type: str | None = Field(default=None, max_length=64)
    entity_id: str | int | None = None
    action_label: str | None = Field(default=None, max_length=120)
    page_path: str | None = Field(default=None, max_length=255)
    details: dict[str, Any] = Field(default_factory=dict)


def _require_view(current_user: User) -> None:
    enforce_roles(current_user, VIEW_ROLES, message="Not allowed")


def _actor_role(entry: ActionAuditLog) -> str | None:
    details = entry.details_json or {}
    if isinstance(details, dict):
        value = details.get("actor_role")
        return str(value) if value is not None else None
    return None


def _action_label(entry: ActionAuditLog) -> str | None:
    details = entry.details_json or {}
    if isinstance(details, dict):
        value = details.get("action_label")
        return str(value) if value is not None else None
    return None


def _page_path(entry: ActionAuditLog) -> str | None:
    details = entry.details_json or {}
    if isinstance(details, dict):
        value = details.get("page_path")
        return str(value) if value is not None else None
    return None


def _serialize_recent(entry: ActionAuditLog) -> dict[str, Any]:
    return {
        "id": entry.id,
        "created_at": entry.created_at.isoformat() if entry.created_at else None,
        "actor_username": entry.actor_username,
        "actor_role": _actor_role(entry),
        "event_name": entry.reason,
        "surface": entry.entity_id,
        "action_label": _action_label(entry),
        "page_path": _page_path(entry),
    }


def _count_unique_users(items: list[ActionAuditLog], predicate) -> int:
    return len(
        {
            item.actor_username
            for item in items
            if item.actor_username and predicate(item)
        }
    )


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


@router.get("/ux/recent")
async def get_recent_ux_events(
    limit: int = 30,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_view(current_user)
    safe_limit = max(1, min(limit, 100))
    rows = await db.execute(
        select(ActionAuditLog)
        .where(ActionAuditLog.action == "ux_event")
        .order_by(desc(ActionAuditLog.created_at))
        .limit(safe_limit)
    )
    items = rows.scalars().all()
    return success_envelope([_serialize_recent(item) for item in items])


@router.get("/ux/summary")
async def get_ux_summary(
    days: int = 7,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_view(current_user)
    safe_days = max(1, min(days, 30))
    cutoff = datetime.now(timezone.utc) - timedelta(days=safe_days)

    rows = await db.execute(
        select(ActionAuditLog)
        .where(ActionAuditLog.action == "ux_event", ActionAuditLog.created_at >= cutoff)
        .order_by(desc(ActionAuditLog.created_at))
    )
    items = rows.scalars().all()

    surface_counter: Counter[str] = Counter()
    role_counter: Counter[str] = Counter()
    action_counter: Counter[str] = Counter()
    surface_views_counter: Counter[str] = Counter()
    next_actions_counter: Counter[str] = Counter()
    ui_actions_counter: Counter[str] = Counter()
    role_views_counter: Counter[str] = Counter()
    role_next_actions_counter: Counter[str] = Counter()
    usernames: set[str] = set()
    chief_roles = {"director", "editor_chief"}
    author_roles = {"journalist", "social_media", "print_editor", "fact_checker"}

    for item in items:
        surface = item.entity_id or "unknown"
        role = _actor_role(item) or "unknown"
        action_label = _action_label(item)
        event_name = item.reason or "unknown"

        surface_counter[surface] += 1
        role_counter[role] += 1
        if item.actor_username:
            usernames.add(item.actor_username)

        if event_name == "surface_view":
            surface_views_counter[surface] += 1
            role_views_counter[role] += 1
        elif event_name == "next_action_click":
            next_actions_counter[surface] += 1
            role_next_actions_counter[role] += 1

        if event_name == "ui_action":
            ui_actions_counter[surface] += 1

        if action_label:
            action_counter[action_label] += 1

    return success_envelope(
        {
            "days": safe_days,
            "total_events": len(items),
            "unique_users": len(usernames),
            "surface_views": sum(surface_views_counter.values()),
            "next_action_clicks": sum(next_actions_counter.values()),
            "ui_actions": sum(ui_actions_counter.values()),
            "by_surface": [
                {
                    "surface": surface,
                    "total_events": total,
                    "surface_views": surface_views_counter.get(surface, 0),
                    "next_action_clicks": next_actions_counter.get(surface, 0),
                    "ui_actions": ui_actions_counter.get(surface, 0),
                }
                for surface, total in surface_counter.most_common()
            ],
            "by_role": [
                {
                    "role": role,
                    "total_events": total,
                    "surface_views": role_views_counter.get(role, 0),
                    "next_action_clicks": role_next_actions_counter.get(role, 0),
                }
                for role, total in role_counter.most_common()
            ],
            "top_actions": [
                {"action_label": label, "total": total}
                for label, total in action_counter.most_common(10)
            ],
            "funnels": {
                "chief": [
                    {
                        "step": "today",
                        "label": "اليوم",
                        "users": _count_unique_users(
                            items,
                            lambda item: _actor_role(item) in chief_roles
                            and item.reason == "surface_view"
                            and item.entity_id == "today",
                        ),
                    },
                    {
                        "step": "editorial",
                        "label": "الاعتماد",
                        "users": _count_unique_users(
                            items,
                            lambda item: _actor_role(item) in chief_roles
                            and item.reason == "surface_view"
                            and item.entity_id == "editorial",
                        ),
                    },
                    {
                        "step": "workspace_drafts",
                        "label": "المسودات",
                        "users": _count_unique_users(
                            items,
                            lambda item: _actor_role(item) in chief_roles
                            and item.reason == "surface_view"
                            and item.entity_id == "workspace_drafts",
                        ),
                    },
                    {
                        "step": "next_action",
                        "label": "ضغط الإجراء التالي",
                        "users": _count_unique_users(
                            items,
                            lambda item: _actor_role(item) in chief_roles
                            and item.reason == "next_action_click",
                        ),
                    },
                ],
                "author": [
                    {
                        "step": "today",
                        "label": "اليوم",
                        "users": _count_unique_users(
                            items,
                            lambda item: _actor_role(item) in author_roles
                            and item.reason == "surface_view"
                            and item.entity_id == "today",
                        ),
                    },
                    {
                        "step": "news",
                        "label": "الأخبار",
                        "users": _count_unique_users(
                            items,
                            lambda item: _actor_role(item) in author_roles
                            and item.reason == "surface_view"
                            and item.entity_id == "news",
                        ),
                    },
                    {
                        "step": "workspace_drafts",
                        "label": "المسودات",
                        "users": _count_unique_users(
                            items,
                            lambda item: _actor_role(item) in author_roles
                            and item.reason == "surface_view"
                            and item.entity_id == "workspace_drafts",
                        ),
                    },
                    {
                        "step": "next_action",
                        "label": "ضغط الإجراء التالي",
                        "users": _count_unique_users(
                            items,
                            lambda item: _actor_role(item) in author_roles
                            and item.reason == "next_action_click",
                        ),
                    },
                ],
            },
        }
    )
