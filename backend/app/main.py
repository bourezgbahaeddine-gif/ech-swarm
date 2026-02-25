"""
╔══════════════════════════════════════════════════╗
║      Echorouk Editorial OS                         ║
║ The Operating System for Intelligent Editorial     ║
║ Workflows                                          ║
║                                                   ║
║    Built with: FastAPI + Gemini + PostgreSQL       ║
║    Version: 1.1.0 (Async AI Isolation)            ║
╚══════════════════════════════════════════════════╝
"""

import asyncio
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.database import init_db
from app.core.logging import setup_logging, get_logger
from app.core.correlation import (
    get_correlation_id,
    get_request_id,
    new_correlation_id,
    new_request_id,
    set_correlation_id,
    set_request_id,
)
from app.services.cache_service import cache_service
from app.schemas import HealthResponse
from app.core.database import async_session
from app.agents import scout_agent
import structlog

# Import routers
from app.api.routes.news import router as news_router
from app.api.routes.sources import router as sources_router
from app.api.routes.editorial import router as editorial_router
from app.api.routes.dashboard import router as dashboard_router
from app.api.routes.auth import router as auth_router
from app.api.routes.rss import router as rss_router
from app.api.routes.settings import router as settings_router
from app.api.routes.constitution import router as constitution_router
from app.api.routes.journalist_services import router as journalist_services_router
from app.api.routes.memory import router as memory_router
from app.api.routes.msi import router as msi_router
from app.api.routes.simulator import router as simulator_router
from app.api.routes.media_logger import router as media_logger_router
from app.api.routes.document_intel import router as document_intel_router
from app.api.routes.competitor_xray import router as competitor_xray_router
from app.api.routes.jobs import router as jobs_router
from app.api.routes.stories import router as stories_router
from app.msi.scheduler import start_msi_scheduler, stop_msi_scheduler
from app.services.competitor_xray_service import competitor_xray_service
from app.services.job_queue_service import job_queue_service
from app.api.envelope import error_envelope

settings = get_settings()
logger = get_logger("main")

# Track uptime
_start_time = time.time()
_shutdown_event = asyncio.Event()
_pipeline_task: asyncio.Task | None = None
_trends_task: asyncio.Task | None = None
_published_monitor_task: asyncio.Task | None = None
_competitor_xray_task: asyncio.Task | None = None


async def _run_pipeline_once():
    async with async_session() as db:
        scout_stats = await scout_agent.run(db)
        router_job_id = None
        allowed_router, depth_router, limit_router = await job_queue_service.check_backpressure("ai_router")
        if allowed_router:
            router_job = await job_queue_service.create_job(
                db,
                job_type="pipeline_router",
                queue_name="ai_router",
                payload={"source": "auto_pipeline"},
                entity_id="auto_pipeline",
                actor_username="system",
                max_attempts=3,
            )
            await job_queue_service.enqueue_by_job_type(job_type="pipeline_router", job_id=str(router_job.id))
            router_job_id = str(router_job.id)
        else:
            logger.warning("auto_pipeline_router_backpressure", depth=depth_router, limit=limit_router)
        scribe_job_id = None
        if settings.auto_scribe_enabled:
            allowed_scribe, depth_scribe, limit_scribe = await job_queue_service.check_backpressure("ai_scribe")
            if allowed_scribe:
                scribe_job = await job_queue_service.create_job(
                    db,
                    job_type="pipeline_scribe",
                    queue_name="ai_scribe",
                    payload={"source": "auto_pipeline"},
                    entity_id="auto_pipeline",
                    actor_username="system",
                    max_attempts=3,
                )
                await job_queue_service.enqueue_by_job_type(job_type="pipeline_scribe", job_id=str(scribe_job.id))
                scribe_job_id = str(scribe_job.id)
            else:
                logger.warning("auto_pipeline_scribe_backpressure", depth=depth_scribe, limit=limit_scribe)
        logger.info(
            "auto_pipeline_tick_done",
            scout=scout_stats,
            router_job_id=router_job_id,
            scribe_job_id=scribe_job_id,
        )


async def _run_trends_once():
    async with async_session() as db:
        active_job = await job_queue_service.find_active_job(
            db,
            job_type="trends_scan",
            entity_id="auto_trends",
            max_age_minutes=max(5, settings.trend_radar_interval_minutes * 2),
        )
        if active_job:
            logger.info("auto_trends_skip_active_job", job_id=str(active_job.id), status=active_job.status)
            return
        allowed, depth, limit_depth = await job_queue_service.check_backpressure("ai_trends")
        if not allowed:
            logger.warning("auto_trends_backpressure", depth=depth, limit=limit_depth)
            return
        job = await job_queue_service.create_job(
            db,
            job_type="trends_scan",
            queue_name="ai_trends",
            payload={"geo": "ALL", "category": "all", "limit": 10, "mode": "fast"},
            entity_id="auto_trends",
            actor_username="system",
            max_attempts=3,
        )
        await job_queue_service.enqueue_by_job_type(job_type="trends_scan", job_id=str(job.id))
    logger.info("auto_trends_tick_done", job_id=str(job.id))


async def _run_published_monitor_once():
    async with async_session() as db:
        allowed, depth, limit_depth = await job_queue_service.check_backpressure("ai_quality")
        if not allowed:
            logger.warning("auto_published_monitor_backpressure", depth=depth, limit=limit_depth)
            return
        job = await job_queue_service.create_job(
            db,
            job_type="published_monitor_scan",
            queue_name="ai_quality",
            payload={"feed_url": settings.published_monitor_feed_url, "limit": settings.published_monitor_limit},
            entity_id="auto_published_monitor",
            actor_username="system",
            max_attempts=3,
        )
        await job_queue_service.enqueue_by_job_type(job_type="published_monitor_scan", job_id=str(job.id))
    logger.info("auto_published_monitor_tick_done", job_id=str(job.id))


async def _run_competitor_xray_once():
    run_id = await competitor_xray_service.trigger_scheduled_run(
        limit_per_source=max(1, settings.competitor_xray_limit_per_source),
        hours_window=max(6, settings.competitor_xray_hours_window),
    )
    logger.info("auto_competitor_xray_tick_done", run_id=run_id)


async def _periodic_loop(name: str, interval_seconds: int, job):
    logger.info("periodic_loop_started", loop=name, interval_seconds=interval_seconds)
    while not _shutdown_event.is_set():
        started = time.time()
        try:
            await job()
        except Exception as exc:  # noqa: BLE001
            logger.error("periodic_loop_error", loop=name, error=str(exc))

        elapsed = int(time.time() - started)
        sleep_for = max(1, interval_seconds - elapsed)
        try:
            await asyncio.wait_for(_shutdown_event.wait(), timeout=sleep_for)
        except asyncio.TimeoutError:
            pass
    logger.info("periodic_loop_stopped", loop=name)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup & shutdown lifecycle."""

    # ── Startup ──
    setup_logging(debug=settings.app_debug)
    logger.info("app_starting", app=settings.app_name, env=settings.app_env)

    # Initialize database tables
    await init_db()
    logger.info("database_initialized")

    # Connect to Redis
    await cache_service.connect()

    # Start periodic pipeline loops (optional)
    global _pipeline_task, _trends_task, _published_monitor_task, _competitor_xray_task
    _shutdown_event.clear()
    if settings.auto_pipeline_enabled:
        newsroom_interval_seconds = 20 * 60
        _pipeline_task = asyncio.create_task(
            _periodic_loop(
                "pipeline",
                newsroom_interval_seconds,
                _run_pipeline_once,
            )
        )
        logger.info(
            "auto_pipeline_enabled",
            scout_interval_minutes=20,
            auto_scribe_enabled=settings.auto_scribe_enabled,
        )

    if settings.auto_trends_enabled:
        trend_interval_seconds = max(300, settings.trend_radar_interval_minutes * 60)
        _trends_task = asyncio.create_task(
            _periodic_loop(
                "trends",
                trend_interval_seconds,
                _run_trends_once,
            )
        )
        logger.info(
            "auto_trends_enabled",
            trend_interval_minutes=settings.trend_radar_interval_minutes,
        )

    if settings.published_monitor_enabled:
        published_monitor_interval_seconds = max(300, settings.published_monitor_interval_minutes * 60)
        _published_monitor_task = asyncio.create_task(
            _periodic_loop(
                "published_monitor",
                published_monitor_interval_seconds,
                _run_published_monitor_once,
            )
        )
        logger.info(
            "published_monitor_enabled",
            interval_minutes=settings.published_monitor_interval_minutes,
            feed_url=settings.published_monitor_feed_url,
        )

    if settings.competitor_xray_enabled:
        _competitor_xray_task = asyncio.create_task(
            _periodic_loop(
                "competitor_xray",
                max(600, settings.competitor_xray_interval_minutes * 60),
                _run_competitor_xray_once,
            )
        )
        logger.info(
            "competitor_xray_enabled",
            interval_minutes=settings.competitor_xray_interval_minutes,
            limit_per_source=settings.competitor_xray_limit_per_source,
            hours_window=settings.competitor_xray_hours_window,
        )

    if settings.msi_enabled and settings.msi_scheduler_enabled:
        start_msi_scheduler()

    logger.info(
        "app_ready",
        msg="🚀 Echorouk Editorial OS is operational",
        port=settings.app_port,
    )

    yield

    # ── Shutdown ──
    _shutdown_event.set()
    for task in (_pipeline_task, _trends_task, _published_monitor_task, _competitor_xray_task):
        if task:
            task.cancel()
    await asyncio.gather(
        *[t for t in (_pipeline_task, _trends_task, _published_monitor_task, _competitor_xray_task) if t],
        return_exceptions=True,
    )
    if settings.msi_enabled and settings.msi_scheduler_enabled:
        stop_msi_scheduler()

    await cache_service.disconnect()
    logger.info("app_shutdown", msg="تم إيقاف النظام بنجاح")


# ── Create FastAPI App ──

app = FastAPI(
    title="Echorouk Editorial OS",
    description=(
        "The Operating System for Intelligent Editorial Workflows.\n\n"
        "Enterprise platform to manage editorial lifecycle from capture "
        "to manual-publish readiness, with strict governance and mandatory Human-in-the-Loop.\n\n"
        "**Agents:**\n"
        "- 🔍 Scout (الكشّاف): RSS ingestion from 300+ sources\n"
        "- 🧭 Router (الموجّه): AI classification & priority routing\n"
        "- ✍️ Scribe (الكاتب): Article generation in Echorouk style\n"
        "- 📡 Trend Radar (رادار التراند): Real-time trend detection\n"
        "- 🎙️ Audio (المذيع): Automated audio news briefings\n"
    ),
    version="1.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS Middleware ──

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request Logging Middleware ──

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all incoming requests with timing."""
    request_id = request.headers.get("x-request-id") or new_request_id()
    correlation_id = request.headers.get("x-correlation-id") or new_correlation_id()
    set_request_id(request_id)
    set_correlation_id(correlation_id)
    structlog.contextvars.bind_contextvars(request_id=request_id, correlation_id=correlation_id)
    start = time.time()
    response = None
    try:
        response = await call_next(request)
        return response
    finally:
        elapsed = round((time.time() - start) * 1000, 2)
        if response is not None:
            response.headers["x-request-id"] = request_id
            response.headers["x-correlation-id"] = correlation_id
            status_code = response.status_code
        else:
            status_code = 500

        if request.url.path not in ["/health", "/docs", "/redoc", "/openapi.json"]:
            logger.info(
                "http_request",
                method=request.method,
                path=request.url.path,
                status=status_code,
                elapsed_ms=elapsed,
                request_id=get_request_id(),
                correlation_id=get_correlation_id(),
            )

        structlog.contextvars.clear_contextvars()
        set_request_id("")
        set_correlation_id("")


# ── Global Exception Handler ──

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    logger.warning(
        "http_exception",
        path=request.url.path,
        status_code=exc.status_code,
        detail=str(exc.detail),
    )
    return error_envelope(
        code="http_error",
        message="Request failed",
        status_code=exc.status_code,
        details=exc.detail,
        meta={"path": request.url.path},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.warning("validation_error", path=request.url.path, errors=exc.errors())
    return error_envelope(
        code="validation_error",
        message="Validation failed",
        status_code=422,
        details=exc.errors(),
        meta={"path": request.url.path},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Graceful Degradation: Never crash completely.
    Log errors and return a user-friendly message.
    """
    logger.error(
        "unhandled_exception",
        path=request.url.path,
        error=str(exc),
        error_type=type(exc).__name__,
    )
    return error_envelope(
        code="internal_error",
        message="خطأ داخلي في النظام",
        status_code=500,
        details="Internal server error. The team has been notified.",
        meta={"path": request.url.path},
    )


# ── Register Routers ──

app.include_router(auth_router, prefix="/api/v1")
app.include_router(news_router, prefix="/api/v1")
app.include_router(sources_router, prefix="/api/v1")
app.include_router(editorial_router, prefix="/api/v1")
app.include_router(dashboard_router, prefix="/api/v1")
app.include_router(rss_router, prefix="/api/v1")
app.include_router(settings_router, prefix="/api/v1")
app.include_router(constitution_router, prefix="/api/v1")
app.include_router(journalist_services_router, prefix="/api/v1")
app.include_router(memory_router, prefix="/api/v1")
app.include_router(msi_router, prefix="/api/v1")
app.include_router(simulator_router, prefix="/api/v1")
app.include_router(media_logger_router, prefix="/api/v1")
app.include_router(document_intel_router, prefix="/api/v1")
app.include_router(competitor_xray_router, prefix="/api/v1")
app.include_router(jobs_router, prefix="/api/v1")
app.include_router(stories_router, prefix="/api/v1")


# ── Health Check ──

@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    """System health check endpoint."""
    uptime = round(time.time() - _start_time, 2)
    redis_status = "connected" if cache_service.connected else "disconnected"

    return HealthResponse(
        status="ok",
        version="1.0.0",
        database="connected",
        redis=redis_status,
        uptime_seconds=uptime,
    )


@app.get("/", tags=["System"])
async def root():
    """Welcome endpoint."""
    return {
        "name": "Echorouk Editorial OS",
        "name_ar": "نظام التشغيل الذكي لسير العمل التحريري",
        "version": "1.1.0",
        "release_name": "Async AI Isolation",
        "status": "operational",
        "docs": "/docs",
        "agents": [
            "🔍 Scout (الكشّاف)",
            "🧭 Router (الموجّه)",
            "✍️ Scribe (الكاتب)",
            "📡 Trend Radar (رادار التراند)",
            "🎙️ Audio (المذيع الآلي)",
        ],
    }
