"""Queue orchestration service (enqueue/status/backpressure/dead-letter)."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.correlation import get_correlation_id, get_request_id
from app.core.logging import get_logger
from app.models import DeadLetterJob, JobRun
from app.queue.celery_app import celery_app

logger = get_logger("services.job_queue")
settings = get_settings()


QUEUE_LIMITS = {
    "ai_router": settings.queue_depth_limit_router,
    "ai_scribe": settings.queue_depth_limit_scribe,
    "ai_quality": settings.queue_depth_limit_quality,
    "ai_simulator": settings.queue_depth_limit_simulator,
    "ai_msi": settings.queue_depth_limit_msi,
    "ai_links": settings.queue_depth_limit_links,
    "ai_trends": settings.queue_depth_limit_trends,
}

JOB_TASK_MAP: dict[str, tuple[str, str]] = {
    "msi_run": ("app.queue.tasks.pipeline_tasks.run_msi_job", "ai_msi"),
    "simulator_run": ("app.queue.tasks.pipeline_tasks.run_simulator_job", "ai_simulator"),
    "editorial_rewrite": ("app.queue.tasks.ai_tasks.run_editorial_ai_job", "ai_quality"),
    "editorial_headlines": ("app.queue.tasks.ai_tasks.run_editorial_ai_job", "ai_quality"),
    "editorial_seo": ("app.queue.tasks.ai_tasks.run_editorial_ai_job", "ai_quality"),
    "editorial_social": ("app.queue.tasks.ai_tasks.run_editorial_ai_job", "ai_quality"),
    "editorial_claims": ("app.queue.tasks.ai_tasks.run_editorial_ai_job", "ai_quality"),
    "editorial_quality": ("app.queue.tasks.ai_tasks.run_editorial_ai_job", "ai_quality"),
    "editorial_links_suggest": ("app.queue.tasks.ai_tasks.run_editorial_links_job", "ai_links"),
    "editorial_ai_apply": ("app.queue.tasks.ai_tasks.run_editorial_ai_job", "ai_quality"),
    "pipeline_scout": ("app.queue.tasks.pipeline_tasks.run_scout_batch", "ai_router"),
    "pipeline_router": ("app.queue.tasks.pipeline_tasks.run_router_batch", "ai_router"),
    "pipeline_scribe": ("app.queue.tasks.pipeline_tasks.run_scribe_batch", "ai_scribe"),
    "trends_scan": ("app.queue.tasks.pipeline_tasks.run_trends_scan", "ai_trends"),
    "published_monitor_scan": ("app.queue.tasks.pipeline_tasks.run_published_monitor_scan", "ai_quality"),
}


class JobQueueService:
    def __init__(self) -> None:
        self._redis: Redis | None = None

    async def _redis_client(self) -> Redis:
        if self._redis is None:
            self._redis = Redis.from_url(settings.redis_queue_url, decode_responses=True)
        return self._redis

    async def queue_depth(self, queue_name: str) -> int:
        redis = await self._redis_client()
        # Celery Redis transport stores pending messages under list key with queue name.
        return int(await redis.llen(queue_name))

    async def check_backpressure(self, queue_name: str) -> tuple[bool, int, int]:
        if not settings.queue_backpressure_enabled:
            return True, 0, 0
        depth = await self.queue_depth(queue_name)
        limit = QUEUE_LIMITS.get(queue_name, settings.queue_depth_limit_default)
        return depth < limit, depth, limit

    async def create_job(
        self,
        db: AsyncSession,
        *,
        job_type: str,
        queue_name: str,
        payload: dict[str, Any],
        entity_id: str | None = None,
        request_id: str | None = None,
        correlation_id: str | None = None,
        actor_user_id: int | None = None,
        actor_username: str | None = None,
        priority: str = "normal",
        max_attempts: int = 5,
    ) -> JobRun:
        request_id = request_id or get_request_id() or None
        correlation_id = correlation_id or get_correlation_id() or None
        job = JobRun(
            job_type=job_type,
            queue_name=queue_name,
            entity_id=entity_id,
            status="queued",
            priority=priority,
            request_id=request_id,
            correlation_id=correlation_id,
            actor_user_id=actor_user_id,
            actor_username=actor_username,
            max_attempts=max_attempts,
            payload_json=payload,
            queued_at=datetime.utcnow(),
        )
        db.add(job)
        await db.flush()
        await db.commit()
        await db.refresh(job)
        return job

    async def mark_stale_jobs_failed(
        self,
        db: AsyncSession,
        *,
        stale_running_minutes: int = 15,
        stale_queued_minutes: int = 30,
        reason: str = "stale_timeout",
    ) -> dict[str, int]:
        now = datetime.utcnow()
        running_cutoff = now - timedelta(minutes=max(1, stale_running_minutes))
        queued_cutoff = now - timedelta(minutes=max(1, stale_queued_minutes))
        updated = {"running_failed": 0, "queued_failed": 0}

        running_rows = await db.execute(
            select(JobRun).where(
                JobRun.status == "running",
                JobRun.started_at.is_not(None),
                JobRun.started_at <= running_cutoff,
                JobRun.finished_at.is_(None),
            )
        )
        stale_running = list(running_rows.scalars().all())
        for job in stale_running:
            job.status = "failed"
            job.error = f"{reason}:running>{stale_running_minutes}m"
            job.finished_at = now
            updated["running_failed"] += 1

        queued_rows = await db.execute(
            select(JobRun).where(
                JobRun.status == "queued",
                JobRun.started_at.is_(None),
                JobRun.queued_at <= queued_cutoff,
                JobRun.finished_at.is_(None),
            )
        )
        stale_queued = list(queued_rows.scalars().all())
        for job in stale_queued:
            job.status = "failed"
            job.error = f"{reason}:queued>{stale_queued_minutes}m"
            job.finished_at = now
            updated["queued_failed"] += 1

        if updated["running_failed"] or updated["queued_failed"]:
            await db.commit()
        return updated

    async def enqueue(self, *, task_name: str, queue_name: str, job_id: str) -> None:
        celery_app.send_task(task_name, kwargs={"job_id": job_id}, queue=queue_name)
        logger.info("job_enqueued", task_name=task_name, queue=queue_name, job_id=job_id)

    async def enqueue_by_job_type(self, *, job_type: str, job_id: str) -> None:
        task_cfg = JOB_TASK_MAP.get(job_type)
        if not task_cfg:
            raise ValueError(f"unsupported_job_type:{job_type}")
        task_name, queue_name = task_cfg
        await self.enqueue(task_name=task_name, queue_name=queue_name, job_id=job_id)

    async def get_job(self, db: AsyncSession, job_id: str) -> JobRun | None:
        try:
            job_uuid = UUID(job_id)
        except Exception:  # noqa: BLE001
            return None
        row = await db.execute(select(JobRun).where(JobRun.id == job_uuid))
        return row.scalar_one_or_none()

    async def list_jobs(
        self,
        db: AsyncSession,
        *,
        limit: int = 50,
        status: str | None = None,
        job_type: str | None = None,
    ) -> list[JobRun]:
        stmt = select(JobRun)
        if status:
            stmt = stmt.where(JobRun.status == status)
        if job_type:
            stmt = stmt.where(JobRun.job_type == job_type)
        stmt = stmt.order_by(desc(JobRun.queued_at)).limit(max(1, min(limit, 200)))
        rows = await db.execute(stmt)
        return list(rows.scalars().all())

    async def find_active_job(
        self,
        db: AsyncSession,
        *,
        job_type: str,
        entity_id: str | None = None,
        max_age_minutes: int = 30,
    ) -> JobRun | None:
        cutoff = datetime.utcnow() - timedelta(minutes=max(1, max_age_minutes))
        stmt = select(JobRun).where(
            JobRun.job_type == job_type,
            JobRun.status.in_(("queued", "running")),
            JobRun.queued_at >= cutoff,
        )
        if entity_id:
            stmt = stmt.where(JobRun.entity_id == entity_id)
        stmt = stmt.order_by(desc(JobRun.queued_at)).limit(1)
        rows = await db.execute(stmt)
        return rows.scalar_one_or_none()

    async def queue_depths(self) -> dict[str, int]:
        queue_names = sorted(set(list(QUEUE_LIMITS.keys()) + [settings.queue_default_name]))
        depths: dict[str, int] = {}
        for queue_name in queue_names:
            try:
                depths[queue_name] = await self.queue_depth(queue_name)
            except Exception:  # noqa: BLE001
                depths[queue_name] = -1
        return depths

    async def mark_running(self, db: AsyncSession, job: JobRun) -> None:
        job.status = "running"
        job.attempt = int(job.attempt or 0) + 1
        job.started_at = datetime.utcnow()
        await db.commit()

    async def mark_completed(self, db: AsyncSession, job: JobRun, result: dict[str, Any]) -> None:
        job.status = "completed"
        job.result_json = result
        job.finished_at = datetime.utcnow()
        await db.commit()

    async def mark_failed(self, db: AsyncSession, job: JobRun, error: str) -> None:
        job.status = "failed"
        job.error = error[:4000]
        job.finished_at = datetime.utcnow()
        await db.commit()

    async def dead_letter(self, db: AsyncSession, *, job: JobRun, error: str, traceback_text: str | None = None) -> None:
        dlq = DeadLetterJob(
            original_job_id=job.id,
            job_type=job.job_type,
            queue_name=job.queue_name,
            error=error[:4000],
            traceback=traceback_text[:16000] if traceback_text else None,
            payload_json=job.payload_json or {},
            meta_json={"attempt": job.attempt, "max_attempts": job.max_attempts},
        )
        db.add(dlq)
        job.status = "dead_lettered"
        job.error = error[:4000]
        job.finished_at = datetime.utcnow()
        await db.commit()


job_queue_service = JobQueueService()
