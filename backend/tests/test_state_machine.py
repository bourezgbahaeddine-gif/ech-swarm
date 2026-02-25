from app.domain.news.state_machine import can_transition, validate_transition
from app.models.news import NewsStatus


def test_valid_transition_candidate_to_approved_handoff() -> None:
    assert can_transition(NewsStatus.CANDIDATE, NewsStatus.APPROVED_HANDOFF)


def test_invalid_transition_rejected_to_candidate() -> None:
    result = validate_transition(NewsStatus.REJECTED, NewsStatus.CANDIDATE)
    assert result.valid is False
    assert NewsStatus.CANDIDATE not in result.allowed_targets
