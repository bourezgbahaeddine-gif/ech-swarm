from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from app.models.news import NewsStatus


STATE_TRANSITIONS: dict[NewsStatus, set[NewsStatus]] = {
    NewsStatus.NEW: {NewsStatus.CLEANED, NewsStatus.CLASSIFIED, NewsStatus.ARCHIVED, NewsStatus.REJECTED},
    NewsStatus.CLEANED: {NewsStatus.DEDUPED, NewsStatus.CLASSIFIED, NewsStatus.ARCHIVED, NewsStatus.REJECTED},
    NewsStatus.DEDUPED: {NewsStatus.CLASSIFIED, NewsStatus.ARCHIVED, NewsStatus.REJECTED},
    NewsStatus.CLASSIFIED: {NewsStatus.CANDIDATE, NewsStatus.ARCHIVED, NewsStatus.REJECTED},
    NewsStatus.CANDIDATE: {NewsStatus.APPROVED, NewsStatus.REJECTED, NewsStatus.APPROVED_HANDOFF},
    NewsStatus.APPROVED: {NewsStatus.APPROVED_HANDOFF, NewsStatus.DRAFT_GENERATED, NewsStatus.ARCHIVED},
    NewsStatus.APPROVED_HANDOFF: {NewsStatus.DRAFT_GENERATED, NewsStatus.ARCHIVED},
    NewsStatus.DRAFT_GENERATED: {
        NewsStatus.READY_FOR_CHIEF_APPROVAL,
        NewsStatus.APPROVAL_REQUEST_WITH_RESERVATIONS,
        NewsStatus.APPROVED_HANDOFF,
        NewsStatus.READY_FOR_MANUAL_PUBLISH,
        NewsStatus.ARCHIVED,
    },
    NewsStatus.READY_FOR_CHIEF_APPROVAL: {
        NewsStatus.READY_FOR_MANUAL_PUBLISH,
        NewsStatus.DRAFT_GENERATED,
        NewsStatus.APPROVAL_REQUEST_WITH_RESERVATIONS,
        NewsStatus.REJECTED,
    },
    NewsStatus.APPROVAL_REQUEST_WITH_RESERVATIONS: {
        NewsStatus.READY_FOR_CHIEF_APPROVAL,
        NewsStatus.DRAFT_GENERATED,
        NewsStatus.READY_FOR_MANUAL_PUBLISH,
        NewsStatus.REJECTED,
    },
    NewsStatus.READY_FOR_MANUAL_PUBLISH: {NewsStatus.PUBLISHED, NewsStatus.ARCHIVED},
    NewsStatus.PUBLISHED: {NewsStatus.ARCHIVED},
    NewsStatus.REJECTED: set(),
    NewsStatus.ARCHIVED: set(),
}


@dataclass(slots=True)
class TransitionValidationResult:
    valid: bool
    from_state: NewsStatus
    to_state: NewsStatus
    allowed_targets: list[NewsStatus]


def allowed_targets(from_state: NewsStatus) -> set[NewsStatus]:
    return set(STATE_TRANSITIONS.get(from_state, set()))


def can_transition(from_state: NewsStatus, to_state: NewsStatus) -> bool:
    if from_state == to_state:
        return True
    return to_state in allowed_targets(from_state)


def validate_transition(from_state: NewsStatus, to_state: NewsStatus) -> TransitionValidationResult:
    targets = sorted(allowed_targets(from_state), key=lambda item: item.value)
    return TransitionValidationResult(
        valid=can_transition(from_state, to_state),
        from_state=from_state,
        to_state=to_state,
        allowed_targets=targets,
    )


def validate_path(states: Iterable[NewsStatus]) -> bool:
    sequence = list(states)
    if len(sequence) <= 1:
        return True
    return all(can_transition(sequence[idx], sequence[idx + 1]) for idx in range(0, len(sequence) - 1))

