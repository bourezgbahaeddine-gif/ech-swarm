from __future__ import annotations

import json
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.routes import scripts as scripts_route
from app.models.script import ScriptProjectStatus, ScriptProjectType
from app.models.user import UserRole
from app.services.script_studio_service import script_studio_service


class _ScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value

    def scalars(self):
        return SimpleNamespace(all=lambda: list(self._value or []))


class _SequenceDb:
    def __init__(self, results):
        self._results = list(results)
        self._index = 0

    async def execute(self, _stmt):
        if self._index >= len(self._results):
            raise AssertionError("Unexpected DB execute call")
        result = self._results[self._index]
        self._index += 1
        return _ScalarResult(result)

    async def commit(self):
        return None


def _decode_data(response):
    payload = json.loads(response.body.decode("utf-8"))
    return payload["data"]


@pytest.mark.asyncio
async def test_create_script_from_article_smoke(monkeypatch):
    article = SimpleNamespace(
        id=77,
        title_ar="عنوان الخبر",
        original_title="Story title",
    )
    now = datetime.now(timezone.utc)
    created_project = SimpleNamespace(
        id=31,
        type=ScriptProjectType.story_script,
        status=ScriptProjectStatus.new,
        story_id=None,
        article_id=77,
        title="Story Script - عنوان الخبر",
        params_json={"tone": "neutral"},
        created_by="editor",
        updated_by="editor",
        created_at=now,
        updated_at=now,
        outputs=[],
    )

    async def _noop_audit(*_args, **_kwargs):
        return None

    async def _fake_create_project(*_args, **_kwargs):
        return created_project

    async def _fake_queue(**_kwargs):
        return {"job_id": "job-1", "status": "queued", "target_version": 1}

    async def _fake_get_project(*_args, **_kwargs):
        return created_project

    monkeypatch.setattr(scripts_route.audit_service, "log_action", _noop_audit)
    monkeypatch.setattr(scripts_route.script_repository, "create_project", _fake_create_project)
    monkeypatch.setattr(scripts_route, "_queue_script_generation", _fake_queue)
    monkeypatch.setattr(scripts_route.script_repository, "get_project_by_id", _fake_get_project)

    db = _SequenceDb([article])
    current_user = SimpleNamespace(id=1, username="editor", role=UserRole.journalist)
    payload = scripts_route.ScriptFromArticleRequest(type="story_script", tone="neutral", length_seconds=90, language="ar")

    response = await scripts_route.create_script_from_article(
        article_id=77,
        payload=payload,
        db=db,
        current_user=current_user,
    )
    data = _decode_data(response)

    assert data["script"]["id"] == 31
    assert data["script"]["article_id"] == 77
    assert data["job"]["target_version"] == 1


@pytest.mark.asyncio
async def test_generate_bulletin_selects_items(monkeypatch):
    selected_articles = [
        SimpleNamespace(id=101),
        SimpleNamespace(id=102),
        SimpleNamespace(id=103),
    ]
    now = datetime.now(timezone.utc)
    captured_params: dict = {}

    async def _fake_select_articles(*_args, **_kwargs):
        return selected_articles

    async def _noop_audit(*_args, **_kwargs):
        return None

    async def _fake_create_project(*_args, **kwargs):
        captured_params.update(kwargs.get("params_json", {}))
        return SimpleNamespace(
            id=55,
            type=ScriptProjectType.bulletin_daily,
            status=ScriptProjectStatus.new,
            story_id=None,
            article_id=None,
            title="Daily Bulletin",
            params_json=kwargs.get("params_json", {}),
            created_by="editor",
            updated_by="editor",
            created_at=now,
            updated_at=now,
            outputs=[],
        )

    async def _fake_queue(**_kwargs):
        return {"job_id": "job-2", "status": "queued", "target_version": 1}

    async def _fake_get_project(*_args, **_kwargs):
        return SimpleNamespace(
            id=55,
            type=ScriptProjectType.bulletin_daily,
            status=ScriptProjectStatus.new,
            story_id=None,
            article_id=None,
            title="Daily Bulletin",
            params_json=captured_params,
            created_by="editor",
            updated_by="editor",
            created_at=now,
            updated_at=now,
            outputs=[],
        )

    monkeypatch.setattr(scripts_route.script_studio_service, "select_bulletin_articles", _fake_select_articles)
    monkeypatch.setattr(scripts_route.audit_service, "log_action", _noop_audit)
    monkeypatch.setattr(scripts_route.script_repository, "create_project", _fake_create_project)
    monkeypatch.setattr(scripts_route, "_queue_script_generation", _fake_queue)
    monkeypatch.setattr(scripts_route.script_repository, "get_project_by_id", _fake_get_project)

    db = _SequenceDb([])
    current_user = SimpleNamespace(id=1, username="editor", role=UserRole.journalist)
    payload = scripts_route.BulletinRequest(max_items=8, duration_minutes=5, desks=["economy"], language="ar", tone="neutral")

    response = await scripts_route.generate_daily_bulletin(
        payload=payload,
        geo="ALL",
        category="all",
        db=db,
        current_user=current_user,
    )
    data = _decode_data(response)

    assert captured_params["selected_article_ids"] == [101, 102, 103]
    assert data["script"]["type"] == "bulletin_daily"


def test_quality_gate_blocks_missing_sections():
    quality = script_studio_service.run_quality_gates(
        project_type=ScriptProjectType.video_script,
        output_json={"vo_script": "short text"},
        params={},
    )

    assert quality["passed"] is False
    blocker_codes = {issue["code"] for issue in quality["issues"] if issue["severity"] == "blocker"}
    assert "missing_scenes" in blocker_codes


@pytest.mark.asyncio
async def test_approve_requires_role_and_reason_on_reject():
    db = _SequenceDb([])

    with pytest.raises(HTTPException) as approve_exc:
        await scripts_route.approve_script_project(
            script_id=1,
            payload=scripts_route.ScriptDecisionRequest(reason=None),
            db=db,
            current_user=SimpleNamespace(id=1, username="journalist", role=UserRole.journalist),
        )
    assert approve_exc.value.status_code == 403

    with pytest.raises(HTTPException) as reject_exc:
        await scripts_route.reject_script_project(
            script_id=1,
            payload=scripts_route.ScriptDecisionRequest(reason=None),
            db=db,
            current_user=SimpleNamespace(id=2, username="chief", role=UserRole.editor_chief),
        )
    assert reject_exc.value.status_code == 400
