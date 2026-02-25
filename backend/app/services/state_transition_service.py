from __future__ import annotations

from fastapi import HTTPException

from app.domain.news.state_machine import validate_transition
from app.models.news import NewsStatus


class StateTransitionService:
    def assert_transition(self, *, current: NewsStatus, target: NewsStatus, entity: str = "article") -> None:
        result = validate_transition(current, target)
        if result.valid:
            return
        raise HTTPException(
            status_code=409,
            detail={
                "code": "invalid_state_transition",
                "entity": entity,
                "from_state": current.value,
                "to_state": target.value,
                "allowed_targets": [item.value for item in result.allowed_targets],
            },
        )


state_transition_service = StateTransitionService()

