from __future__ import annotations

from typing import Any

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.correlation import get_correlation_id, get_request_id
from app.core.logging import get_logger
from app.models import ActionAuditLog
from app.models.user import User

logger = get_logger("services.audit")


class AuditService:
    async def log_action(
        self,
        db: AsyncSession,
        *,
        action: str,
        entity_type: str,
        entity_id: str | int | None = None,
        actor: User | None = None,
        reason: str | None = None,
        from_state: str | None = None,
        to_state: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        try:
            db.add(
                ActionAuditLog(
                    action=action,
                    entity_type=entity_type,
                    entity_id=str(entity_id) if entity_id is not None else None,
                    from_state=from_state,
                    to_state=to_state,
                    reason=reason,
                    details_json=details or {},
                    actor_user_id=actor.id if actor else None,
                    actor_username=actor.username if actor else None,
                    correlation_id=get_correlation_id() or None,
                    request_id=get_request_id() or None,
                )
            )
            await db.flush()
        except SQLAlchemyError as exc:
            logger.warning(
                "audit_log_failed",
                action=action,
                entity_type=entity_type,
                error=str(exc.__class__.__name__),
            )


audit_service = AuditService()

