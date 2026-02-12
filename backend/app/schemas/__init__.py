"""
Echorouk AI Swarm — Pydantic Schemas
======================================
Request/Response schemas for the API layer.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, HttpUrl


# ── Source Schemas ──

class SourceCreate(BaseModel):
    name: str = Field(..., max_length=255)
    slug: Optional[str] = None
    method: str = Field("rss", pattern="^(rss|scraper)$")
    url: str = Field(..., max_length=1024)
    rss_url: Optional[str] = None
    category: str = "general"
    language: str = "ar"
    languages: Optional[str] = None
    region: Optional[str] = None
    source_type: Optional[str] = None
    description: Optional[str] = None
    trust_score: float = Field(0.5, ge=0, le=1)
    credibility: str = "medium"
    priority: int = Field(5, ge=1, le=10)
    enabled: bool = True
    fetch_interval_minutes: int = 30


class SourceResponse(BaseModel):
    id: int
    name: str
    slug: Optional[str] = None
    method: str
    url: str
    rss_url: Optional[str] = None
    category: str
    language: str
    languages: Optional[str] = None
    region: Optional[str] = None
    source_type: Optional[str] = None
    description: Optional[str] = None
    trust_score: float
    credibility: str
    priority: int
    enabled: bool
    fetch_interval_minutes: int
    last_fetched_at: Optional[datetime] = None
    error_count: int
    created_at: datetime

    class Config:
        from_attributes = True


class SourceUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    method: Optional[str] = None
    rss_url: Optional[str] = None
    category: Optional[str] = None
    trust_score: Optional[float] = None
    credibility: Optional[str] = None
    languages: Optional[str] = None
    region: Optional[str] = None
    source_type: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[int] = None
    enabled: Optional[bool] = None
    fetch_interval_minutes: Optional[int] = None


# ── Article Schemas ──

class ArticleResponse(BaseModel):
    id: int
    unique_hash: str
    original_title: str
    original_url: str
    published_at: Optional[datetime] = None
    crawled_at: datetime
    source_name: Optional[str] = None
    title_ar: Optional[str] = None
    summary: Optional[str] = None
    body_html: Optional[str] = None
    category: Optional[str] = None
    importance_score: int
    urgency: Optional[str] = None
    is_breaking: bool
    sentiment: Optional[str] = None
    truth_score: Optional[float] = None
    entities: list = []
    keywords: list = []
    seo_title: Optional[str] = None
    seo_description: Optional[str] = None
    status: str
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    published_url: Optional[str] = None
    processing_time_ms: Optional[int] = None
    ai_model_used: Optional[str] = None
    trace_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ArticleBrief(BaseModel):
    """Lightweight article response for list views."""
    id: int
    title_ar: Optional[str] = None
    original_title: str
    original_url: Optional[str] = None
    source_name: Optional[str] = None
    category: Optional[str] = None
    importance_score: int
    urgency: Optional[str] = None
    is_breaking: bool
    status: str
    crawled_at: datetime
    created_at: datetime
    summary: Optional[str] = None

    class Config:
        from_attributes = True


# ── Editorial Schemas ──

class EditorDecisionCreate(BaseModel):
    editor_name: str = Field(..., max_length=255)
    decision: str = Field(..., pattern="^(approve|reject|rewrite)$")
    reason: Optional[str] = None
    edited_title: Optional[str] = None
    edited_body: Optional[str] = None


class EditorDecisionResponse(BaseModel):
    id: int
    article_id: int
    editor_name: str
    decision: str
    reason: Optional[str] = None
    decided_at: datetime

    class Config:
        from_attributes = True


# ── AI Analysis Schema ──

class AIAnalysisResult(BaseModel):
    """Output schema from Gemini/Groq AI analysis."""
    title_ar: str = ""
    summary: str = ""
    category: str = "local_algeria"
    importance_score: int = Field(5, ge=1, le=10)
    is_breaking: bool = False
    entities: list[str] = []
    keywords: list[str] = []
    sentiment: str = "neutral"


# ── Dashboard Schemas ──

class DashboardStats(BaseModel):
    total_articles: int = 0
    articles_today: int = 0
    pending_review: int = 0
    approved: int = 0
    rejected: int = 0
    published: int = 0
    breaking_news: int = 0
    sources_active: int = 0
    sources_total: int = 0
    ai_calls_today: int = 0
    avg_processing_ms: Optional[float] = None


class PipelineRunResponse(BaseModel):
    id: int
    run_type: str
    started_at: datetime
    finished_at: Optional[datetime] = None
    total_items: int
    new_items: int
    duplicates: int
    errors: int
    ai_calls: int
    status: str

    class Config:
        from_attributes = True


# ── Trend Radar Schemas ──

class TrendAlert(BaseModel):
    keyword: str
    source_signals: list[str] = []
    strength: int = Field(5, ge=1, le=10)
    reason: Optional[str] = None
    suggested_angles: list[str] = []
    archive_matches: list[str] = []
    detected_at: datetime = Field(default_factory=datetime.utcnow)


# ── General ──

class PaginatedResponse(BaseModel):
    items: list = []
    total: int = 0
    page: int = 1
    per_page: int = 20
    pages: int = 0


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "1.0.0"
    database: str = "connected"
    redis: str = "connected"
    uptime_seconds: float = 0


# ——— API Settings Schemas ———

class ApiSettingResponse(BaseModel):
    key: str
    value: Optional[str] = None
    description: Optional[str] = None
    is_secret: bool = True
    has_value: bool = False
    updated_at: Optional[datetime] = None


class ApiSettingUpsert(BaseModel):
    value: Optional[str] = None
    description: Optional[str] = None
    is_secret: Optional[bool] = None


class SettingsAuditResponse(BaseModel):
    id: int
    key: str
    action: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    actor: Optional[str] = None
    created_at: Optional[datetime] = None


class ConstitutionMetaResponse(BaseModel):
    version: str
    file_url: str
    updated_at: Optional[datetime] = None


class ConstitutionAckResponse(BaseModel):
    acknowledged: bool
    version: Optional[str] = None


class ConstitutionAckRequest(BaseModel):
    version: str
