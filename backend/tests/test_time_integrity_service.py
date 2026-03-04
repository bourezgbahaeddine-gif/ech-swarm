from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from app.models.news import NewsStatus
from app.services import time_integrity_service as time_integrity_module
from app.services.time_integrity_service import TimeIntegrityService


class _Result:
    def __init__(self, *, scalar=None, rows=None, scalars=None, rowcount=None):
        self._scalar = scalar
        self._rows = list(rows or [])
        self._scalars = list(scalars or [])
        self.rowcount = rowcount

    def scalar_one_or_none(self):
        return self._scalar

    def all(self):
        return list(self._rows)

    def scalars(self):
        return SimpleNamespace(all=lambda: list(self._scalars))


class _DbStub:
    def __init__(self, results):
        self._results = list(results)
        self.committed = False

    async def execute(self, _stmt):
        if not self._results:
            raise AssertionError("Unexpected execute call")
        return self._results.pop(0)

    async def commit(self):
        self.committed = True


@pytest.mark.asyncio
async def test_archive_stale_non_published_writes_per_article_audit(monkeypatch):
    svc = TimeIntegrityService()
    now = datetime.utcnow()
    stale_rows = [
        (11, NewsStatus.CLASSIFIED, now - timedelta(hours=30)),
        (12, NewsStatus.CANDIDATE, now - timedelta(hours=28)),
    ]
    db = _DbStub(
        [
            _Result(rows=stale_rows),
            _Result(rowcount=2),
        ]
    )

    audit_calls = []

    async def _capture_audit(_db, **kwargs):
        audit_calls.append(kwargs)

    monkeypatch.setattr(time_integrity_module.audit_service, "log_action", _capture_audit)

    result = await svc.archive_stale_non_published(db, max_age_hours=24, dry_run=False)

    assert result["matched_rows"] == 2
    assert result["archived_rows"] == 2
    assert result["audit_action"] == "auto_archived_stale"
    assert len(audit_calls) == 2
    assert {call["entity_id"] for call in audit_calls} == {11, 12}
    assert all(call["action"] == "auto_archived_stale" for call in audit_calls)
    assert all(call["reason"] == "auto_archived_stale" for call in audit_calls)
    assert all(call["to_state"] == NewsStatus.ARCHIVED.value for call in audit_calls)
    assert db.committed is True

    empty_db = _DbStub([_Result(rows=[])])
    result_second = await svc.archive_stale_non_published(empty_db, max_age_hours=24, dry_run=False)
    assert result_second["matched_rows"] == 0
    assert result_second["archived_rows"] == 0
    assert empty_db.committed is False


@pytest.mark.asyncio
async def test_restore_recent_auto_archived_restores_only_guarded_rows(monkeypatch):
    svc = TimeIntegrityService()
    now = datetime.utcnow()
    log1 = SimpleNamespace(
        id=501,
        entity_id="21",
        from_state=NewsStatus.CLASSIFIED.value,
        reason="auto_archived_stale",
        details_json={"original_status": NewsStatus.CLASSIFIED.value, "age_hours": 25.2},
        created_at=now - timedelta(hours=1),
    )
    log2 = SimpleNamespace(
        id=502,
        entity_id="22",
        from_state=NewsStatus.CANDIDATE.value,
        reason="auto_archived_stale",
        details_json={"original_status": NewsStatus.CANDIDATE.value, "age_hours": 26.1},
        created_at=now - timedelta(hours=2),
    )

    db = _DbStub(
        [
            _Result(scalars=[log1, log2]),
            _Result(
                rows=[
                    (21, NewsStatus.ARCHIVED, "auto_archived:strict_time_guard:24h"),
                    (22, NewsStatus.ARCHIVED, "manual_archive_reason"),
                ]
            ),
            _Result(rowcount=1),
        ]
    )

    audit_calls = []

    async def _capture_audit(_db, **kwargs):
        audit_calls.append(kwargs)

    monkeypatch.setattr(time_integrity_module.audit_service, "log_action", _capture_audit)

    result = await svc.restore_recent_auto_archived(
        db,
        lookback_hours=24,
        max_rows=10,
        dry_run=False,
        actor=SimpleNamespace(id=1, username="director"),
    )

    assert result["candidate_logs"] == 2
    assert result["restorable_candidates"] == 1
    assert result["restored_rows"] == 1
    assert len(result["advisories"]) == 1
    assert len(audit_calls) == 1
    assert audit_calls[0]["action"] == "auto_archived_stale_restored"
    assert audit_calls[0]["entity_id"] == 21
    assert db.committed is True
