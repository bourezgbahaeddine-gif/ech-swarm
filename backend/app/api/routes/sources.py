"""
Echorouk Editorial OS -- Sources API Routes
======================================
CRUD operations for RSS/news sources.
"""

from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import urlparse
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import case, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.models import Article, NewsStatus, Source
from app.schemas import SourceCreate, SourceResponse, SourceUpdate
from app.services.cache_service import cache_service

router = APIRouter(prefix="/sources", tags=["Sources"])
settings = get_settings()


def _normalize_domain(value: str | None) -> str:
    host = (value or "").strip().lower()
    if not host:
        return ""
    if "://" not in host:
        host = f"https://{host}"
    try:
        parsed = urlparse(host)
    except Exception:
        return ""
    netloc = (parsed.netloc or "").lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return netloc


def _source_aliases(source: Source) -> set[str]:
    aliases = {
        (source.name or "").strip().lower(),
        (source.slug or "").strip().lower(),
        _normalize_domain(source.url),
        _normalize_domain(source.rss_url),
    }
    return {a for a in aliases if a}


def _score_band(score: float) -> str:
    if score >= 80:
        return "excellent"
    if score >= 60:
        return "good"
    if score >= 40:
        return "review"
    return "weak"


def _safe_ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(float(numerator) / float(denominator), 4)


def _health_score(
    *,
    trust_score: float,
    error_count: int,
    ingested_count: int,
    candidate_rate: float,
    breaking_rate: float,
    last_seen_hours: Optional[float],
) -> float:
    trust_component = max(0.0, min(1.0, trust_score)) * 35.0
    candidate_component = max(0.0, min(1.0, candidate_rate)) * 35.0
    breaking_component = min(10.0, breaking_rate * 100.0)
    volume_component = min(20.0, ingested_count * 0.8)
    error_penalty = min(30.0, max(0, error_count) * 6.0)
    stale_penalty = 0.0
    if last_seen_hours is None:
        stale_penalty = 25.0
    elif last_seen_hours > 72:
        stale_penalty = 25.0
    elif last_seen_hours > 24:
        stale_penalty = 12.0
    raw_score = trust_component + candidate_component + breaking_component + volume_component - error_penalty - stale_penalty
    return round(max(0.0, min(100.0, raw_score)), 1)


def _health_actions(
    *,
    source: Source,
    score: float,
    ingested_count: int,
    candidate_rate: float,
    last_seen_hours: Optional[float],
) -> list[str]:
    actions: list[str] = []
    if source.enabled and ingested_count == 0 and ((source.error_count or 0) >= 3 or (last_seen_hours is not None and last_seen_hours > 72)):
        actions.append("disable_temporarily")
    if score < 45 and source.priority > 3:
        actions.append("decrease_priority")
    if score >= 80 and source.priority < 8 and candidate_rate >= 0.2:
        actions.append("increase_priority")
    if (not source.enabled) and score >= 70 and ingested_count >= 5:
        actions.append("re_enable")
    return actions


@router.get("/", response_model=list[SourceResponse])
async def list_sources(
    enabled: Optional[bool] = None,
    category: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """List all registered news sources."""
    query = select(Source).order_by(Source.priority.desc())

    if enabled is not None:
        query = query.where(Source.enabled == enabled)
    if category:
        query = query.where(Source.category == category)

    result = await db.execute(query)
    sources = result.scalars().all()
    return [SourceResponse.model_validate(s) for s in sources]


@router.post("/", response_model=SourceResponse, status_code=201)
async def create_source(data: SourceCreate, db: AsyncSession = Depends(get_db)):
    """Register a new news source."""
    # Check for duplicate URL
    existing = await db.execute(select(Source).where(Source.url == data.url))
    if existing.scalar_one_or_none():
        raise HTTPException(409, "Source URL already registered")

    source = Source(**data.model_dump())
    db.add(source)
    await db.commit()
    await db.refresh(source)
    return SourceResponse.model_validate(source)


@router.put("/{source_id}", response_model=SourceResponse)
async def update_source(source_id: int, data: SourceUpdate, db: AsyncSession = Depends(get_db)):
    """Update a news source."""
    result = await db.execute(select(Source).where(Source.id == source_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(404, "Source not found")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(source, key, value)

    await db.commit()
    await db.refresh(source)
    return SourceResponse.model_validate(source)


@router.delete("/{source_id}")
async def delete_source(source_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a news source."""
    result = await db.execute(select(Source).where(Source.id == source_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(404, "Source not found")

    await db.delete(source)
    await db.commit()
    return {"message": "Source deleted"}


@router.get("/stats")
async def sources_stats(db: AsyncSession = Depends(get_db)):
    """Get source statistics."""
    cached = await cache_service.get_json("sources:stats")
    if cached:
        return cached

    total = await db.execute(select(func.count(Source.id)))
    active = await db.execute(
        select(func.count(Source.id)).where(Source.enabled == True)
    )
    categories = await db.execute(
        select(Source.category, func.count(Source.id))
        .group_by(Source.category)
    )

    stats = {
        "total": total.scalar(),
        "active": active.scalar(),
        "by_category": dict(categories.all()),
    }
    await cache_service.set_json("sources:stats", stats, ttl=timedelta(seconds=60))
    return stats


@router.get("/health")
async def sources_health(
    hours: int = 48,
    include_disabled: bool = True,
    db: AsyncSession = Depends(get_db),
):
    """Return operational quality metrics per source with actionable recommendations."""
    hours = max(6, min(hours, 168))
    since = datetime.utcnow() - timedelta(hours=hours)

    source_query = select(Source).order_by(Source.priority.desc(), Source.id.asc())
    if not include_disabled:
        source_query = source_query.where(Source.enabled == True)
    source_result = await db.execute(source_query)
    sources = source_result.scalars().all()

    candidate_statuses = [
        NewsStatus.CANDIDATE,
        NewsStatus.APPROVED,
        NewsStatus.APPROVED_HANDOFF,
        NewsStatus.DRAFT_GENERATED,
        NewsStatus.READY_FOR_CHIEF_APPROVAL,
        NewsStatus.APPROVAL_REQUEST_WITH_RESERVATIONS,
        NewsStatus.READY_FOR_MANUAL_PUBLISH,
        NewsStatus.PUBLISHED,
    ]
    article_rows_result = await db.execute(
        select(
            func.lower(func.coalesce(Article.source_name, "")).label("source_name"),
            func.count(Article.id).label("ingested_count"),
            func.sum(case((Article.status.in_(candidate_statuses), 1), else_=0)).label("candidate_count"),
            func.sum(case((Article.is_breaking == True, 1), else_=0)).label("breaking_count"),
            func.max(Article.created_at).label("last_seen_at"),
        )
        .where(Article.created_at >= since)
        .group_by(func.lower(func.coalesce(Article.source_name, "")))
    )
    source_rows = [
        {
            "source_name": (row.source_name or "").strip().lower(),
            "ingested_count": int(row.ingested_count or 0),
            "candidate_count": int(row.candidate_count or 0),
            "breaking_count": int(row.breaking_count or 0),
            "last_seen_at": row.last_seen_at,
        }
        for row in article_rows_result.all()
    ]

    blocked_domains = sorted(settings.scout_blocked_domains_set)

    items = []
    now = datetime.utcnow()
    for source in sources:
        aliases = _source_aliases(source)
        matched = []
        for row in source_rows:
            row_name = row["source_name"]
            if not row_name:
                continue
            if any(alias in row_name or row_name in alias for alias in aliases):
                matched.append(row)

        ingested_count = sum(x["ingested_count"] for x in matched)
        candidate_count = sum(x["candidate_count"] for x in matched)
        breaking_count = sum(x["breaking_count"] for x in matched)
        latest_seen = max((x["last_seen_at"] for x in matched if x["last_seen_at"] is not None), default=None)
        candidate_rate = _safe_ratio(candidate_count, ingested_count)
        breaking_rate = _safe_ratio(breaking_count, ingested_count)

        last_seen_hours = None
        if latest_seen is not None:
            last_seen_hours = round((now - latest_seen).total_seconds() / 3600.0, 2)

        score = _health_score(
            trust_score=float(source.trust_score or 0.0),
            error_count=int(source.error_count or 0),
            ingested_count=ingested_count,
            candidate_rate=candidate_rate,
            breaking_rate=breaking_rate,
            last_seen_hours=last_seen_hours,
        )
        actions = _health_actions(
            source=source,
            score=score,
            ingested_count=ingested_count,
            candidate_rate=candidate_rate,
            last_seen_hours=last_seen_hours,
        )
        source_domain = _normalize_domain(source.url)
        if source_domain and source_domain in blocked_domains:
            actions.append("blocked_by_policy")

        items.append(
            {
                "source_id": source.id,
                "name": source.name,
                "domain": source_domain,
                "enabled": bool(source.enabled),
                "priority": int(source.priority or 0),
                "trust_score": round(float(source.trust_score or 0.0), 3),
                "error_count": int(source.error_count or 0),
                "window_hours": hours,
                "ingested_count": ingested_count,
                "candidate_count": candidate_count,
                "breaking_count": breaking_count,
                "candidate_rate": candidate_rate,
                "breaking_rate": breaking_rate,
                "last_seen_at": latest_seen.isoformat() if latest_seen else None,
                "last_seen_hours": last_seen_hours,
                "health_score": score,
                "health_band": _score_band(score),
                "actions": actions,
            }
        )

    items.sort(key=lambda x: (x["health_score"], -x["ingested_count"], x["name"].lower()))

    return {
        "window_hours": hours,
        "blocked_domains": blocked_domains,
        "total_sources": len(items),
        "weak_sources": sum(1 for x in items if x["health_band"] in {"weak", "review"}),
        "items": items,
    }
