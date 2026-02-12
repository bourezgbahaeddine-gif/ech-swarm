"""
╔══════════════════════════════════════════════════╗
║      Echorouk AI Swarm — غرفة الشروق الذكية       ║
║    AI-Powered Newsroom for Echorouk Online        ║
║                                                   ║
║    Built with: FastAPI + Gemini + PostgreSQL       ║
║    Version: 1.0.0                                 ║
╚══════════════════════════════════════════════════╝
"""

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

settings = get_settings()
logger = get_logger("main")

# Track uptime
_start_time = time.time()


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

    logger.info(
        "app_ready",
        msg="🚀 غرفة الشروق الذكية جاهزة للعمل",
        port=settings.app_port,
    )

    yield

    # ── Shutdown ──
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
