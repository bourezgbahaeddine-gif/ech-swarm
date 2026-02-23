"""
Echorouk Editorial OS -- Sources API Routes
======================================
CRUD operations for RSS/news sources.
"""

from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import urlparse
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.auth import get_current_user
from app.core.config import get_settings
from app.core.database import get_db
from app.models.audit import SettingsAudit
from app.models import Article, NewsStatus, Source
from app.models.settings import ApiSetting
from app.models.user import User, UserRole
from app.schemas import SourceCreate, SourceResponse, SourceUpdate
from app.services.cache_service import cache_service
from app.services.settings_service import settings_service

router = APIRouter(prefix="/sources", tags=["Sources"])
settings = get_settings()
POLICY_KEY_BLOCKED = "SCOUT_BLOCKED_DOMAINS"
POLICY_KEY_FRESHRSS_CAP = "SCOUT_FRESHRSS_MAX_PER_SOURCE_PER_RUN"


def _ensure_director(user: User) -> None:
    if user.role != UserRole.director:
        raise HTTPException(status_code=403, detail="Not authorized")


def _normalize_domains_input(values: list[str] | None) -> list[str]:
    normalized = []
    seen = set()
    for value in values or []:
        domain = _normalize_domain(value)
        if not domain:
            continue
        if domain in seen:
            continue
        seen.add(domain)
        normalized.append(domain)
    return normalized


def _split_csv_domains(value: str | None) -> list[str]:
    items = []
    for part in (value or "").split(","):
        part = part.strip()
        if not part:
            continue
        items.append(part)
    return _normalize_domains_input(items)


async def _read_policy_values() -> dict:
    blocked_csv = await settings_service.get_value(
        POLICY_KEY_BLOCKED,
        settings.scout_blocked_domains,
    )
    freshrss_cap_raw = await settings_service.get_value(
        POLICY_KEY_FRESHRSS_CAP,
        str(settings.scout_freshrss_max_per_source_per_run),
    )
    try:
        freshrss_cap = int(freshrss_cap_raw or settings.scout_freshrss_max_per_source_per_run)
    except (TypeError, ValueError):
        freshrss_cap = settings.scout_freshrss_max_per_source_per_run
    freshrss_cap = max(1, min(freshrss_cap, 100))
    return {
        "blocked_domains": _split_csv_domains(blocked_csv),
        "freshrss_max_per_source_per_run": freshrss_cap,
    }


async def _upsert_setting(
    db: AsyncSession,
    *,
    key: str,
    value: str,
    actor: str,
    description: str,
) -> None:
    result = await db.execute(select(ApiSetting).where(ApiSetting.key == key))
    row = result.scalar_one_or_none()
    old_value = row.value if row else None
    if row is None:
        row = ApiSetting(
            key=key,
            value=value,
            description=description,
            is_secret=False,
            updated_at=datetime.utcnow(),
        )
        db.add(row)
        action = "create"
    else:
        row.value = value
        row.description = description
        row.is_secret = False
        row.updated_at = datetime.utcnow()
        action = "update"
    db.add(
        SettingsAudit(
            key=key,
            action=action,
            old_value=old_value,
            new_value=value,
            actor=actor,
        )
    )
    await settings_service.set_value(key, value)


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


def _candidate_statuses() -> list[NewsStatus]:
    return [
        NewsStatus.CANDIDATE,
        NewsStatus.APPROVED,
        NewsStatus.APPROVED_HANDOFF,
        NewsStatus.DRAFT_GENERATED,
        NewsStatus.READY_FOR_CHIEF_APPROVAL,
        NewsStatus.APPROVAL_REQUEST_WITH_RESERVATIONS,
        NewsStatus.READY_FOR_MANUAL_PUBLISH,
        NewsStatus.PUBLISHED,
    ]


async def _compute_sources_health(
    db: AsyncSession,
    *,
    hours: int,
    include_disabled: bool,
) -> dict:
    policy = await _read_policy_values()
    since = datetime.utcnow() - timedelta(hours=hours)

    source_query = select(Source).order_by(Source.priority.desc(), Source.id.asc())
    if not include_disabled:
        source_query = source_query.where(Source.enabled == True)
    source_result = await db.execute(source_query)
    sources = source_result.scalars().all()

    source_name_expr = func.lower(func.coalesce(Article.source_name, ""))
    article_rows_result = await db.execute(
        select(
            source_name_expr.label("source_name"),
            func.count(Article.id).label("ingested_count"),
            func.sum(case((Article.status.in_(_candidate_statuses()), 1), else_=0)).label("candidate_count"),
            func.sum(case((Article.is_breaking == True, 1), else_=0)).label("breaking_count"),
            func.max(Article.created_at).label("last_seen_at"),
        )
        .where(Article.created_at >= since)
        .group_by(source_name_expr)
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

    blocked_domains = sorted(policy["blocked_domains"])

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


@router.put("/{source_id:int}", response_model=SourceResponse)
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


@router.delete("/{source_id:int}")
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


@router.get("/policy")
async def get_sources_policy(
    current_user: User = Depends(get_current_user),
):
    """Get source ingestion policy values."""
    _ensure_director(current_user)
    policy = await _read_policy_values()
    return policy


@router.put("/policy")
async def update_sources_policy(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update source ingestion policy (blocked domains and FreshRSS source cap)."""
    _ensure_director(current_user)

    blocked_domains = _normalize_domains_input(payload.get("blocked_domains"))
    if not blocked_domains:
        blocked_domains = _split_csv_domains(settings.scout_blocked_domains)

    freshrss_cap = payload.get("freshrss_max_per_source_per_run", settings.scout_freshrss_max_per_source_per_run)
    try:
        freshrss_cap = int(freshrss_cap)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid freshrss_max_per_source_per_run")
    freshrss_cap = max(1, min(freshrss_cap, 100))

    await _upsert_setting(
        db,
        key=POLICY_KEY_BLOCKED,
        value=",".join(blocked_domains),
        actor=current_user.username,
        description="CSV domains blocked from scout ingestion.",
    )
    await _upsert_setting(
        db,
        key=POLICY_KEY_FRESHRSS_CAP,
        value=str(freshrss_cap),
        actor=current_user.username,
        description="Max new FreshRSS entries per source per run.",
    )
    await db.commit()

    return {
        "blocked_domains": blocked_domains,
        "freshrss_max_per_source_per_run": freshrss_cap,
        "updated_by": current_user.username,
        "updated_at": datetime.utcnow().isoformat(),
    }


@router.get("/health")
async def sources_health(
    hours: int = 48,
    include_disabled: bool = True,
    db: AsyncSession = Depends(get_db),
):
    """Return operational quality metrics per source with actionable recommendations."""
    hours = max(6, min(hours, 168))
    return await _compute_sources_health(
        db,
        hours=hours,
        include_disabled=include_disabled,
    )


@router.post("/health/apply")
async def apply_sources_health_actions(
    hours: int = Query(default=48, ge=6, le=168),
    include_disabled: bool = True,
    dry_run: bool = True,
    max_changes: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Apply source tuning actions derived from health score."""
    _ensure_director(current_user)
    report = await _compute_sources_health(
        db,
        hours=hours,
        include_disabled=include_disabled,
    )

    result = await db.execute(select(Source))
    source_map = {s.id: s for s in result.scalars().all()}

    changed = []
    for item in report["items"]:
        if len(changed) >= max_changes:
            break
        source = source_map.get(item["source_id"])
        if not source:
            continue
        before_enabled = bool(source.enabled)
        before_priority = int(source.priority or 0)
        after_enabled = before_enabled
        after_priority = before_priority

        for action in item["actions"]:
            if action == "disable_temporarily":
                after_enabled = False
            elif action == "re_enable":
                after_enabled = True
            elif action == "decrease_priority":
                after_priority = max(1, after_priority - 1)
            elif action == "increase_priority":
                after_priority = min(10, after_priority + 1)

        if after_enabled == before_enabled and after_priority == before_priority:
            continue

        changed.append(
            {
                "source_id": source.id,
                "name": source.name,
                "actions": item["actions"],
                "before": {"enabled": before_enabled, "priority": before_priority},
                "after": {"enabled": after_enabled, "priority": after_priority},
                "health_score": item["health_score"],
                "health_band": item["health_band"],
            }
        )
        if not dry_run:
            source.enabled = after_enabled
            source.priority = after_priority

    if not dry_run and changed:
        await db.commit()

    return {
        "dry_run": dry_run,
        "hours": hours,
        "candidate_changes": len(changed),
        "applied_changes": 0 if dry_run else len(changed),
        "items": changed,
    }
