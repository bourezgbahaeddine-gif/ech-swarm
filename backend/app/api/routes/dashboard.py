"""
Echorouk Editorial OS - Dashboard & Agent Control API.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select, func, and_, update, desc, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.config import get_settings
from app.core.correlation import get_correlation_id, get_request_id
from app.core.logging import get_logger
from app.models import Article, Source, PipelineRun, FailedJob, NewsStatus, UrgencyLevel, JobRun
from app.models.user import User, UserRole
from app.api.routes.auth import get_current_user
from app.schemas import DashboardStats, PipelineRunResponse
from app.services.cache_service import cache_service
from app.agents import published_content_monitor_agent
from app.services.event_reminder_service import event_reminder_service
from app.services.job_queue_service import job_queue_service

logger = get_logger("api.dashboard")
router = APIRouter(prefix="/dashboard", tags=["Dashboard"])
settings = get_settings()


async def _expire_stale_breaking_flags(db: AsyncSession) -> None:
    cutoff = datetime.utcnow() - timedelta(minutes=settings.breaking_news_ttl_minutes)
    await db.execute(
        update(Article)
        .where(
            and_(
                Article.is_breaking == True,
                func.coalesce(Article.published_at, Article.crawled_at) < cutoff,
            )
        )
        .values(
            is_breaking=False,
            urgency=UrgencyLevel.HIGH,
            updated_at=datetime.utcnow(),
        )
    )
    await db.commit()


@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(db: AsyncSession = Depends(get_db)):
    """Get real-time dashboard statistics."""
    await _expire_stale_breaking_flags(db)
    cached = await cache_service.get_json("dashboard:stats")
    if cached:
        return DashboardStats(**cached)

    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    breaking_cutoff = datetime.utcnow() - timedelta(minutes=settings.breaking_news_ttl_minutes)

    total = await db.execute(select(func.count(Article.id)))
    today_count = await db.execute(
        select(func.count(Article.id)).where(Article.crawled_at >= today)
    )
    pending = await db.execute(
        select(func.count(Article.id)).where(Article.status == NewsStatus.CANDIDATE)
    )
    approved = await db.execute(
        select(func.count(Article.id)).where(Article.status == NewsStatus.APPROVED)
    )
    rejected = await db.execute(
        select(func.count(Article.id)).where(Article.status == NewsStatus.REJECTED)
    )
    published = await db.execute(
        select(func.count(Article.id)).where(Article.status == NewsStatus.PUBLISHED)
    )
    breaking = await db.execute(
        select(func.count(Article.id)).where(
            and_(
                Article.is_breaking == True,
                func.coalesce(Article.published_at, Article.crawled_at) >= breaking_cutoff,
                Article.status.in_([NewsStatus.NEW, NewsStatus.CLASSIFIED, NewsStatus.CANDIDATE]),
            )
        )
    )

    sources_active = await db.execute(
        select(func.count(Source.id)).where(Source.enabled == True)
    )
    sources_total = await db.execute(select(func.count(Source.id)))
    ai_calls = await cache_service.get_counter("ai_calls_today")
    avg_time = await db.execute(
        select(func.avg(Article.processing_time_ms))
        .where(Article.processing_time_ms.isnot(None))
    )

    stats = DashboardStats(
        total_articles=total.scalar() or 0,
        articles_today=today_count.scalar() or 0,
        pending_review=pending.scalar() or 0,
        approved=approved.scalar() or 0,
        rejected=rejected.scalar() or 0,
        published=published.scalar() or 0,
        breaking_news=breaking.scalar() or 0,
        sources_active=sources_active.scalar() or 0,
        sources_total=sources_total.scalar() or 0,
        ai_calls_today=ai_calls,
        avg_processing_ms=avg_time.scalar(),
    )
    await cache_service.set_json("dashboard:stats", stats.model_dump(), ttl=timedelta(seconds=30))
    return stats


@router.get("/pipeline-runs", response_model=list[PipelineRunResponse])
async def get_pipeline_runs(
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """Get recent pipeline execution logs."""
    result = await db.execute(
        select(PipelineRun)
        .order_by(PipelineRun.started_at.desc())
        .limit(limit)
    )
    runs = result.scalars().all()
    return [PipelineRunResponse.model_validate(r) for r in runs]


@router.get("/ops/overview")
async def get_operational_overview(
    lookback_hours: int = Query(24, ge=1, le=168),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lightweight operational telemetry from existing run tables."""
    _assert_agent_control_permission(current_user)
    window_start = datetime.utcnow() - timedelta(hours=lookback_hours)

    job_counts_rows = await db.execute(
        select(JobRun.job_type, func.count(JobRun.id))
        .where(
            JobRun.status == "completed",
            JobRun.finished_at.is_not(None),
            JobRun.finished_at >= window_start,
        )
        .group_by(JobRun.job_type)
        .order_by(func.count(JobRun.id).desc())
    )
    throughput = [
        {"job_type": job_type, "completed": int(count or 0)}
        for job_type, count in job_counts_rows.all()
    ]

    job_latency_rows = await db.execute(
        select(
            JobRun.job_type,
            func.avg(func.extract("epoch", JobRun.finished_at - JobRun.started_at)).label("avg_seconds"),
        )
        .where(
            JobRun.status == "completed",
            JobRun.started_at.is_not(None),
            JobRun.finished_at.is_not(None),
            JobRun.finished_at >= window_start,
        )
        .group_by(JobRun.job_type)
        .order_by(func.avg(func.extract("epoch", JobRun.finished_at - JobRun.started_at)).desc())
    )
    latency = [
        {"job_type": job_type, "avg_seconds": round(float(avg_seconds or 0.0), 2)}
        for job_type, avg_seconds in job_latency_rows.all()
    ]

    failures_rows = await db.execute(
        select(JobRun.error, func.count(JobRun.id))
        .where(
            JobRun.status.in_(["failed", "dead_lettered"]),
            JobRun.finished_at.is_not(None),
            JobRun.finished_at >= window_start,
            JobRun.error.is_not(None),
        )
        .group_by(JobRun.error)
        .order_by(func.count(JobRun.id).desc())
        .limit(10)
    )
    failure_distribution: list[dict[str, object]] = []
    for error_text, count in failures_rows.all():
        reason = str(error_text or "unknown").split(":", 1)[0].strip() or "unknown"
        failure_distribution.append({"reason": reason, "count": int(count or 0)})

    pipeline_summary_row = await db.execute(
        select(
            func.count(PipelineRun.id).label("runs"),
            func.avg(func.extract("epoch", PipelineRun.finished_at - PipelineRun.started_at)).label("avg_seconds"),
            func.sum(case((PipelineRun.status == "success", 1), else_=0)).label("success_runs"),
        )
        .where(
            PipelineRun.started_at >= window_start,
            PipelineRun.finished_at.is_not(None),
        )
    )
    pipeline_summary = pipeline_summary_row.one()
    runs_total = int(pipeline_summary.runs or 0)
    success_runs = int(pipeline_summary.success_runs or 0)
    success_rate = round((success_runs / runs_total) * 100.0, 2) if runs_total else 0.0

    state_age_rows = await db.execute(
        select(
            Article.status,
            func.avg(func.extract("epoch", datetime.utcnow() - Article.updated_at)).label("avg_age_seconds"),
            func.count(Article.id).label("count"),
        )
        .group_by(Article.status)
    )
    state_ages = [
        {
            "status": status.value if status else None,
            "avg_age_seconds": round(float(avg_age_seconds or 0.0), 2),
            "count": int(count or 0),
        }
        for status, avg_age_seconds, count in state_age_rows.all()
    ]

    return {
        "lookback_hours": lookback_hours,
        "generated_at": datetime.utcnow().isoformat(),
        "throughput": throughput,
        "latency": latency,
        "pipeline": {
            "runs_total": runs_total,
            "success_runs": success_runs,
            "success_rate_percent": success_rate,
            "avg_run_seconds": round(float(pipeline_summary.avg_seconds or 0.0), 2),
        },
        "failure_reasons": failure_distribution,
        "queue_depth": await job_queue_service.queue_depths(),
        "state_age_seconds": state_ages,
    }


@router.get("/failed-jobs")
async def get_failed_jobs(
    resolved: bool = False,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """Get failed jobs from the Dead Letter Queue."""
    result = await db.execute(
        select(FailedJob)
        .where(FailedJob.resolved == resolved)
        .order_by(FailedJob.created_at.desc())
        .limit(limit)
    )
    jobs = result.scalars().all()
    return [
        {
            "id": j.id,
            "type": j.job_type,
            "error": j.error_message,
            "retries": j.retry_count,
            "created_at": j.created_at.isoformat(),
        }
        for j in jobs
    ]


async def _enqueue_dashboard_job(
    *,
    db: AsyncSession,
    request: Request,
    current_user: User,
    job_type: str,
    queue_name: str,
    payload: dict | None = None,
    entity_id: str | None = None,
) -> dict:
    allowed, depth, limit_depth = await job_queue_service.check_backpressure(queue_name)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=f"Queue busy for {job_type} ({depth}/{limit_depth}). Retry in a moment.",
        )

    payload_data = dict(payload or {})
    payload_data.setdefault("trigger_nonce", uuid4().hex)
    payload_data.setdefault(
        "idempotency_key",
        f"{job_type}:{entity_id or 'dashboard'}:{payload_data['trigger_nonce']}",
    )

    job = await job_queue_service.create_job(
        db,
        job_type=job_type,
        queue_name=queue_name,
        payload=payload_data,
        entity_id=entity_id,
        request_id=request.headers.get("x-request-id") or get_request_id(),
        correlation_id=request.headers.get("x-correlation-id") or get_correlation_id(),
        actor_user_id=current_user.id,
        actor_username=current_user.username,
        max_attempts=3,
    )
    try:
        await job_queue_service.enqueue_by_job_type(job_type=job_type, job_id=str(job.id))
    except Exception as exc:  # noqa: BLE001
        logger.error("dashboard_enqueue_failed", job_type=job_type, error=str(exc))
        await job_queue_service.mark_failed(db, job, f"queue_unavailable:{exc}")
        return {
            "job_id": str(job.id),
            "status": "queue_unavailable",
            "job_type": job_type,
            "message": "Queue unavailable. Retry in a moment.",
        }
    return {"job_id": str(job.id), "status": "queued", "job_type": job_type}


def _assert_agent_control_permission(user: User) -> None:
    if user.role not in {UserRole.director, UserRole.editor_chief}:
        raise HTTPException(status_code=403, detail="غير مسموح لك بتشغيل هذا الوكيل.")


def _assert_newsroom_refresh_permission(user: User) -> None:
    if user.role not in {
        UserRole.director,
        UserRole.editor_chief,
        UserRole.journalist,
        UserRole.social_media,
        UserRole.print_editor,
    }:
        raise HTTPException(status_code=403, detail="غير مسموح لك بتحديث غرفة الأخبار.")


def _assert_trend_permission(user: User) -> None:
    if user.role not in {
        UserRole.director,
        UserRole.editor_chief,
        UserRole.journalist,
        UserRole.social_media,
        UserRole.print_editor,
    }:
        raise HTTPException(status_code=403, detail="غير مسموح لك باستخدام رادار التراند.")


@router.post("/agents/scout/run")
async def trigger_scout(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Enqueue scout pipeline run."""
    _assert_newsroom_refresh_permission(current_user)
    ticket = await _enqueue_dashboard_job(
        db=db,
        request=request,
        current_user=current_user,
        job_type="pipeline_scout",
        queue_name="ai_router",
        payload={"source": "dashboard"},
        entity_id="dashboard_scout",
    )
    return {"message": "Scout queued.", **ticket}


@router.post("/agents/router/run")
async def trigger_router(
    request: Request,
    limit: int = Query(default=settings.router_batch_limit, ge=10, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Enqueue router run."""
    _assert_newsroom_refresh_permission(current_user)
    ticket = await _enqueue_dashboard_job(
        db=db,
        request=request,
        current_user=current_user,
        job_type="pipeline_router",
        queue_name="ai_router",
        payload={"source": "dashboard", "limit": limit},
        entity_id="dashboard_router",
    )
    return {"message": "Router queued.", **ticket}


@router.post("/agents/scribe/run")
async def trigger_scribe(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Enqueue scribe run."""
    _assert_agent_control_permission(current_user)
    ticket = await _enqueue_dashboard_job(
        db=db,
        request=request,
        current_user=current_user,
        job_type="pipeline_scribe",
        queue_name="ai_scribe",
        payload={"source": "dashboard"},
        entity_id="dashboard_scribe",
    )
    return {"message": "Scribe queued.", **ticket}


@router.post("/agents/trends/scan")
async def trigger_trend_scan(
    request: Request,
    db: AsyncSession = Depends(get_db),
    geo: str = Query("DZ", min_length=2, max_length=16),
    category: str = Query("all", min_length=2, max_length=32),
    limit: int = Query(12, ge=1, le=30),
    mode: str = Query("fast", pattern="^(fast|deep)$"),
    current_user: User = Depends(get_current_user),
):
    """Enqueue trend scan run."""
    _assert_trend_permission(current_user)
    geo_upper = geo.upper()
    if geo_upper in {"*", "ALL"}:
        geo_upper = "ALL"
    category_lower = category.lower()
    if geo_upper == "ALL":
        category_lower = "all"
    entity_id = f"trend:{geo_upper}:{category_lower}"
    active = await job_queue_service.find_active_job(
        db,
        job_type="trends_scan",
        entity_id=entity_id,
        max_age_minutes=max(5, settings.trend_radar_interval_minutes * 2),
    )
    if active:
        return {
            "message": "Trends scan already active.",
            "job_id": str(active.id),
            "status": active.status,
            "job_type": "trends_scan",
        }
    ticket = await _enqueue_dashboard_job(
        db=db,
        request=request,
        current_user=current_user,
        job_type="trends_scan",
        queue_name="ai_trends",
        payload={
            "geo": geo_upper,
            "category": category_lower,
            "limit": limit,
            "mode": mode.lower(),
        },
        entity_id=entity_id,
    )
    return {"message": "Trends scan queued.", **ticket}


@router.get("/agents/trends/latest")
async def get_latest_trend_scan(
    request: Request,
    geo: str = Query("ALL", min_length=2, max_length=16),
    category: str = Query("all", min_length=2, max_length=32),
    refresh_if_empty: bool = Query(True),
    refresh_if_stale: bool = Query(True),
    stale_after_minutes: int = Query(120, ge=30, le=360),
    limit: int = Query(12, ge=1, le=30),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Fetch latest cached trend payload (and optionally enqueue refresh)."""
    _assert_trend_permission(current_user)
    geo = geo.upper()
    if geo in {"*", "ALL"}:
        geo = "ALL"
    category = category.lower()
    payload = await cache_service.get_json(f"trends:last:{geo}:{category}")
    if not payload:
        snapshot = await cache_service.get_json("trends:last:ALL:all")
        if snapshot and snapshot.get("alerts"):
            alerts = snapshot.get("alerts") or []
            filtered = [
                item
                for item in alerts
                if (geo == "ALL" or str(item.get("geography", "")).upper() == geo)
                and (category == "all" or str(item.get("category", "")).lower() == category)
            ]
            payload = {
                "alerts": filtered,
                "generated_at": snapshot.get("generated_at"),
                "status": "from_aggregate_cache",
            }
    elif category != "all" or geo != "ALL":
        alerts = payload.get("alerts") or []
        payload = {
            **payload,
            "alerts": [
                item
                for item in alerts
                if (geo == "ALL" or str(item.get("geography", "")).upper() == geo)
                and (category == "all" or str(item.get("category", "")).lower() == category)
            ],
        }
    generated_at = None
    if payload and payload.get("generated_at"):
        try:
            generated_at = datetime.fromisoformat(str(payload.get("generated_at")))
        except Exception:  # noqa: BLE001
            generated_at = None
    stale_cutoff = datetime.utcnow() - timedelta(minutes=stale_after_minutes)
    is_stale = bool(payload and generated_at and generated_at <= stale_cutoff)

    if payload and payload.get("alerts") and not (refresh_if_stale and is_stale):
        return payload

    should_refresh = (refresh_if_empty and not (payload and payload.get("alerts"))) or (refresh_if_stale and is_stale)
    if should_refresh:
        # Always refresh the aggregate snapshot once, then serve all geo/category filters from cache.
        entity_id = "trend:ALL:all"
        active = await job_queue_service.find_active_job(
            db,
            job_type="trends_scan",
            entity_id=entity_id,
            max_age_minutes=max(5, settings.trend_radar_interval_minutes * 2),
        )
        if active:
            status_payload = {"alerts": (payload or {}).get("alerts", []), "status": "refresh_running", "job_id": str(active.id)}
            if payload and payload.get("generated_at"):
                status_payload["generated_at"] = payload.get("generated_at")
            return status_payload
        ticket = await _enqueue_dashboard_job(
            db=db,
            request=request,
            current_user=current_user,
            job_type="trends_scan",
            queue_name="ai_trends",
            payload={"geo": "ALL", "category": "all", "limit": max(8, limit), "mode": "fast"},
            entity_id=entity_id,
        )
        refresh_status = "refresh_queued"
        if is_stale:
            refresh_status = "stale_refresh_queued"
        return {"alerts": (payload or {}).get("alerts", []), "status": refresh_status, **ticket}

    return payload or {"alerts": []}


@router.post("/agents/published-monitor/run")
async def trigger_published_monitor(
    request: Request,
    db: AsyncSession = Depends(get_db),
    feed_url: str | None = Query(default=None),
    limit: int | None = Query(default=None, ge=1, le=30),
    wait: bool = Query(default=False),
    wait_timeout_seconds: int = Query(default=90, ge=5, le=180),
    current_user: User = Depends(get_current_user),
):
    """Enqueue published-content quality monitor."""
    _assert_newsroom_refresh_permission(current_user)
    active = await job_queue_service.find_active_job(
        db,
        job_type="published_monitor_scan",
        entity_id="published_monitor",
        max_age_minutes=max(5, settings.published_monitor_interval_minutes * 2),
    )
    if active:
        ticket = {
            "job_id": str(active.id),
            "status": active.status,
            "job_type": "published_monitor_scan",
        }
        if wait:
            deadline = datetime.utcnow() + timedelta(seconds=wait_timeout_seconds)
            while datetime.utcnow() < deadline:
                job = await job_queue_service.get_job(db, str(active.id))
                if not job:
                    break
                if job.status == "completed":
                    report = ((job.result_json or {}).get("report") or {})
                    normalized = _normalize_published_monitor_payload(report, status=str(report.get("status") or "ok"))
                    return {"message": "Published monitor completed.", "report": normalized, **ticket, "status": "completed"}
                if job.status in {"failed", "dead_lettered"}:
                    return {"message": "Published monitor failed.", **ticket, "status": job.status, "error": job.error}
                await asyncio.sleep(1)
        return {"message": "Published monitor already active.", **ticket}

    ticket = await _enqueue_dashboard_job(
        db=db,
        request=request,
        current_user=current_user,
        job_type="published_monitor_scan",
        queue_name="ai_quality",
        payload={"feed_url": feed_url, "limit": limit},
        entity_id="published_monitor",
    )
    if wait and ticket.get("job_id"):
        deadline = datetime.utcnow() + timedelta(seconds=wait_timeout_seconds)
        while datetime.utcnow() < deadline:
            job = await job_queue_service.get_job(db, ticket["job_id"])
            if not job:
                break
            if job.status == "completed":
                report = ((job.result_json or {}).get("report") or {})
                normalized = _normalize_published_monitor_payload(report, status=str(report.get("status") or "ok"))
                return {"message": "Published monitor completed.", "report": normalized, **ticket, "status": "completed"}
            if job.status in {"failed", "dead_lettered"}:
                return {"message": "Published monitor failed.", **ticket, "status": job.status, "error": job.error}
            await asyncio.sleep(1)
    return {"message": "Published monitor queued.", **ticket}


def _safe_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_iso_datetime(value) -> str:
    now = datetime.now(timezone.utc)
    if isinstance(value, datetime):
        dt = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")

    raw = str(value or "").strip()
    if not raw:
        return now.isoformat(timespec="milliseconds").replace("+00:00", "Z")

    candidate = raw
    if raw.endswith("Z"):
        candidate = raw[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(candidate)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    except ValueError:
        return now.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _normalize_published_monitor_payload(payload: dict | None, status: str = "ok") -> dict:
    payload = payload or {}
    executed_at = _normalize_iso_datetime(payload.get("executed_at"))
    items = payload.get("items")
    if not isinstance(items, list):
        items = []
    return {
        "feed_url": str(payload.get("feed_url") or settings.published_monitor_feed_url),
        "executed_at": executed_at,
        "interval_minutes": _safe_int(payload.get("interval_minutes"), settings.published_monitor_interval_minutes),
        "total_items": _safe_int(payload.get("total_items"), len(items)),
        "average_score": round(_safe_float(payload.get("average_score"), 0.0), 2),
        "weak_items_count": _safe_int(payload.get("weak_items_count"), 0),
        "issues_count": _safe_int(payload.get("issues_count"), 0),
        "status": str(payload.get("status") or status),
        "items": items,
    }


async def _latest_published_monitor_from_jobs(db: AsyncSession) -> dict | None:
    row = await db.execute(
        select(JobRun)
        .where(
            JobRun.job_type == "published_monitor_scan",
            JobRun.status == "completed",
            JobRun.result_json.is_not(None),
        )
        .order_by(desc(JobRun.finished_at), desc(JobRun.queued_at))
        .limit(1)
    )
    job = row.scalar_one_or_none()
    if not job:
        return None
    report = (job.result_json or {}).get("report")
    if isinstance(report, dict):
        return report
    return None


@router.get("/agents/published-monitor/latest")
async def get_latest_published_monitor(
    request: Request,
    refresh_if_empty: bool = Query(True),
    limit: int | None = Query(default=None, ge=1, le=30),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get latest published-content quality report."""
    _assert_newsroom_refresh_permission(current_user)
    payload = await published_content_monitor_agent.latest()
    if not payload:
        payload = await _latest_published_monitor_from_jobs(db)
    if payload:
        return _normalize_published_monitor_payload(payload, status="ok")

    if refresh_if_empty:
        active = await job_queue_service.find_active_job(
            db,
            job_type="published_monitor_scan",
            entity_id="published_monitor",
            max_age_minutes=max(5, settings.published_monitor_interval_minutes * 2),
        )
        if active:
            normalized = _normalize_published_monitor_payload({"status": "refresh_running"}, status="refresh_running")
            return {
                "job_id": str(active.id),
                "job_type": "published_monitor_scan",
                "job_status": active.status,
                **normalized,
                "status": "refresh_running",
            }
        ticket = await _enqueue_dashboard_job(
            db=db,
            request=request,
            current_user=current_user,
            job_type="published_monitor_scan",
            queue_name="ai_quality",
            payload={"feed_url": settings.published_monitor_feed_url, "limit": limit},
            entity_id="published_monitor",
        )
        normalized = _normalize_published_monitor_payload({"status": "refresh_queued"}, status="refresh_queued")
        return {
            **ticket,
            **normalized,
            "job_status": ticket.get("status"),
            "status": "refresh_queued",
        }

    return _normalize_published_monitor_payload({"status": "empty"}, status="empty")


@router.get("/agents/status")
async def agents_status():
    """Get current agent statuses."""
    return {
        "scout": {"status": "ready", "description": "وكيل الكشاف - جمع الأخبار من المصادر"},
        "router": {"status": "ready", "description": "وكيل الموجه - التصنيف والتوجيه"},
        "scribe": {"status": "ready", "description": "وكيل الكاتب - توليد المسودة"},
        "trend_radar": {"status": "ready", "description": "رادار التراند - اكتشاف الاتجاهات"},
        "published_monitor": {"status": "ready", "description": "مراقبة جودة المحتوى المنشور"},
        "audio": {"status": "ready", "description": "وكيل الصوت - النشرات الصوتية"},
    }


@router.get("/notifications")
async def dashboard_notifications(
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Unified in-app notifications feed for newsroom users."""
    _assert_newsroom_refresh_permission(current_user)

    items: list[dict] = []
    now = datetime.utcnow()

    breaking_rows = await db.execute(
        select(Article)
        .where(
            and_(
                Article.is_breaking == True,
                Article.crawled_at >= now - timedelta(hours=6),
            )
        )
        .order_by(Article.crawled_at.desc())
        .limit(8)
    )
    for article in breaking_rows.scalars().all():
        items.append(
            {
                "id": f"breaking-{article.id}",
                "type": "breaking",
                "title": article.title_ar or article.original_title,
                "message": "خبر عاجل جديد يحتاج متابعة تحريرية فورية.",
                "article_id": article.id,
                "created_at": article.crawled_at,
                "severity": "high",
            }
        )

    candidate_rows = await db.execute(
        select(Article)
        .where(
            and_(
                Article.status == NewsStatus.CANDIDATE,
                Article.crawled_at >= now - timedelta(hours=6),
            )
        )
        .order_by(Article.crawled_at.desc())
        .limit(8)
    )
    for article in candidate_rows.scalars().all():
        items.append(
            {
                "id": f"candidate-{article.id}",
                "type": "candidate",
                "title": article.title_ar or article.original_title,
                "message": "خبر مرشح بانتظار قرار التحرير.",
                "article_id": article.id,
                "created_at": article.crawled_at,
                "severity": "medium",
            }
        )

    if current_user.role in {UserRole.director, UserRole.editor_chief}:
        chief_rows = await db.execute(
            select(Article)
            .where(
                and_(
                    Article.status.in_(
                        [
                            NewsStatus.READY_FOR_CHIEF_APPROVAL,
                            NewsStatus.APPROVAL_REQUEST_WITH_RESERVATIONS,
                        ]
                    ),
                    Article.updated_at >= now - timedelta(hours=24),
                )
            )
            .order_by(Article.updated_at.desc())
            .limit(12)
        )
        for article in chief_rows.scalars().all():
            with_reservations = article.status == NewsStatus.APPROVAL_REQUEST_WITH_RESERVATIONS
            items.append(
                {
                    "id": f"chief-review-{article.id}",
                    "type": "chief_review",
                    "title": article.title_ar or article.original_title,
                    "message": "طلب اعتماد مع تحفظات من وكيل السياسة." if with_reservations else "خبر جاهز لاعتماد رئيس التحرير.",
                    "article_id": article.id,
                    "created_at": article.updated_at or article.crawled_at,
                    "severity": "high" if with_reservations else "medium",
                }
            )

    if current_user.role in {UserRole.social_media, UserRole.director, UserRole.editor_chief}:
        social_rows = await db.execute(
            select(Article)
            .where(
                and_(
                    Article.status.in_([NewsStatus.READY_FOR_MANUAL_PUBLISH, NewsStatus.PUBLISHED]),
                    Article.updated_at >= now - timedelta(hours=24),
                )
            )
            .order_by(Article.updated_at.desc())
            .limit(10)
        )
        for article in social_rows.scalars().all():
            items.append(
                {
                    "id": f"social-ready-{article.id}",
                    "type": "social_ready",
                    "title": article.title_ar or article.original_title,
                    "message": "الخبر معتمد ويمكن نسخ نسخ السوشيال الجاهزة.",
                    "article_id": article.id,
                    "created_at": article.updated_at or article.crawled_at,
                    "severity": "medium",
                }
            )

    reminder_items = await event_reminder_service.get_feed(limit=20)
    for reminder in reminder_items:
        starts_at = reminder.get("starts_at")
        scope = reminder.get("scope")
        scope_suffix = f" [{scope}]" if scope else ""
        message = str(reminder.get("message") or "Upcoming event requires preparation.")
        if starts_at:
            message = f"{message} الموعد: {starts_at}"
        items.append(
            {
                "id": reminder.get("id") or f"event-reminder-{reminder.get('event_id')}",
                "type": "event_reminder",
                "title": f"{reminder.get('title') or 'حدث قادم'}{scope_suffix}",
                "message": message,
                "event_id": reminder.get("event_id"),
                "created_at": reminder.get("created_at") or now.isoformat(),
                "severity": reminder.get("severity") or "medium",
            }
        )

    trend_payload = await cache_service.get_json("trends:last:DZ:all")
    seen_trends: set[str] = set()
    for idx, alert in enumerate((trend_payload or {}).get("alerts", [])[:12]):
        keyword = (alert.get("keyword", "") or "").strip()
        normalized_keyword = " ".join(keyword.lower().split())
        if normalized_keyword in seen_trends:
            continue
        seen_trends.add(normalized_keyword)
        items.append(
            {
                "id": f"trend-{idx}-{keyword}",
                "type": "trend",
                "title": keyword or "\u062a\u0631\u0627\u0646\u062f \u062c\u062f\u064a\u062f",
                "message": alert.get("reason", "\u0627\u062a\u062c\u0627\u0647 \u062a\u0631\u0646\u062f \u064a\u062d\u062a\u0627\u062c \u0645\u062a\u0627\u0628\u0639\u0629 \u062a\u062d\u0631\u064a\u0631\u064a\u0629."),
                "created_at": alert.get("detected_at") or now.isoformat(),
                "severity": "low",
            }
        )

    monitor_payload = await published_content_monitor_agent.latest()
    if not monitor_payload:
        monitor_payload = await _latest_published_monitor_from_jobs(db)
    if monitor_payload:
        weak_items = int(monitor_payload.get("weak_items_count", 0))
        average_score = monitor_payload.get("average_score", 0)
        items.append(
            {
                "id": "published-quality-monitor",
                "type": "published_quality",
                "title": "مراقبة جودة المحتوى المنشور",
                "message": (
                    f"تم رصد {weak_items} مقالاً يحتاج مراجعة. المعدل العام {average_score}/100."
                    if weak_items > 0
                    else f"لا توجد إنذارات حرجة حالياً. المعدل العام {average_score}/100."
                ),
                "created_at": monitor_payload.get("executed_at") or now.isoformat(),
                "severity": "high" if weak_items > 0 else "low",
            }
        )

    severity_rank = {"high": 3, "medium": 2, "low": 1}

    def _dedupe_key(item: dict) -> str:
        article_id = item.get("article_id")
        if article_id:
            return f"article:{article_id}"
        event_id = item.get("event_id")
        if event_id:
            return f"event:{event_id}:{item.get('type', 'event')}"
        normalized_title = " ".join(str(item.get("title", "")).lower().split())
        return f"{item.get('type', 'generic')}:{normalized_title}"

    deduped: dict[str, dict] = {}
    for item in items:
        key = _dedupe_key(item)
        previous = deduped.get(key)
        if previous is None:
            deduped[key] = item
            continue

        prev_rank = severity_rank.get(str(previous.get("severity", "low")).lower(), 0)
        cur_rank = severity_rank.get(str(item.get("severity", "low")).lower(), 0)
        if cur_rank > prev_rank:
            deduped[key] = item
            continue

        prev_created = str(previous.get("created_at") or "")
        cur_created = str(item.get("created_at") or "")
        if cur_created > prev_created:
            deduped[key] = item

    def _dt(v: object) -> datetime:
        if isinstance(v, datetime):
            return v
        if isinstance(v, str):
            try:
                return datetime.fromisoformat(v.replace("Z", "+00:00")).replace(tzinfo=None)
            except Exception:
                return datetime.min
        return datetime.min

    items = sorted(deduped.values(), key=lambda x: _dt(x.get("created_at")), reverse=True)[:limit]
    return {"items": items, "total": len(items)}
