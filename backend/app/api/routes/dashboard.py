"""
Echorouk AI Swarm — Dashboard & Agent Control API
====================================================
Dashboard stats, agent triggers, and pipeline monitoring.
"""

from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.logging import get_logger
from app.models import Article, Source, PipelineRun, FailedJob, NewsStatus
from app.schemas import DashboardStats, PipelineRunResponse
from app.services.cache_service import cache_service
from app.agents import scout_agent, router_agent, scribe_agent, trend_radar_agent

logger = get_logger("api.dashboard")
router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(db: AsyncSession = Depends(get_db)):
    """Get real-time dashboard statistics."""
    cached = await cache_service.get_json("dashboard:stats")
    if cached:
        return DashboardStats(**cached)

    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    # Article counts
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
            and_(Article.is_breaking == True, Article.crawled_at >= today)
        )
    )

    # Source counts
    sources_active = await db.execute(
        select(func.count(Source.id)).where(Source.enabled == True)
    )
    sources_total = await db.execute(select(func.count(Source.id)))

    # AI calls
    ai_calls = await cache_service.get_counter("ai_calls_today")

    # Avg processing time
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
    # Cache for a short window to reduce DB load on dashboards
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


# ── Agent Triggers ──

@router.post("/agents/scout/run")
async def trigger_scout(background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    """Manually trigger the Scout Agent to fetch news."""
    stats = await scout_agent.run(db)
    # Optional smooth pipeline: route immediately after scout
    await router_agent.process_batch(db)
    return {"message": "Scout run completed", "stats": stats}


@router.post("/agents/router/run")
async def trigger_router(db: AsyncSession = Depends(get_db)):
    """Manually trigger the Router Agent to classify pending articles."""
    stats = await router_agent.process_batch(db)
    return {"message": "Router run completed", "stats": stats}


@router.post("/agents/scribe/run")
async def trigger_scribe(db: AsyncSession = Depends(get_db)):
    """Manually trigger the Scribe Agent to write approved articles."""
    stats = await scribe_agent.batch_write(db)
    return {"message": "Scribe run completed", "stats": stats}


@router.post("/agents/trends/scan")
async def trigger_trend_scan():
    """Manually trigger the Trend Radar scan."""
    alerts = await trend_radar_agent.scan()
    return {
        "message": "Trend scan completed",
        "alerts": [a.model_dump() for a in alerts],
    }


@router.get("/agents/status")
async def agents_status():
    """Get current agent statuses."""
    return {
        "scout": {"status": "ready", "description": "الوكيل الكشّاف - RSS Ingestion"},
        "router": {"status": "ready", "description": "الموجّه - Classification & Routing"},
        "scribe": {"status": "ready", "description": "الوكيل الكاتب - Article Generation"},
        "trend_radar": {"status": "ready", "description": "رادار التراند - Trend Detection"},
        "audio": {"status": "ready", "description": "المذيع الآلي - Audio Briefings"},
    }
