"""
Echorouk AI Swarm - Dashboard & Agent Control API.
"""

from datetime import datetime, timedelta
import asyncio

from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException, Query
from sqlalchemy import select, func, and_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db, async_session
from app.core.config import get_settings
from app.core.logging import get_logger
from app.models import Article, Source, PipelineRun, FailedJob, NewsStatus, UrgencyLevel
from app.models.user import User, UserRole
from app.api.routes.auth import get_current_user
from app.schemas import DashboardStats, PipelineRunResponse
from app.services.cache_service import cache_service
from app.agents import scout_agent, router_agent, scribe_agent, trend_radar_agent

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
                Article.crawled_at < cutoff,
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
                Article.crawled_at >= breaking_cutoff,
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


async def _run_scout_pipeline():
    async with async_session() as db:
        stats = await scout_agent.run(db)
        await router_agent.process_batch(db)
        logger.info("scout_pipeline_completed", stats=stats)


async def _run_router_pipeline():
    async with async_session() as db:
        stats = await router_agent.process_batch(db)
        logger.info("router_pipeline_completed", stats=stats)


async def _run_scribe_pipeline():
    async with async_session() as db:
        stats = await scribe_agent.batch_write(db)
        logger.info("scribe_pipeline_completed", stats=stats)


async def _run_trends_scan(geo: str, category: str, limit: int, mode: str):
    alerts = await trend_radar_agent.scan(geo=geo, category=category, limit=limit, mode=mode)
    logger.info("trends_scan_completed", alerts_count=len(alerts), geo=geo, category=category, limit=limit, mode=mode)


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
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
):
    """Queue Scout Agent run in background and return immediately."""
    _assert_newsroom_refresh_permission(current_user)
    background_tasks.add_task(_run_scout_pipeline)
    return {"message": "تمت جدولة تشغيل الكشاف."}


@router.post("/agents/router/run")
async def trigger_router(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
):
    """Queue Router Agent run in background and return immediately."""
    _assert_newsroom_refresh_permission(current_user)
    background_tasks.add_task(_run_router_pipeline)
    return {"message": "تمت جدولة تشغيل الموجه."}


@router.post("/agents/scribe/run")
async def trigger_scribe(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
):
    """Queue Scribe Agent run in background and return immediately."""
    _assert_agent_control_permission(current_user)
    background_tasks.add_task(_run_scribe_pipeline)
    return {"message": "تمت جدولة تشغيل الكاتب."}


@router.post("/agents/trends/scan")
async def trigger_trend_scan(
    background_tasks: BackgroundTasks,
    geo: str = Query("DZ", min_length=2, max_length=16),
    category: str = Query("all", min_length=2, max_length=32),
    limit: int = Query(12, ge=1, le=30),
    mode: str = Query("fast", pattern="^(fast|deep)$"),
    wait: bool = Query(False),
    current_user: User = Depends(get_current_user),
):
    """Run Trend Radar scan (sync when wait=true, async otherwise)."""
    _assert_trend_permission(current_user)
    if wait:
        try:
            alerts = await asyncio.wait_for(
                trend_radar_agent.scan(geo=geo, category=category, limit=limit, mode=mode),
                timeout=25,
            )
            return {"message": "اكتمل مسح التراند.", "alerts": [a.model_dump(mode="json") for a in alerts]}
        except TimeoutError:
            payload = await cache_service.get_json(f"trends:last:{geo.upper()}:{category.lower()}")
            return {
                "message": "انتهت مهلة المسح. تم إرجاع آخر نتائج مخزنة.",
                "alerts": (payload or {}).get("alerts", []),
            }

    background_tasks.add_task(_run_trends_scan, geo.upper(), category.lower(), limit, mode.lower())
    return {"message": "تمت جدولة مسح التراند."}


@router.get("/agents/trends/latest")
async def get_latest_trend_scan(
    geo: str = Query("DZ", min_length=2, max_length=16),
    category: str = Query("all", min_length=2, max_length=32),
    refresh_if_empty: bool = Query(True),
    limit: int = Query(12, ge=1, le=30),
    current_user: User = Depends(get_current_user),
):
    """Fetch latest cached trend scan payload for a geography/category."""
    _assert_trend_permission(current_user)
    geo = geo.upper()
    category = category.lower()
    payload = await cache_service.get_json(f"trends:last:{geo}:{category}")
    if payload and payload.get("alerts"):
        return payload

    if refresh_if_empty:
        try:
            alerts = await asyncio.wait_for(
                trend_radar_agent.scan(geo=geo, category=category, limit=limit, mode="fast"),
                timeout=15,
            )
            if alerts:
                return {"alerts": [a.model_dump(mode="json") for a in alerts]}
        except TimeoutError:
            logger.warning("latest_trends_refresh_timeout", geo=geo, category=category)
        except Exception as exc:
            logger.warning("latest_trends_refresh_error", geo=geo, category=category, error=str(exc))

    return payload or {"alerts": []}


@router.get("/agents/status")
async def agents_status():
    """Get current agent statuses."""
    return {
        "scout": {"status": "ready", "description": "وكيل الكشاف - جمع الأخبار من المصادر"},
        "router": {"status": "ready", "description": "وكيل الموجه - التصنيف والتوجيه"},
        "scribe": {"status": "ready", "description": "وكيل الكاتب - توليد المسودة"},
        "trend_radar": {"status": "ready", "description": "رادار التراند - اكتشاف الاتجاهات"},
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

    trend_payload = await cache_service.get_json("trends:last:DZ:all")
    for idx, alert in enumerate((trend_payload or {}).get("alerts", [])[:8]):
        items.append(
            {
                "id": f"trend-{idx}-{alert.get('keyword', '')}",
                "type": "trend",
                "title": alert.get("keyword", "تراند جديد"),
                "message": alert.get("reason", "اتجاه ترند يحتاج متابعة تحريرية."),
                "created_at": alert.get("detected_at") or now.isoformat(),
                "severity": "low",
            }
        )

    def _dt(v: object) -> datetime:
        if isinstance(v, datetime):
            return v
        if isinstance(v, str):
            try:
                return datetime.fromisoformat(v.replace("Z", "+00:00")).replace(tzinfo=None)
            except Exception:
                return datetime.min
        return datetime.min

    items = sorted(items, key=lambda x: _dt(x.get("created_at")), reverse=True)[:limit]
    return {"items": items, "total": len(items)}
