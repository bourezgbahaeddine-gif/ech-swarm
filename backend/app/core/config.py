"""
Echorouk Editorial OS - Configuration Module
============================================
All configuration is loaded from environment variables.
Zero hardcoded secrets (Rule #2: Zero Trust Security).
"""

import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env."""

    # App
    app_name: str = "Echorouk Editorial OS"
    app_env: str = "development"
    app_debug: bool = True
    app_secret_key: str = Field(..., min_length=32)
    app_port: int = 8000

    @property
    def secret_key(self) -> str:
        return self.app_secret_key

    # Database
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "echorouk_db"
    postgres_user: str = "echorouk"
    postgres_password: str = Field(..., min_length=8)

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def database_url_sync(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str = ""
    redis_db: int = 0
    redis_queue_db: int = 1

    @property
    def redis_url(self) -> str:
        auth = f":{self.redis_password}@" if self.redis_password else ""
        return f"redis://{auth}{self.redis_host}:{self.redis_port}/{self.redis_db}"

    @property
    def redis_queue_url(self) -> str:
        auth = f":{self.redis_password}@" if self.redis_password else ""
        return f"redis://{auth}{self.redis_host}:{self.redis_port}/{self.redis_queue_db}"

    # AI Services
    gemini_api_key: str = ""
    gemini_model_flash: str = "gemini-2.5-flash"
    gemini_model_pro: str = "gemini-2.5-pro"
    groq_api_key: str = ""
    youtube_data_api_key: str = ""
    youtube_trends_enabled: bool = False

    # Notifications
    telegram_bot_token: str = ""
    telegram_channel_editors: str = ""
    telegram_channel_alerts: str = ""
    slack_webhook_url: str = ""

    # MinIO
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "echorouk-media"
    minio_use_ssl: bool = False

    # Scheduling
    scout_interval_minutes: int = 20
    trend_radar_interval_minutes: int = 120
    auto_pipeline_enabled: bool = False
    auto_trends_enabled: bool = True
    auto_scribe_enabled: bool = True
    published_monitor_enabled: bool = True
    published_monitor_interval_minutes: int = 15
    published_monitor_feed_url: str = "https://www.echoroukonline.com/feed"
    published_monitor_limit: int = 12
    published_monitor_fetch_timeout: int = 12
    published_monitor_alert_threshold: int = 75
    competitor_xray_enabled: bool = True
    competitor_xray_interval_minutes: int = 30
    competitor_xray_limit_per_source: int = 6
    competitor_xray_hours_window: int = 48
    msi_enabled: bool = True
    msi_scheduler_enabled: bool = True
    msi_timezone: str = "Africa/Algiers"
    msi_daily_hour: int = 6
    msi_daily_minute: int = 0
    msi_weekly_day_of_week: str = "mon"
    msi_weekly_hour: int = 6
    msi_weekly_minute: int = 30
    msi_default_baseline_days: int = 90
    msi_default_report_limit: int = 30

    # Queue / Workers
    queue_enabled: bool = True
    queue_default_name: str = "ai_default"
    queue_backpressure_enabled: bool = True
    queue_depth_limit_default: int = 300
    queue_depth_limit_router: int = 200
    queue_depth_limit_scribe: int = 120
    queue_depth_limit_quality: int = 300
    queue_depth_limit_simulator: int = 100
    queue_depth_limit_msi: int = 80
    queue_depth_limit_links: int = 120
    queue_depth_limit_trends: int = 120
    queue_depth_limit_scripts: int = 120

    # Router throughput tuning
    router_batch_limit: int = 120
    router_source_quota: int = 20
    router_candidate_source_quota: int = 10
    router_rule_min_hits: int = 1
    router_skip_ai_for_non_local_aggregator: bool = True
    auto_pipeline_router_burst_max: int = 4
    auto_pipeline_router_burst_backlog_threshold: int = 400

    # Provider routing / circuit breaker
    provider_health_window_sec: int = 180
    provider_circuit_failures: int = 5
    provider_circuit_open_sec: int = 60
    provider_weight_gemini: float = 0.7
    provider_weight_groq: float = 0.3

    # FreshRSS / RSS-Bridge
    scout_use_freshrss: bool = False
    freshrss_feed_url: str = "http://freshrss:80/p/i/?a=rss&state=all"
    rssbridge_base_url: str = "http://rssbridge:80"
    rssbridge_enabled: bool = True

    # Processing Thresholds
    dedup_similarity_threshold: float = 0.70
    breaking_news_urgency_threshold: int = 8
    breaking_news_ttl_minutes: int = 60
    truth_score_reject_threshold: float = 0.4
    truth_score_verify_threshold: float = 0.8
    editorial_min_importance: int = 6
    editorial_require_local_signal: bool = True
    max_rss_sources: int = 300
    rss_fetch_timeout: int = 30
    scout_batch_size: int = 8
    scout_concurrency: int = 8
    scout_max_new_per_run: int = 250
    scout_freshrss_max_per_source_per_run: int = 12
    scout_max_article_age_hours: int = 72
    scout_max_article_future_minutes: int = 30
    scout_require_timestamp_for_aggregator: bool = True
    scout_blocked_domains: str = "echoroukonline.com,www.echoroukonline.com"

    # TTS
    tts_voice: str = "ar-DZ-IsmaelNeural"
    tts_rate: str = "+0%"
    tts_pitch: str = "+0Hz"

    # Document Intelligence
    document_intel_docling_timeout_seconds: int = 45
    document_intel_docling_max_size_mb: int = 8
    document_intel_docling_skip_for_ar: bool = True
    document_intel_max_upload_mb: int = 80
    document_intel_job_payload_ttl_seconds: int = 3600
    document_intel_ocr_enabled: bool = True
    document_intel_ocr_force: bool = False
    document_intel_ocr_timeout_seconds: int = 180
    document_intel_ocr_per_page_timeout_seconds: int = 15
    document_intel_ocr_max_pages: int = 24
    document_intel_ocr_dpi: int = 220
    document_intel_ocr_trigger_min_chars: int = 1200

    # CORS
    cors_origins: str = "http://localhost:3000,http://localhost:8000"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]

    @property
    def scout_blocked_domains_set(self) -> set[str]:
        domains: set[str] = set()
        for raw in (self.scout_blocked_domains or "").split(","):
            host = raw.strip().lower()
            if not host:
                continue
            if host.startswith("www."):
                host = host[4:]
            domains.add(host)
        return domains

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        env_prefix = "ECHOROUK_OS_"


def _load_dotenv_pairs(dotenv_path: str = ".env") -> dict[str, str]:
    path = Path(dotenv_path)
    if not path.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            values[key] = value
    return values


def _bootstrap_prefixed_env() -> None:
    """Populate ECHOROUK_OS_ vars from legacy keys for backward compatibility."""
    legacy_pairs = _load_dotenv_pairs(".env")
    prefix = "ECHOROUK_OS_"

    for field_name in Settings.model_fields.keys():
        legacy_key = field_name.upper()
        prefixed_key = f"{prefix}{legacy_key}"

        if os.getenv(prefixed_key):
            continue

        legacy_value = os.getenv(legacy_key)
        if legacy_value is not None:
            os.environ[prefixed_key] = legacy_value
            continue

        if legacy_key in legacy_pairs:
            os.environ[prefixed_key] = legacy_pairs[legacy_key]


_bootstrap_prefixed_env()


@lru_cache()
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
