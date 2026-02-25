"""Pipeline and graph tasks executed in workers."""

from __future__ import annotations

import traceback
from collections.abc import Awaitable, Callable
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
from app.queue.async_runtime import run_async
from app.queue.celery_app import celery_app
from app.services.document_intel_job_storage import document_intel_job_storage
from app.services.document_intel_service import document_intel_service
from app.services.job_queue_service import job_queue_service
from app.services.task_execution_service import execute_with_task_idempotency
from app.simulator.service import audience_simulation_service

logger = get_logger("queue.pipeline_tasks")
DEFAULT_TASK_SOFT_LIMIT_SEC = 120
DEFAULT_TASK_HARD_LIMIT_SEC = 180


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


async def _run_task_with_idempotency(
    job_id: str,
    *,
    task_name: str,
    runner: Callable[[JobRun], Awaitable[dict]],
) -> dict:
    job = await _load_job(job_id)
    logger.info(
        "task_execution_started",
        task_name=task_name,
        job_id=job_id,
        entity_id=job.entity_id,
        queue_name=job.queue_name,
    )
    result = await execute_with_task_idempotency(
        job=job,
        task_name=task_name,
        runner=lambda: runner(job),
    )
    logger.info(
        "task_execution_completed",
        task_name=task_name,
        job_id=job_id,
        entity_id=job.entity_id,
    )
    return result


async def _run_router_batch(_: JobRun) -> dict:
    async with async_session() as db:
        stats = await router_agent.process_batch(db)
    return {"stats": stats}


async def _run_scout_batch(_: JobRun) -> dict:
    async with async_session() as db:
        stats = await scout_agent.run(db)
        router_stats = await router_agent.process_batch(db)
    return {"scout": stats, "router": router_stats}


async def _run_scribe_batch(_: JobRun) -> dict:
    async with async_session() as db:
        stats = await scribe_agent.batch_write(db)
    return {"stats": stats}


async def _run_msi_job(job: JobRun) -> dict:
    run_id = str((job.payload_json or {}).get("run_id") or "")
    if not run_id:
        raise RuntimeError("run_id_missing")
    await msi_monitor_service.execute_run(run_id)
    return {"run_id": run_id, "status": "completed"}


async def _run_simulator_job(job: JobRun) -> dict:
    run_id = str((job.payload_json or {}).get("run_id") or "")
    if not run_id:
        raise RuntimeError("run_id_missing")
    await audience_simulation_service.execute_run(run_id)
    return {"run_id": run_id, "status": "completed"}


async def _run_trends_scan(job: JobRun) -> dict:
    payload = job.payload_json or {}
    alerts = await trend_radar_agent.scan(
        geo=str(payload.get("geo") or "DZ"),
        category=str(payload.get("category") or "all"),
        limit=int(payload.get("limit") or 12),
        mode=str(payload.get("mode") or "fast"),
    )
    return {"alerts_count": len(alerts), "alerts": [a.model_dump(mode="json") for a in alerts]}


async def _run_published_monitor(job: JobRun) -> dict:
    payload = job.payload_json or {}
    report = await published_content_monitor_agent.scan(
        feed_url=payload.get("feed_url"),
        limit=payload.get("limit"),
    )
    return {"report": report}


async def _run_document_intel_extract(job: JobRun) -> dict:
    payload = job.payload_json or {}
    blob_key = str(payload.get("blob_key") or "")
    if not blob_key:
        raise RuntimeError("document_intel_blob_key_missing")

    raw_pdf = await document_intel_job_storage.load_payload(blob_key)
    if not raw_pdf:
        raise RuntimeError("document_intel_payload_missing_or_expired")

    try:
        result = await document_intel_service.extract_pdf(
            filename=str(payload.get("filename") or "document.pdf"),
            payload=raw_pdf,
            language_hint=str(payload.get("language_hint") or "ar"),
            max_news_items=int(payload.get("max_news_items") or 8),
            max_data_points=int(payload.get("max_data_points") or 30),
        )
        return result
    finally:
        await document_intel_job_storage.delete_payload(blob_key)


@celery_app.task(
    bind=True,
    autoretry_for=(TimeoutError, ConnectionError),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=5,
    soft_time_limit=DEFAULT_TASK_SOFT_LIMIT_SEC,
    time_limit=DEFAULT_TASK_HARD_LIMIT_SEC,
)
def run_router_batch(self: Task, job_id: str) -> dict:
    try:
        result = run_async(
            _run_task_with_idempotency(
                job_id,
                task_name="pipeline_router",
                runner=_run_router_batch,
            )
        )
        run_async(_complete(job_id, result))
        return {"ok": True}
    except Exception as exc:  # noqa: BLE001
        tb = traceback.format_exc()
        final = int(getattr(self.request, "retries", 0)) >= int(getattr(self, "max_retries", 5))
        run_async(_fail(job_id, str(exc), tb, final))
        raise
    finally:
        structlog.contextvars.clear_contextvars()


@celery_app.task(
    bind=True,
    autoretry_for=(TimeoutError, ConnectionError),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=3,
    soft_time_limit=DEFAULT_TASK_SOFT_LIMIT_SEC,
    time_limit=DEFAULT_TASK_HARD_LIMIT_SEC,
)
def run_scout_batch(self: Task, job_id: str) -> dict:
    try:
        result = run_async(
            _run_task_with_idempotency(
                job_id,
                task_name="pipeline_scout",
                runner=_run_scout_batch,
            )
        )
        run_async(_complete(job_id, result))
        return {"ok": True}
    except Exception as exc:  # noqa: BLE001
        tb = traceback.format_exc()
        final = int(getattr(self.request, "retries", 0)) >= int(getattr(self, "max_retries", 3))
        run_async(_fail(job_id, str(exc), tb, final))
        raise
    finally:
        structlog.contextvars.clear_contextvars()


@celery_app.task(
    bind=True,
    autoretry_for=(TimeoutError, ConnectionError),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=5,
    soft_time_limit=DEFAULT_TASK_SOFT_LIMIT_SEC,
    time_limit=DEFAULT_TASK_HARD_LIMIT_SEC,
)
def run_scribe_batch(self: Task, job_id: str) -> dict:
    try:
        result = run_async(
            _run_task_with_idempotency(
                job_id,
                task_name="pipeline_scribe",
                runner=_run_scribe_batch,
            )
        )
        run_async(_complete(job_id, result))
        return {"ok": True}
    except Exception as exc:  # noqa: BLE001
        tb = traceback.format_exc()
        final = int(getattr(self.request, "retries", 0)) >= int(getattr(self, "max_retries", 5))
        run_async(_fail(job_id, str(exc), tb, final))
        raise
    finally:
        structlog.contextvars.clear_contextvars()


@celery_app.task(
    bind=True,
    autoretry_for=(TimeoutError, ConnectionError),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=3,
    soft_time_limit=DEFAULT_TASK_SOFT_LIMIT_SEC,
    time_limit=DEFAULT_TASK_HARD_LIMIT_SEC,
)
def run_trends_scan(self: Task, job_id: str) -> dict:
    try:
        result = run_async(
            _run_task_with_idempotency(
                job_id,
                task_name="trends_scan",
                runner=_run_trends_scan,
            )
        )
        run_async(_complete(job_id, result))
        return {"ok": True}
    except Exception as exc:  # noqa: BLE001
        tb = traceback.format_exc()
        final = int(getattr(self.request, "retries", 0)) >= int(getattr(self, "max_retries", 3))
        run_async(_fail(job_id, str(exc), tb, final))
        raise
    finally:
        structlog.contextvars.clear_contextvars()


@celery_app.task(
    bind=True,
    autoretry_for=(TimeoutError, ConnectionError),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=3,
    soft_time_limit=DEFAULT_TASK_SOFT_LIMIT_SEC,
    time_limit=DEFAULT_TASK_HARD_LIMIT_SEC,
)
def run_published_monitor_scan(self: Task, job_id: str) -> dict:
    try:
        result = run_async(
            _run_task_with_idempotency(
                job_id,
                task_name="published_monitor_scan",
                runner=_run_published_monitor,
            )
        )
        run_async(_complete(job_id, result))
        return {"ok": True}
    except Exception as exc:  # noqa: BLE001
        tb = traceback.format_exc()
        final = int(getattr(self.request, "retries", 0)) >= int(getattr(self, "max_retries", 3))
        run_async(_fail(job_id, str(exc), tb, final))
        raise
    finally:
        structlog.contextvars.clear_contextvars()


@celery_app.task(
    bind=True,
    autoretry_for=(TimeoutError, ConnectionError),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=5,
    soft_time_limit=DEFAULT_TASK_SOFT_LIMIT_SEC,
    time_limit=DEFAULT_TASK_HARD_LIMIT_SEC,
)
def run_msi_job(self: Task, job_id: str) -> dict:
    try:
        result = run_async(
            _run_task_with_idempotency(
                job_id,
                task_name="msi_run",
                runner=_run_msi_job,
            )
        )
        run_async(_complete(job_id, result))
        return {"ok": True}
    except Exception as exc:  # noqa: BLE001
        tb = traceback.format_exc()
        final = int(getattr(self.request, "retries", 0)) >= int(getattr(self, "max_retries", 5))
        run_async(_fail(job_id, str(exc), tb, final))
        raise
    finally:
        structlog.contextvars.clear_contextvars()


@celery_app.task(
    bind=True,
    autoretry_for=(TimeoutError, ConnectionError),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=5,
    soft_time_limit=DEFAULT_TASK_SOFT_LIMIT_SEC,
    time_limit=DEFAULT_TASK_HARD_LIMIT_SEC,
)
def run_simulator_job(self: Task, job_id: str) -> dict:
    try:
        result = run_async(
            _run_task_with_idempotency(
                job_id,
                task_name="simulator_run",
                runner=_run_simulator_job,
            )
        )
        run_async(_complete(job_id, result))
        return {"ok": True}
    except Exception as exc:  # noqa: BLE001
        tb = traceback.format_exc()
        final = int(getattr(self.request, "retries", 0)) >= int(getattr(self, "max_retries", 5))
        run_async(_fail(job_id, str(exc), tb, final))
        raise
    finally:
        structlog.contextvars.clear_contextvars()


@celery_app.task(
    bind=True,
    autoretry_for=(TimeoutError, ConnectionError),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=2,
    soft_time_limit=DEFAULT_TASK_SOFT_LIMIT_SEC,
    time_limit=DEFAULT_TASK_HARD_LIMIT_SEC,
)
def run_document_intel_extract_job(self: Task, job_id: str) -> dict:
    try:
        result = run_async(
            _run_task_with_idempotency(
                job_id,
                task_name="document_intel_extract",
                runner=_run_document_intel_extract,
            )
        )
        run_async(_complete(job_id, result))
        return {"ok": True}
    except Exception as exc:  # noqa: BLE001
        tb = traceback.format_exc()
        final = int(getattr(self.request, "retries", 0)) >= int(getattr(self, "max_retries", 2))
        run_async(_fail(job_id, str(exc), tb, final))
        raise
    finally:
        structlog.contextvars.clear_contextvars()
