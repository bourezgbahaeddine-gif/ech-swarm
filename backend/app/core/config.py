"""
Echorouk AI Swarm — Configuration Module
==========================================
All configuration is loaded from environment variables.
Zero hardcoded secrets (Rule #2: Zero Trust Security).
"""

from functools import lru_cache
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from .env file."""

    # ── App ──
    app_name: str = "Echorouk AI Swarm"
    app_env: str = "development"
    app_debug: bool = True
    app_secret_key: str = Field(..., min_length=32)
    app_port: int = 8000

    @property
    def secret_key(self) -> str:
        return self.app_secret_key

    # ── Database ──
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

    # ── Redis ──
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str = ""
    redis_db: int = 0

    @property
    def redis_url(self) -> str:
        auth = f":{self.redis_password}@" if self.redis_password else ""
        return f"redis://{auth}{self.redis_host}:{self.redis_port}/{self.redis_db}"

    # ── AI Services ──
    gemini_api_key: str = ""
    gemini_model_flash: str = "gemini-1.5-flash"
    gemini_model_pro: str = "gemini-1.5-pro"
    groq_api_key: str = ""

    # ── Telegram Notifications ──
    telegram_bot_token: str = ""
    telegram_channel_editors: str = ""
    telegram_channel_alerts: str = ""
    slack_webhook_url: str = ""

    # ── MinIO ──
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "echorouk-media"
    minio_use_ssl: bool = False

    # ── Scheduling ──
    scout_interval_minutes: int = 30
    trend_radar_interval_minutes: int = 15

    # ── FreshRSS / RSS-Bridge ──
    scout_use_freshrss: bool = False
    freshrss_feed_url: str = "http://freshrss:80/p/i/?a=rss&state=all"
    rssbridge_base_url: str = "http://rssbridge:80"
    rssbridge_enabled: bool = True

    # ── Processing Thresholds ──
    dedup_similarity_threshold: float = 0.70
    breaking_news_urgency_threshold: int = 8
    truth_score_reject_threshold: float = 0.4
    truth_score_verify_threshold: float = 0.8
    max_rss_sources: int = 300
    rss_fetch_timeout: int = 30
    scout_batch_size: int = 8
    scout_concurrency: int = 8
    scout_max_new_per_run: int = 250

    # ── TTS ──
    tts_voice: str = "ar-DZ-IsmaelNeural"
    tts_rate: str = "+0%"
    tts_pitch: str = "+0Hz"

    # ── CORS ──
    cors_origins: str = "http://localhost:3000,http://localhost:8000"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
