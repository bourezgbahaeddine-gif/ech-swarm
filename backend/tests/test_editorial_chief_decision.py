from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.deps.rbac import enforce_roles
from app.api.routes import editorial as editorial_route
from app.domain.quality.gates import GateIssue, GateResult, GateSeverity
from app.models.news import NewsStatus
from app.models.user import UserRole


class _Result:
    def __init__(self, scalar):
        self._scalar = scalar

    def scalar_one_or_none(self):
        return self._scalar


class _DbStub:
    def __init__(self, article):
        self._article = article
        self.added = []
        self.committed = False

    async def execute(self, _stmt):
        return _Result(self._article)

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.committed = True


def _chief_user():
    return SimpleNamespace(
        id=7,
        username="chief",
        full_name_ar="Editor Chief",
        role=UserRole.editor_chief,
    )


def _chief_article():
    return SimpleNamespace(
        id=101,
        status=NewsStatus.READY_FOR_CHIEF_APPROVAL,
        title_ar="Title",
        body_html="<p>Body</p>",
        reviewed_by=None,
        reviewed_at=None,
        rejection_reason=None,
    )


@pytest.mark.asyncio
async def test_chief_reservations_requires_reason():
    db = _DbStub(_chief_article())
    payload = editorial_route.ChiefFinalDecisionRequest(
        decision="approve_with_reservations",
        notes=None,
    )

    with pytest.raises(HTTPException) as exc_info:
        await editorial_route.chief_final_decision(
            article_id=101,
            payload=payload,
            db=db,
            current_user=_chief_user(),
        )

    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_chief_approve_blocked_when_gate_has_blockers(monkeypatch):
    db = _DbStub(_chief_article())
    payload = editorial_route.ChiefFinalDecisionRequest(
        decision="approve",
        notes=None,
    )

    async def _deny_publish_gate(*_args, **_kwargs):
        raise HTTPException(
            status_code=412,
            detail={
                "message": "gate_failed",
                "blocking_reasons": ["FACT_CHECK blocker"],
            },
        )

    monkeypatch.setattr(editorial_route, "_assert_publish_gate_and_constitution", _deny_publish_gate)

    with pytest.raises(HTTPException) as exc_info:
        await editorial_route.chief_final_decision(
            article_id=101,
            payload=payload,
            db=db,
            current_user=_chief_user(),
        )

    assert exc_info.value.status_code == 412
    assert "blocking_reasons" in exc_info.value.detail
    assert db.committed is False


@pytest.mark.asyncio
async def test_chief_approve_with_reservations_records_overridden_blockers(monkeypatch):
    article = _chief_article()
    db = _DbStub(article)
    payload = editorial_route.ChiefFinalDecisionRequest(
        decision="approve_with_reservations",
        notes="Keeping as reservations until desk review.",
    )

    async def _fake_latest_stage_report(*_args, **_kwargs):
        return None

    async def _fake_transition(*, article, target_status, **_kwargs):
        article.status = target_status
        return article

    async def _noop_publish_gate(*_args, **_kwargs):
        return None

    async def _noop_flush(*_args, **_kwargs):
        return None

    async def _fake_run_gates(*_args, **_kwargs):
        return GateResult(
            passed=False,
            issues=[
                GateIssue(code="a", message="Policy blocker A", severity=GateSeverity.BLOCKER, details={}),
                GateIssue(code="a2", message="Policy blocker A", severity=GateSeverity.BLOCKER, details={}),
                GateIssue(code="b", message="Policy blocker B", severity=GateSeverity.BLOCKER, details={}),
            ],
        )

    monkeypatch.setattr(editorial_route, "_latest_stage_report", _fake_latest_stage_report)
    monkeypatch.setattr(editorial_route, "_transition_article_status", _fake_transition)
    monkeypatch.setattr(editorial_route, "_assert_publish_gate_and_constitution", _noop_publish_gate)
    monkeypatch.setattr(editorial_route.notification_service, "send_policy_gate_alert", _noop_flush)
    monkeypatch.setattr(editorial_route.quality_gate_service, "run_submission_quality_gates", _fake_run_gates)

    response = await editorial_route.chief_final_decision(
        article_id=101,
        payload=payload,
        db=db,
        current_user=_chief_user(),
    )

    assert response["decision"] == "approve_with_reservations"
    assert response["status"] == NewsStatus.APPROVAL_REQUEST_WITH_RESERVATIONS.value
    assert response["overridden_blockers"] == ["Policy blocker A", "Policy blocker B"]
    assert db.committed is True


def test_rbac_chief_override_denied_for_journalist():
    journalist = SimpleNamespace(role=UserRole.journalist)
    with pytest.raises(HTTPException) as exc_info:
        enforce_roles(journalist, {UserRole.director, UserRole.editor_chief})
    assert exc_info.value.status_code == 403
