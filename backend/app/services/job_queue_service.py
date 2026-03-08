"""Queue orchestration service (enqueue/status/backpressure/dead-letter)."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from redis.asyncio import Redis
from sqlalchemy import and_, case, desc, func, select
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
    "ai_scripts": settings.queue_depth_limit_scripts,
}

QUEUE_SLA_TARGETS = {
    "ai_router": settings.queue_sla_target_minutes_router,
    "ai_scribe": settings.queue_sla_target_minutes_scribe,
    "ai_quality": settings.queue_sla_target_minutes_quality,
    "ai_simulator": settings.queue_sla_target_minutes_simulator,
    "ai_msi": settings.queue_sla_target_minutes_msi,
    "ai_links": settings.queue_sla_target_minutes_links,
    "ai_trends": settings.queue_sla_target_minutes_trends,
    "ai_scripts": settings.queue_sla_target_minutes_scripts,
}

JOB_TASK_MAP: dict[str, tuple[str, str]] = {
    "msi_run": ("app.queue.tasks.pipeline_tasks.run_msi_job", "ai_msi"),
    "simulator_run": ("app.queue.tasks.pipeline_tasks.run_simulator_job", "ai_simulator"),
    "editorial_rewrite": ("app.queue.tasks.ai_tasks.run_editorial_ai_job", "ai_quality"),
    "editorial_proofread": ("app.queue.tasks.ai_tasks.run_editorial_ai_job", "ai_quality"),
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
    "document_intel_extract": ("app.queue.tasks.pipeline_tasks.run_document_intel_extract_job", "ai_quality"),
    "script_generate": ("app.queue.tasks.pipeline_tasks.run_script_generate_job", "ai_scripts"),
    "echorouk_archive_backfill": ("app.queue.tasks.pipeline_tasks.run_echorouk_archive_backfill", "ai_scripts"),
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
        limit = self.queue_depth_limit(queue_name)
        return depth < limit, depth, limit

    def queue_depth_limit(self, queue_name: str) -> int:
        return int(QUEUE_LIMITS.get(queue_name, settings.queue_depth_limit_default))

    def queue_sla_target_minutes(self, queue_name: str) -> int:
        return int(QUEUE_SLA_TARGETS.get(queue_name, settings.queue_sla_target_minutes_default))

    def build_backpressure_detail(
        self,
        *,
        queue_name: str,
        current_depth: int,
        depth_limit: int,
        retry_after_seconds: int | None = None,
        message: str | None = None,
    ) -> dict[str, Any]:
        retry_after = int(retry_after_seconds or settings.queue_backpressure_retry_after_seconds)
        detail: dict[str, Any] = {
            "queue_name": queue_name,
            "current_depth": int(current_depth),
            "depth_limit": int(depth_limit),
            "retry_after_seconds": max(1, retry_after),
        }
        if message:
            detail["message"] = message
        return detail

    def backpressure_exception(
        self,
        *,
        queue_name: str,
        current_depth: int,
        depth_limit: int,
        retry_after_seconds: int | None = None,
        message: str | None = None,
    ) -> HTTPException:
        detail = self.build_backpressure_detail(
            queue_name=queue_name,
            current_depth=current_depth,
            depth_limit=depth_limit,
            retry_after_seconds=retry_after_seconds,
            message=message,
        )
        return HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=detail,
            headers={"Retry-After": str(detail["retry_after_seconds"])},
        )

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
        # Force a fresh read to avoid returning stale ORM identity-map values
        # while another worker updates the same row.
        row = await db.execute(
            select(JobRun).where(JobRun.id == job_uuid).execution_options(populate_existing=True)
        )
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

    async def queue_sla_overview(self, db: AsyncSession, *, lookback_hours: int = 24) -> dict[str, Any]:
        window_hours = max(1, min(int(lookback_hours), 168))
        window_start = datetime.utcnow() - timedelta(hours=window_hours)
        stale_timeout_failed = and_(
            JobRun.status == "failed",
            JobRun.error.is_not(None),
            JobRun.error.ilike("stale_timeout:%"),
        )

        runtime_rows = await db.execute(
            select(
                JobRun.queue_name,
                func.avg(
                    case(
                        (
                            JobRun.status == "completed",
                            func.extract("epoch", JobRun.finished_at - JobRun.started_at),
                        ),
                        else_=None,
                    )
                ).label("avg_runtime_seconds"),
                func.sum(case((stale_timeout_failed, 0), else_=1)).label("finished_count"),
                func.sum(
                    case(
                        (
                            and_(
                                JobRun.status.in_(("failed", "dead_lettered")),
                                ~stale_timeout_failed,
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ).label("failed_count"),
                func.sum(case((stale_timeout_failed, 1), else_=0)).label("stale_excluded_count"),
            )
            .where(
                JobRun.status.in_(("completed", "failed", "dead_lettered")),
                JobRun.finished_at.is_not(None),
                JobRun.finished_at >= window_start,
            )
            .group_by(JobRun.queue_name)
        )
        runtime_by_queue: dict[str, dict[str, float]] = {}
        for queue_name, avg_runtime_seconds, finished_count, failed_count, stale_excluded_count in runtime_rows.all():
            finished = int(finished_count or 0)
            failed = int(failed_count or 0)
            stale_excluded = int(stale_excluded_count or 0)
            failure_rate = round((failed / finished) * 100.0, 2) if finished else 0.0
            mean_runtime_minutes = round((float(avg_runtime_seconds or 0.0) / 60.0), 2)
            runtime_by_queue[str(queue_name)] = {
                "mean_runtime": mean_runtime_minutes,
                "failure_rate_24h": failure_rate,
                "stale_failures_excluded_24h": float(stale_excluded),
            }

        running_rows = await db.execute(
            select(
                JobRun.queue_name,
                func.count(JobRun.id).label("running_count"),
                func.min(func.coalesce(JobRun.started_at, JobRun.queued_at)).label("oldest_running_at"),
            )
            .where(
                JobRun.status == "running",
                JobRun.finished_at.is_(None),
            )
            .group_by(JobRun.queue_name)
        )
        queued_rows = await db.execute(
            select(
                JobRun.queue_name,
                func.count(JobRun.id).label("queued_count"),
                func.min(JobRun.queued_at).label("oldest_queued_at"),
            )
            .where(
                JobRun.status == "queued",
                JobRun.finished_at.is_(None),
            )
            .group_by(JobRun.queue_name)
        )

        now = datetime.utcnow()
        running_by_queue: dict[str, dict[str, float]] = {}
        for queue_name, running_count, oldest_running_at in running_rows.all():
            age_minutes = 0.0
            if oldest_running_at:
                age_minutes = max(0.0, (now - oldest_running_at).total_seconds() / 60.0)
            running_by_queue[str(queue_name)] = {
                "count": int(running_count or 0),
                "oldest_age": round(age_minutes, 2),
            }

        queued_by_queue: dict[str, dict[str, float]] = {}
        for queue_name, queued_count, oldest_queued_at in queued_rows.all():
            age_minutes = 0.0
            if oldest_queued_at:
                age_minutes = max(0.0, (now - oldest_queued_at).total_seconds() / 60.0)
            queued_by_queue[str(queue_name)] = {
                "count": int(queued_count or 0),
                "oldest_age": round(age_minutes, 2),
            }

        depths = await self.queue_depths()
        queue_names = sorted(set(depths.keys()) | set(runtime_by_queue.keys()) | set(running_by_queue.keys()) | set(queued_by_queue.keys()))
        failure_threshold = float(settings.queue_sla_failure_rate_threshold_percent)
        items: list[dict[str, Any]] = []
        for queue_name in queue_names:
            depth = int(depths.get(queue_name, 0))
            depth_limit = self.queue_depth_limit(queue_name)
            running_stats = running_by_queue.get(queue_name, {})
            queued_stats = queued_by_queue.get(queue_name, {})
            running_count = int(running_stats.get("count", 0))
            queued_count = int(queued_stats.get("count", 0))
            oldest_running_age = float(running_stats.get("oldest_age", 0.0))
            oldest_queued_age = float(queued_stats.get("oldest_age", 0.0))

            # If Redis depth is zero, queued rows in DB often indicate stale state.
            # In that case we only use running age, because queued-age SLA should track
            # real backlog pressure from Redis.
            if depth > 0:
                oldest_task_age = round(max(oldest_queued_age, oldest_running_age), 2)
            elif running_count > 0:
                oldest_task_age = round(oldest_running_age, 2)
            else:
                oldest_task_age = 0.0

            state_drift_suspected = depth == 0 and queued_count > 0
            runtime_stats = runtime_by_queue.get(queue_name, {})
            mean_runtime = float(runtime_stats.get("mean_runtime", 0.0))
            failure_rate_24h = float(runtime_stats.get("failure_rate_24h", 0.0))
            stale_failures_excluded_24h = int(runtime_stats.get("stale_failures_excluded_24h", 0.0))
            sla_target_minutes = self.queue_sla_target_minutes(queue_name)
            depth_breach = depth >= depth_limit
            age_breach = oldest_task_age > sla_target_minutes
            runtime_breach = mean_runtime > sla_target_minutes
            failure_breach = failure_rate_24h >= failure_threshold
            sla_breached = depth_breach or age_breach or runtime_breach or failure_breach
            items.append(
                {
                    "queue_name": queue_name,
                    "depth": depth,
                    "depth_limit": depth_limit,
                    "oldest_task_age": oldest_task_age,
                    "mean_runtime": mean_runtime,
                    "failure_rate_24h": failure_rate_24h,
                    "stale_failures_excluded_24h": stale_failures_excluded_24h,
                    "SLA_target_minutes": sla_target_minutes,
                    "SLA_breached": sla_breached,
                    "active_running_jobs": running_count,
                    "active_queued_jobs": queued_count,
                    "state_drift_suspected": state_drift_suspected,
                }
            )

        return {
            "generated_at": datetime.utcnow().isoformat(),
            "lookback_hours": window_hours,
            "failure_rate_threshold_percent": failure_threshold,
            "queues": items,
        }

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
