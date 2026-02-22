"""Pipeline and graph tasks executed in workers."""

from __future__ import annotations

import asyncio
import traceback
from uuid import UUID

import structlog
from celery import Task
from sqlalchemy import select

from app.agents.router import router_agent
from app.agents.scout import scout_agent
from app.agents.scribe import scribe_agent
from app.agents.trend_radar import trend_radar_agent
from app.agents.published_monitor import published_content_monitor_agent
from app.core.database import async_session
from app.core.logging import get_logger
from app.models import JobRun
from app.msi.service import msi_monitor_service
from app.queue.celery_app import celery_app
from app.services.job_queue_service import job_queue_service
from app.simulator.service import audience_simulation_service

logger = get_logger("queue.pipeline_tasks")


async def _load_job(job_id: str) -> JobRun:
    async with async_session() as db:
        row = await db.execute(select(JobRun).where(JobRun.id == UUID(job_id)))
        job = row.scalar_one_or_none()
        if not job:
            raise RuntimeError("job_not_found")
        await job_queue_service.mark_running(db, job)
        structlog.contextvars.bind_contextvars(
            job_id=job_id,
            request_id=job.request_id or "",
            correlation_id=job.correlation_id or "",
            job_type=job.job_type,
            queue_name=job.queue_name,
        )
        return job


async def _complete(job_id: str, result: dict) -> None:
    async with async_session() as db:
        row = await db.execute(select(JobRun).where(JobRun.id == UUID(job_id)))
        job = row.scalar_one_or_none()
        if job:
            await job_queue_service.mark_completed(db, job, result)


async def _fail(job_id: str, error: str, tb: str, final: bool) -> None:
    async with async_session() as db:
        row = await db.execute(select(JobRun).where(JobRun.id == UUID(job_id)))
        job = row.scalar_one_or_none()
        if not job:
            return
        if final:
            await job_queue_service.dead_letter(db, job=job, error=error, traceback_text=tb)
        else:
            await job_queue_service.mark_failed(db, job, error)


async def _run_router_batch(job_id: str) -> dict:
    await _load_job(job_id)
    async with async_session() as db:
        stats = await router_agent.process_batch(db)
    return {"stats": stats}


async def _run_scout_batch(job_id: str) -> dict:
    await _load_job(job_id)
    async with async_session() as db:
        stats = await scout_agent.run(db)
        router_stats = await router_agent.process_batch(db)
    return {"scout": stats, "router": router_stats}


async def _run_scribe_batch(job_id: str) -> dict:
    await _load_job(job_id)
    async with async_session() as db:
        stats = await scribe_agent.batch_write(db)
    return {"stats": stats}


async def _run_msi_job(job_id: str) -> dict:
    job = await _load_job(job_id)
    run_id = str((job.payload_json or {}).get("run_id") or "")
    if not run_id:
        raise RuntimeError("run_id_missing")
    await msi_monitor_service.execute_run(run_id)
    return {"run_id": run_id, "status": "completed"}


async def _run_simulator_job(job_id: str) -> dict:
    job = await _load_job(job_id)
    run_id = str((job.payload_json or {}).get("run_id") or "")
    if not run_id:
        raise RuntimeError("run_id_missing")
    await audience_simulation_service.execute_run(run_id)
    return {"run_id": run_id, "status": "completed"}


async def _run_trends_scan(job_id: str) -> dict:
    job = await _load_job(job_id)
    payload = job.payload_json or {}
    alerts = await trend_radar_agent.scan(
        geo=str(payload.get("geo") or "DZ"),
        category=str(payload.get("category") or "all"),
        limit=int(payload.get("limit") or 12),
        mode=str(payload.get("mode") or "fast"),
    )
    return {"alerts_count": len(alerts), "alerts": [a.model_dump(mode="json") for a in alerts]}


async def _run_published_monitor(job_id: str) -> dict:
    job = await _load_job(job_id)
    payload = job.payload_json or {}
    report = await published_content_monitor_agent.scan(
        feed_url=payload.get("feed_url"),
        limit=payload.get("limit"),
    )
    return {"report": report}


@celery_app.task(bind=True, autoretry_for=(TimeoutError, ConnectionError), retry_backoff=True, retry_jitter=True, max_retries=5)
def run_router_batch(self: Task, job_id: str) -> dict:
    try:
        result = asyncio.run(_run_router_batch(job_id))
        asyncio.run(_complete(job_id, result))
        structlog.contextvars.clear_contextvars()
        return {"ok": True}
    except Exception as exc:  # noqa: BLE001
        tb = traceback.format_exc()
        final = int(getattr(self.request, "retries", 0)) >= int(getattr(self, "max_retries", 5))
        asyncio.run(_fail(job_id, str(exc), tb, final))
        structlog.contextvars.clear_contextvars()
        raise


@celery_app.task(bind=True, autoretry_for=(TimeoutError, ConnectionError), retry_backoff=True, retry_jitter=True, max_retries=3)
def run_scout_batch(self: Task, job_id: str) -> dict:
    try:
        result = asyncio.run(_run_scout_batch(job_id))
        asyncio.run(_complete(job_id, result))
        structlog.contextvars.clear_contextvars()
        return {"ok": True}
    except Exception as exc:  # noqa: BLE001
        tb = traceback.format_exc()
        final = int(getattr(self.request, "retries", 0)) >= int(getattr(self, "max_retries", 3))
        asyncio.run(_fail(job_id, str(exc), tb, final))
        structlog.contextvars.clear_contextvars()
        raise


@celery_app.task(bind=True, autoretry_for=(TimeoutError, ConnectionError), retry_backoff=True, retry_jitter=True, max_retries=5)
def run_scribe_batch(self: Task, job_id: str) -> dict:
    try:
        result = asyncio.run(_run_scribe_batch(job_id))
        asyncio.run(_complete(job_id, result))
        structlog.contextvars.clear_contextvars()
        return {"ok": True}
    except Exception as exc:  # noqa: BLE001
        tb = traceback.format_exc()
        final = int(getattr(self.request, "retries", 0)) >= int(getattr(self, "max_retries", 5))
        asyncio.run(_fail(job_id, str(exc), tb, final))
        structlog.contextvars.clear_contextvars()
        raise


@celery_app.task(bind=True, autoretry_for=(TimeoutError, ConnectionError), retry_backoff=True, retry_jitter=True, max_retries=3)
def run_trends_scan(self: Task, job_id: str) -> dict:
    try:
        result = asyncio.run(_run_trends_scan(job_id))
        asyncio.run(_complete(job_id, result))
        structlog.contextvars.clear_contextvars()
        return {"ok": True}
    except Exception as exc:  # noqa: BLE001
        tb = traceback.format_exc()
        final = int(getattr(self.request, "retries", 0)) >= int(getattr(self, "max_retries", 3))
        asyncio.run(_fail(job_id, str(exc), tb, final))
        structlog.contextvars.clear_contextvars()
        raise


@celery_app.task(bind=True, autoretry_for=(TimeoutError, ConnectionError), retry_backoff=True, retry_jitter=True, max_retries=3)
def run_published_monitor_scan(self: Task, job_id: str) -> dict:
    try:
        result = asyncio.run(_run_published_monitor(job_id))
        asyncio.run(_complete(job_id, result))
        structlog.contextvars.clear_contextvars()
        return {"ok": True}
    except Exception as exc:  # noqa: BLE001
        tb = traceback.format_exc()
        final = int(getattr(self.request, "retries", 0)) >= int(getattr(self, "max_retries", 3))
        asyncio.run(_fail(job_id, str(exc), tb, final))
        structlog.contextvars.clear_contextvars()
        raise


@celery_app.task(bind=True, autoretry_for=(TimeoutError, ConnectionError), retry_backoff=True, retry_jitter=True, max_retries=5)
def run_msi_job(self: Task, job_id: str) -> dict:
    try:
        result = asyncio.run(_run_msi_job(job_id))
        asyncio.run(_complete(job_id, result))
        structlog.contextvars.clear_contextvars()
        return {"ok": True}
    except Exception as exc:  # noqa: BLE001
        tb = traceback.format_exc()
        final = int(getattr(self.request, "retries", 0)) >= int(getattr(self, "max_retries", 5))
        asyncio.run(_fail(job_id, str(exc), tb, final))
        structlog.contextvars.clear_contextvars()
        raise


@celery_app.task(bind=True, autoretry_for=(TimeoutError, ConnectionError), retry_backoff=True, retry_jitter=True, max_retries=5)
def run_simulator_job(self: Task, job_id: str) -> dict:
    try:
        result = asyncio.run(_run_simulator_job(job_id))
        asyncio.run(_complete(job_id, result))
        structlog.contextvars.clear_contextvars()
        return {"ok": True}
    except Exception as exc:  # noqa: BLE001
        tb = traceback.format_exc()
        final = int(getattr(self.request, "retries", 0)) >= int(getattr(self, "max_retries", 5))
        asyncio.run(_fail(job_id, str(exc), tb, final))
        structlog.contextvars.clear_contextvars()
        raise
