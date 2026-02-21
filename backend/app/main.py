"""
╔══════════════════════════════════════════════════╗
║      Echorouk AI Swarm — غرفة الشروق الذكية       ║
║    AI-Powered Newsroom for Echorouk Online        ║
║                                                   ║
║    Built with: FastAPI + Gemini + PostgreSQL       ║
║    Version: 1.0.0                                 ║
╚══════════════════════════════════════════════════╝
"""

import asyncio
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.database import init_db
from app.core.logging import setup_logging, get_logger
from app.services.cache_service import cache_service
from app.schemas import HealthResponse
from app.core.database import async_session
from app.agents import scout_agent, router_agent, scribe_agent, trend_radar_agent, published_content_monitor_agent

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
from app.msi.scheduler import start_msi_scheduler, stop_msi_scheduler

settings = get_settings()
logger = get_logger("main")

# Track uptime
_start_time = time.time()
_shutdown_event = asyncio.Event()
_pipeline_task: asyncio.Task | None = None
_trends_task: asyncio.Task | None = None
_published_monitor_task: asyncio.Task | None = None


async def _run_pipeline_once():
    async with async_session() as db:
        scout_stats = await scout_agent.run(db)
        router_stats = await router_agent.process_batch(db)
        scribe_stats = None
        if settings.auto_scribe_enabled:
            scribe_stats = await scribe_agent.batch_write(db)
        logger.info(
            "auto_pipeline_tick_done",
            scout=scout_stats,
            router=router_stats,
            scribe=scribe_stats,
        )


async def _run_trends_once():
    alerts = await trend_radar_agent.scan()
    logger.info("auto_trends_tick_done", alerts_count=len(alerts))


async def _run_published_monitor_once():
    report = await published_content_monitor_agent.scan()
    logger.info(
        "auto_published_monitor_tick_done",
        status=report.get("status", "unknown"),
        total_items=report.get("total_items", 0),
        weak_items=report.get("weak_items_count", 0),
        average_score=report.get("average_score", 0),
    )


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
    global _pipeline_task, _trends_task, _published_monitor_task
    _shutdown_event.clear()
    if settings.auto_pipeline_enabled:
        newsroom_interval_seconds = 20 * 60
        trend_interval_seconds = 10 * 60
        _pipeline_task = asyncio.create_task(
            _periodic_loop(
                "pipeline",
                newsroom_interval_seconds,
                _run_pipeline_once,
            )
        )
        _trends_task = asyncio.create_task(
            _periodic_loop(
                "trends",
                trend_interval_seconds,
                _run_trends_once,
            )
        )
        logger.info(
            "auto_pipeline_enabled",
            scout_interval_minutes=20,
            trend_interval_minutes=10,
            auto_scribe_enabled=settings.auto_scribe_enabled,
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

    if settings.msi_enabled and settings.msi_scheduler_enabled:
        start_msi_scheduler()

    logger.info(
        "app_ready",
        msg="🚀 غرفة الشروق الذكية جاهزة للعمل",
        port=settings.app_port,
    )

    yield

    # ── Shutdown ──
    _shutdown_event.set()
    for task in (_pipeline_task, _trends_task, _published_monitor_task):
        if task:
            task.cancel()
    await asyncio.gather(
        *[t for t in (_pipeline_task, _trends_task, _published_monitor_task) if t],
        return_exceptions=True,
    )
    if settings.msi_enabled and settings.msi_scheduler_enabled:
        stop_msi_scheduler()

    await cache_service.disconnect()
    logger.info("app_shutdown", msg="تم إيقاف النظام بنجاح")


# ── Create FastAPI App ──

app = FastAPI(
    title="Echorouk AI Swarm — غرفة الشروق الذكية",
    description=(
        "منصة ذكاء اصطناعي لأتمتة غرفة الأخبار.\n\n"
        "AI-powered newsroom automation platform for Echorouk Online.\n\n"
        "**Agents:**\n"
        "- 🔍 Scout (الكشّاف): RSS ingestion from 300+ sources\n"
        "- 🧭 Router (الموجّه): AI classification & priority routing\n"
        "- ✍️ Scribe (الكاتب): Article generation in Echorouk style\n"
        "- 📡 Trend Radar (رادار التراند): Real-time trend detection\n"
        "- 🎙️ Audio (المذيع): Automated audio news briefings\n"
    ),
    version="1.0.0",
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
    start = time.time()
    response = await call_next(request)
    elapsed = round((time.time() - start) * 1000, 2)

    if request.url.path not in ["/health", "/docs", "/redoc", "/openapi.json"]:
        logger.info(
            "http_request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            elapsed_ms=elapsed,
        )

    return response


# ── Global Exception Handler ──

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
    return JSONResponse(
        status_code=500,
        content={
            "error": "خطأ داخلي في النظام",
            "detail": "Internal server error. The team has been notified.",
        },
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
        "name": "Echorouk AI Swarm",
        "name_ar": "غرفة الشروق الذكية",
        "version": "1.0.0",
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
