from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.services.job_queue_service import JobQueueService


class _Result:
    def __init__(self, *, rows=None):
        self._rows = list(rows or [])

    def all(self):
        return list(self._rows)


class _DbStub:
    def __init__(self, results):
        self._results = list(results)

    async def execute(self, _stmt):
        if not self._results:
            raise AssertionError("Unexpected execute call")
        return self._results.pop(0)


def test_backpressure_exception_shape():
    svc = JobQueueService()
    exc = svc.backpressure_exception(
        queue_name="ai_quality",
        current_depth=345,
        depth_limit=300,
        message="Queue busy",
    )

    assert exc.status_code == 429
    assert isinstance(exc.detail, dict)
    assert exc.detail["queue_name"] == "ai_quality"
    assert exc.detail["current_depth"] == 345
    assert exc.detail["depth_limit"] == 300
    assert isinstance(exc.detail["retry_after_seconds"], int)
    assert exc.detail["retry_after_seconds"] > 0
    assert exc.headers["Retry-After"] == str(exc.detail["retry_after_seconds"])


@pytest.mark.asyncio
async def test_queue_sla_overview_aggregates_metrics(monkeypatch):
    svc = JobQueueService()
    now = datetime.utcnow()
    db = _DbStub(
        [
            _Result(
                rows=[
                    ("ai_router", 180.0, 20, 4),  # 3.0 min runtime, 20% failure
                    ("ai_scribe", 900.0, 4, 2),  # 15.0 min runtime, 50% failure
                ]
            ),
            _Result(
                rows=[
                    ("ai_router", 1, now - timedelta(minutes=12)),
                ]
            ),
            _Result(
                rows=[
                    ("ai_router", 5, now - timedelta(minutes=8)),
                    ("ai_scribe", 2, now - timedelta(minutes=3)),
                ]
            ),
        ]
    )

    async def _queue_depths():
        return {"ai_router": 12, "ai_scribe": 2}

    monkeypatch.setattr(svc, "queue_depths", _queue_depths)

    overview = await svc.queue_sla_overview(db, lookback_hours=24)

    assert overview["lookback_hours"] == 24
    assert "generated_at" in overview
    rows = {row["queue_name"]: row for row in overview["queues"]}
    assert {"ai_router", "ai_scribe"} <= set(rows.keys())

    router = rows["ai_router"]
    assert router["depth"] == 12
    assert router["mean_runtime"] == 3.0
    assert router["failure_rate_24h"] == 20.0
    assert router["oldest_task_age"] >= 11.5
    assert router["SLA_target_minutes"] == 10
    assert router["SLA_breached"] is True
    assert router["active_running_jobs"] == 1
    assert router["active_queued_jobs"] == 5
    assert router["state_drift_suspected"] is False

    scribe = rows["ai_scribe"]
    assert scribe["depth"] == 2
    assert scribe["oldest_task_age"] >= 2.5
    assert scribe["mean_runtime"] == 15.0
    assert scribe["failure_rate_24h"] == 50.0
    assert scribe["SLA_target_minutes"] == 20
    assert scribe["SLA_breached"] is True
    assert scribe["active_running_jobs"] == 0
    assert scribe["active_queued_jobs"] == 2


@pytest.mark.asyncio
async def test_queue_sla_ignores_queued_age_when_depth_is_zero(monkeypatch):
    svc = JobQueueService()
    now = datetime.utcnow()
    db = _DbStub(
        [
            _Result(rows=[]),
            _Result(rows=[]),
            _Result(rows=[("ai_router", 3, now - timedelta(minutes=240))]),
        ]
    )

    async def _queue_depths():
        return {"ai_router": 0}

    monkeypatch.setattr(svc, "queue_depths", _queue_depths)

    overview = await svc.queue_sla_overview(db, lookback_hours=24)
    row = next(item for item in overview["queues"] if item["queue_name"] == "ai_router")

    assert row["depth"] == 0
    assert row["active_queued_jobs"] == 3
    assert row["active_running_jobs"] == 0
    assert row["state_drift_suspected"] is True
    assert row["oldest_task_age"] == 0.0
    assert row["SLA_breached"] is False


@pytest.mark.asyncio
async def test_queue_sla_keeps_running_age_signal_when_depth_is_zero(monkeypatch):
    svc = JobQueueService()
    now = datetime.utcnow()
    db = _DbStub(
        [
            _Result(rows=[]),
            _Result(rows=[("ai_router", 1, now - timedelta(minutes=45))]),
            _Result(rows=[]),
        ]
    )

    async def _queue_depths():
        return {"ai_router": 0}

    monkeypatch.setattr(svc, "queue_depths", _queue_depths)

    overview = await svc.queue_sla_overview(db, lookback_hours=24)
    row = next(item for item in overview["queues"] if item["queue_name"] == "ai_router")

    assert row["depth"] == 0
    assert row["active_running_jobs"] == 1
    assert row["active_queued_jobs"] == 0
    assert row["state_drift_suspected"] is False
    assert row["oldest_task_age"] >= 44.0
    assert row["SLA_breached"] is True
