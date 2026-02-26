"""
Echorouk Editorial OS — News API Routes
=====================================
CRUD operations for articles with filtering & pagination.
"""

from datetime import datetime, timedelta
import hashlib
import math
import re
import unicodedata
from urllib.parse import urlparse, urlunparse
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, select, func, desc, and_, or_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.models import (
    Article,
    ArticleRelation,
    ArticleVector,
    NewsCategory,
    NewsStatus,
    StoryCluster,
    StoryClusterMember,
    UrgencyLevel,
)
from app.schemas import ArticleResponse, ArticleBrief, PaginatedResponse
from app.services.trend_signal_service import bump_keyword_interactions, extract_keywords

router = APIRouter(prefix="/news", tags=["News"])
settings = get_settings()
TOKEN_RE = re.compile(r"[\u0600-\u06FFA-Za-z\u00C0-\u024F0-9]{2,}")
SPACE_RE = re.compile(r"\s+")
STOPWORDS = {
    # Arabic
    "في", "من", "على", "الى", "إلى", "عن", "مع", "هذا", "هذه", "ذلك", "تلك",
    "بعد", "قبل", "بين", "حول", "حتى", "أو", "و", "التي", "الذي", "الذين",
    # French
    "les", "des", "dans", "avec", "pour", "sur", "une", "un", "du", "de", "et",
    # English
    "the", "and", "for", "with", "from", "into", "over", "under", "that", "this",
}
SYNONYMS = {
    # Arabic <-> French/English newsroom concepts
    "الطاقة": {"طاقة", "الطاقوية", "الطاقي", "energie", "énergie", "energetique", "énergétique", "energy"},
    "طاقة": {"الطاقة", "الطاقوية", "الطاقي", "energie", "énergie", "energetique", "énergétique", "energy"},
    "الجزائر": {"جزائر", "algerie", "algérie", "algeria", "algérien", "algerien"},
    "جزائر": {"الجزائر", "algerie", "algérie", "algeria", "algérien", "algerien"},
}

LOCAL_PRIORITY_TERMS = [
    "الجزائر",
    "جزائري",
    "جزائرية",
    "algeria",
    "algerie",
    "algérie",
    "dz",
    "رئاسة الجمهورية",
    "الوزير الأول",
    "سوناطراك",
    "وزارة",
]

LOCAL_PRIORITY_SOURCES = [
    "echorouk",
    "الشروق",
    "aps",
    "tsa",
    "el khabar",
    "الخبر",
    "النهار",
]


def _query_embedding(text: str, dim: int = 256) -> list[float]:
    base = hashlib.sha256((text or "").encode("utf-8")).digest()
    values = []
    seed = base
    while len(values) < dim:
        seed = hashlib.sha256(seed).digest()
        for b in seed:
            values.append((b / 255.0) * 2.0 - 1.0)
            if len(values) >= dim:
                break
    norm = math.sqrt(sum(v * v for v in values)) or 1.0
    return [v / norm for v in values]


def _tokenize(text: str) -> set[str]:
    return {m.group(0).lower() for m in TOKEN_RE.finditer(text or "")}


def _normalize_text(text: str | None) -> str:
    if not text:
        return ""
    t = (text or "").strip().lower()
    # Fold accents so "énergie" and "energie" match consistently.
    t = unicodedata.normalize("NFKD", t)
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    return SPACE_RE.sub(" ", t)


def _token_forms(token: str) -> set[str]:
    token_norm = _normalize_text(token)
    forms = {token_norm}
    # Arabic definite article normalization: "الطاقة" -> "طاقة"
    if token_norm.startswith("ال") and len(token_norm) > 4:
        forms.add(token_norm[2:])
    forms |= {_normalize_text(x) for x in SYNONYMS.get(token_norm, set())}
    return {f for f in forms if f}


def _matched_query_tokens(query_tokens: set[str], text_tokens: set[str], text_norm: str) -> set[str]:
    matched: set[str] = set()
    for token in query_tokens:
        forms = _token_forms(token)
        if any(f in text_tokens for f in forms):
            matched.add(token)
            continue
        # Fallback for derivations (e.g., طاقة / الطاقوية)
        if any(len(f) >= 4 and f in text_norm for f in forms):
            matched.add(token)
    return matched


def _is_geo_token(token: str) -> bool:
    t = _normalize_text(token)
    return t in {"الجزائر", "جزائر", "algerie", "algeria"}


def _canonical_url(url: str | None) -> str:
    if not url:
        return ""
    try:
        parsed = urlparse(url.strip())
        return urlunparse(parsed._replace(query="", fragment=""))
    except Exception:
        return url


def _source_trust(source_name: str | None) -> float:
    s = (source_name or "").lower()
    if not s:
        return 0.4
    trusted = [
        "aps", "reuters", "bbc", "france24", "le monde", "guardian", "echorouk", "el khabar",
    ]
    low = ["news.google.com", "google news", "aggregator", "reddit"]
    if any(k in s for k in trusted):
        return 1.0
    if any(k in s for k in low):
        return 0.25
    return 0.6


def _is_aggregator_source(source_name: str | None) -> bool:
    s = (source_name or "").lower()
    return "news.google.com" in s or "google news" in s or "aggregator" in s


def _local_priority_expression():
    title_match = or_(*[Article.original_title.ilike(f"%{term}%") for term in LOCAL_PRIORITY_TERMS])
    arabic_title_match = or_(*[Article.title_ar.ilike(f"%{term}%") for term in LOCAL_PRIORITY_TERMS])
    summary_match = or_(*[Article.summary.ilike(f"%{term}%") for term in LOCAL_PRIORITY_TERMS])
    source_match = or_(*[Article.source_name.ilike(f"%{term}%") for term in LOCAL_PRIORITY_SOURCES])
    category_local = Article.category == NewsCategory.LOCAL_ALGERIA
    return case(
        (category_local, 4),
        (source_match, 3),
        (title_match, 2),
        (arabic_title_match, 2),
        (summary_match, 1),
        else_=0,
    )


async def _expire_stale_breaking_flags(db: AsyncSession) -> None:
    cutoff = datetime.utcnow() - timedelta(minutes=settings.breaking_news_ttl_minutes)
    await db.execute(
        update(Article)
        .where(
            and_(
                Article.is_breaking == True,
                func.coalesce(Article.published_at, Article.crawled_at) < cutoff,
            )
        )
        .values(
            is_breaking=False,
            urgency=UrgencyLevel.HIGH,
            updated_at=datetime.utcnow(),
        )
    )
    await db.commit()


@router.get("/", response_model=PaginatedResponse)
async def list_articles(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    category: Optional[str] = None,
    is_breaking: Optional[bool] = None,
    search: Optional[str] = None,
    sort_by: str = Query("created_at", regex="^(created_at|crawled_at|importance_score|published_at)$"),
    local_first: bool = Query(True),
    db: AsyncSession = Depends(get_db),
):
    """List articles with filtering and pagination."""
    if is_breaking:
        await _expire_stale_breaking_flags(db)

    query = select(Article)
    count_query = select(func.count(Article.id))
    breaking_cutoff = datetime.utcnow() - timedelta(minutes=settings.breaking_news_ttl_minutes)
    freshness_cutoff = datetime.utcnow() - timedelta(hours=settings.scout_max_article_age_hours)
    actionable_breaking_statuses = [NewsStatus.NEW, NewsStatus.CLASSIFIED, NewsStatus.CANDIDATE]
    newsroom_fresh_statuses = [NewsStatus.NEW, NewsStatus.CLASSIFIED, NewsStatus.CANDIDATE]

    # Apply filters
    filters = []
    if status:
        try:
            selected_status = NewsStatus(status)
            filters.append(Article.status == selected_status)
            if selected_status in newsroom_fresh_statuses:
                filters.append(func.coalesce(Article.published_at, Article.crawled_at) >= freshness_cutoff)
        except ValueError:
            raise HTTPException(400, f"Invalid status: {status}")
    else:
        # Keep newsroom list focused by hiding auto-archived noise by default.
        filters.append(Article.status != NewsStatus.ARCHIVED)
        filters.append(
            or_(
                Article.status.notin_(newsroom_fresh_statuses),
                func.coalesce(Article.published_at, Article.crawled_at) >= freshness_cutoff,
            )
        )
    if category:
        try:
            filters.append(Article.category == NewsCategory(category))
        except ValueError:
            raise HTTPException(400, f"Invalid category: {category}")
    if is_breaking is not None:
        filters.append(Article.is_breaking == is_breaking)
        if is_breaking:
            filters.append(Article.crawled_at >= breaking_cutoff)
            if not status:
                filters.append(Article.status.in_(actionable_breaking_statuses))
    if search:
        search_filter = Article.original_title.ilike(f"%{search}%")
        if Article.title_ar:
            search_filter = search_filter | Article.title_ar.ilike(f"%{search}%")
        filters.append(search_filter)

    if filters:
        query = query.where(and_(*filters))
        count_query = count_query.where(and_(*filters))

    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # Sort and paginate
    sort_column = getattr(Article, sort_by)
    if local_first and not status:
        local_priority = _local_priority_expression()
        query = query.order_by(desc(local_priority), desc(sort_column))
    else:
        query = query.order_by(desc(sort_column))
    query = query.offset((page - 1) * per_page).limit(per_page)

    result = await db.execute(query)
    articles = result.scalars().all()

    return PaginatedResponse(
        items=[ArticleBrief.model_validate(a) for a in articles],
        total=total,
        page=page,
        per_page=per_page,
        pages=(total + per_page - 1) // per_page,
    )


@router.get("/breaking/latest")
async def get_breaking_news(
    limit: int = Query(5, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
):
    """Get actionable breaking news for dashboard newsroom workflow."""
    await _expire_stale_breaking_flags(db)
    cutoff = datetime.utcnow() - timedelta(minutes=settings.breaking_news_ttl_minutes)
    actionable_breaking_statuses = [NewsStatus.NEW, NewsStatus.CLASSIFIED, NewsStatus.CANDIDATE]
    result = await db.execute(
        select(Article)
        .where(
            and_(
                Article.is_breaking == True,
                func.coalesce(Article.published_at, Article.crawled_at) >= cutoff,
                Article.status.in_(actionable_breaking_statuses),
            )
        )
        .order_by(desc(Article.crawled_at))
        .limit(limit)
    )
    articles = result.scalars().all()
    return [ArticleBrief.model_validate(a) for a in articles]


@router.get("/candidates/pending")
async def get_pending_candidates(
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Get articles pending editorial review."""
    result = await db.execute(
        select(Article)
        .where(Article.status == NewsStatus.CANDIDATE)
        .order_by(desc(Article.importance_score), desc(Article.created_at))
        .limit(limit)
    )
    articles = result.scalars().all()
    return [ArticleBrief.model_validate(a) for a in articles]


@router.get("/insights")
async def news_insights(
    article_ids: list[int] = Query(default=[]),
    db: AsyncSession = Depends(get_db),
):
    """
    Return lightweight per-article insights for newsroom cards:
    - cluster_size: number of members in the same story cluster
    - relation_count: number of explicit outgoing relations
    """
    ids = [int(x) for x in article_ids if int(x) > 0]
    if not ids:
        return []

    sm_self = StoryClusterMember.__table__.alias("sm_self")
    sm_all = StoryClusterMember.__table__.alias("sm_all")

    cluster_rows = await db.execute(
        select(
            sm_self.c.article_id.label("article_id"),
            sm_self.c.cluster_id.label("cluster_id"),
            func.count(sm_all.c.article_id).label("cluster_size"),
        )
        .select_from(sm_self.join(sm_all, sm_self.c.cluster_id == sm_all.c.cluster_id))
        .where(sm_self.c.article_id.in_(ids))
        .group_by(sm_self.c.article_id, sm_self.c.cluster_id)
    )
    cluster_map: dict[int, dict[str, int]] = {}
    for r in cluster_rows:
        aid = int(r.article_id)
        payload = {"cluster_size": int(r.cluster_size), "cluster_id": int(r.cluster_id)}
        prev = cluster_map.get(aid)
        if prev is None or payload["cluster_size"] > prev["cluster_size"]:
            cluster_map[aid] = payload

    relation_rows = await db.execute(
        select(
            ArticleRelation.from_article_id.label("article_id"),
            func.count(ArticleRelation.id).label("relation_count"),
        )
        .where(ArticleRelation.from_article_id.in_(ids))
        .group_by(ArticleRelation.from_article_id)
    )
    relation_map = {int(r.article_id): int(r.relation_count) for r in relation_rows}

    return [
        {
            "article_id": aid,
            "cluster_size": cluster_map.get(aid, {}).get("cluster_size", 0),
            "cluster_id": cluster_map.get(aid, {}).get("cluster_id"),
            "relation_count": relation_map.get(aid, 0),
        }
        for aid in ids
    ]


@router.get("/search/semantic")
async def semantic_search(
    q: str = Query(..., min_length=2),
    limit: int = Query(10, ge=1, le=50),
    status: Optional[str] = None,
    mode: str = Query("editorial", pattern="^(editorial|semantic)$"),
    include_aggregators: bool = Query(False),
    strict_tokens: bool = Query(True),
    db: AsyncSession = Depends(get_db),
):
    """
    Hybrid retrieval on vectorized title/summary with editorial ranking.
    """
    query_vec = _query_embedding(q, 256)
    query_tokens_raw = _tokenize(q)
    query_tokens = {t for t in query_tokens_raw if t not in STOPWORDS} or query_tokens_raw
    query_norm = _normalize_text(q)
    pool_size = max(limit * 25, 120)

    stmt = (
        select(
            Article,
            ArticleVector.embedding.cosine_distance(query_vec).label("dist"),
        )
        .join(ArticleVector, ArticleVector.article_id == Article.id)
        .where(ArticleVector.vector_type.in_(["title", "summary"]))
        .order_by(ArticleVector.embedding.cosine_distance(query_vec))
        .limit(pool_size)
    )
    if status:
        try:
            stmt = stmt.where(Article.status == NewsStatus(status))
        except ValueError:
            raise HTTPException(400, f"Invalid status: {status}")
    else:
        stmt = stmt.where(Article.status != NewsStatus.ARCHIVED)

    rows = await db.execute(stmt)
    raw_items = rows.all()

    # Keep best distance per article first (title+summary can duplicate article rows)
    best_by_article: dict[int, tuple[Article, float]] = {}
    for article, dist in raw_items:
        prev = best_by_article.get(article.id)
        if prev is None or dist < prev[1]:
            best_by_article[article.id] = (article, float(dist))

    now = datetime.utcnow()
    ranked: list[tuple[float, Article]] = []
    required_overlap = 0
    if mode == "editorial" and strict_tokens and len(query_tokens) >= 2:
        if len(query_tokens) <= 3:
            required_overlap = len(query_tokens)
        else:
            required_overlap = max(2, math.ceil(len(query_tokens) * 0.75))
    core_tokens = {t for t in query_tokens if not _is_geo_token(t)}

    def _build_ranked(min_overlap: int, require_title_overlap: bool, require_core_match: bool) -> list[tuple[float, Article]]:
        local_ranked: list[tuple[float, Article]] = []
        for article, dist in best_by_article.values():
            if mode == "editorial" and not include_aggregators and _is_aggregator_source(article.source_name):
                continue

            semantic = 1.0 - max(0.0, min(dist, 2.0)) / 2.0

            combined_text = " ".join([
                article.title_ar or "",
                article.original_title or "",
                article.summary or "",
            ])
            title_text = " ".join([article.title_ar or "", article.original_title or ""])
            text_tokens = _tokenize(combined_text)
            text_norm = _normalize_text(combined_text)
            matched_tokens = _matched_query_tokens(query_tokens, text_tokens, text_norm)
            overlap_count = len(matched_tokens)
            overlap = (overlap_count / max(1, len(query_tokens))) if query_tokens else 0.0
            phrase_hit = 1.0 if query_norm and query_norm in text_norm else 0.0

            if min_overlap and overlap_count < min_overlap:
                continue
            if require_core_match and core_tokens:
                core_matched = _matched_query_tokens(core_tokens, text_tokens, text_norm)
                if not core_matched:
                    continue

            title_tokens = _tokenize(title_text)
            title_norm = _normalize_text(title_text)
            title_overlap_count = len(_matched_query_tokens(query_tokens, title_tokens, title_norm))
            title_overlap = (title_overlap_count / max(1, len(query_tokens))) if query_tokens else 0.0
            if require_title_overlap and title_overlap_count == 0:
                continue

            trust = _source_trust(article.source_name)
            recency_hours = max(0.0, (now - (article.created_at or article.crawled_at or now)).total_seconds() / 3600.0)
            recency = math.exp(-recency_hours / 72.0)
            importance = max(0.0, min(1.0, (article.importance_score or 0) / 10.0))
            breaking = 1.0 if article.is_breaking else 0.0

            if mode == "editorial":
                score = (
                    0.15 * semantic
                    + 0.45 * overlap
                    + 0.10 * title_overlap
                    + 0.12 * phrase_hit
                    + 0.08 * recency
                    + 0.05 * trust
                    + 0.03 * importance
                    + 0.02 * breaking
                )
            else:
                score = (
                    0.70 * semantic
                    + 0.15 * overlap
                    + 0.10 * recency
                    + 0.05 * trust
                )
            local_ranked.append((score, article))
        local_ranked.sort(key=lambda x: x[0], reverse=True)
        return local_ranked

    ranked = _build_ranked(
        min_overlap=required_overlap,
        require_title_overlap=(mode == "editorial" and strict_tokens and len(query_tokens) >= 2),
        require_core_match=(mode == "editorial" and strict_tokens),
    )
    # Progressive fallback: avoid empty UX while preserving relevance.
    if not ranked and mode == "editorial" and strict_tokens:
        ranked = _build_ranked(min_overlap=1, require_title_overlap=False, require_core_match=True)
    if not ranked and mode == "editorial":
        ranked = _build_ranked(min_overlap=1, require_title_overlap=False, require_core_match=False)

    # Canonical URL de-dup on final list.
    final: list[Article] = []
    seen_urls: set[str] = set()
    seen_ids: set[int] = set()
    for _, article in ranked:
        if article.id in seen_ids:
            continue
        url_key = _canonical_url(article.original_url)
        if url_key and url_key in seen_urls:
            continue
        seen_ids.add(article.id)
        if url_key:
            seen_urls.add(url_key)
        final.append(article)
        if len(final) >= limit:
            break

    return [ArticleBrief.model_validate(a) for a in final]


@router.get("/{article_id}", response_model=ArticleResponse)
async def get_article(article_id: int, db: AsyncSession = Depends(get_db)):
    """Get a single article by ID."""
    result = await db.execute(select(Article).where(Article.id == article_id))
    article = result.scalar_one_or_none()
    if not article:
        raise HTTPException(404, "Article not found")
    await bump_keyword_interactions(extract_keywords(article.title_ar or article.original_title), weight=1)
    return ArticleResponse.model_validate(article)


@router.get("/{article_id}/related")
async def related_articles(
    article_id: int,
    limit: int = Query(8, ge=1, le=30),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve related articles via summary vectors.
    """
    src_vec_result = await db.execute(
        select(ArticleVector)
        .where(
            and_(
                ArticleVector.article_id == article_id,
                ArticleVector.vector_type == "summary",
            )
        )
        .limit(1)
    )
    src_vec = src_vec_result.scalar_one_or_none()
    if not src_vec:
        return []

    stmt = (
        select(Article)
        .join(ArticleVector, ArticleVector.article_id == Article.id)
        .where(
            and_(
                Article.id != article_id,
                ArticleVector.vector_type == "summary",
                Article.status != NewsStatus.ARCHIVED,
            )
        )
        .order_by(ArticleVector.embedding.cosine_distance(src_vec.embedding))
        .limit(limit)
    )
    rows = await db.execute(stmt)
    return [ArticleBrief.model_validate(a) for a in rows.scalars().all()]


@router.get("/{article_id}/cluster")
async def article_cluster(
    article_id: int,
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """
    Return cluster members for the article (event card view).
    """
    cluster_sizes = (
        select(
            StoryClusterMember.cluster_id.label("cluster_id"),
            func.count(StoryClusterMember.article_id).label("members"),
        )
        .group_by(StoryClusterMember.cluster_id)
        .subquery()
    )
    member_row = await db.execute(
        select(StoryClusterMember)
        .join(cluster_sizes, cluster_sizes.c.cluster_id == StoryClusterMember.cluster_id)
        .where(StoryClusterMember.article_id == article_id)
        .order_by(desc(cluster_sizes.c.members), desc(StoryClusterMember.score), StoryClusterMember.id.asc())
        .limit(1)
    )
    member = member_row.scalar_one_or_none()
    if not member:
        return {"cluster": None, "members": []}

    cluster_row = await db.execute(select(StoryCluster).where(StoryCluster.id == member.cluster_id))
    cluster = cluster_row.scalar_one_or_none()
    if not cluster:
        return {"cluster": None, "members": []}

    rows = await db.execute(
        select(Article)
        .join(StoryClusterMember, StoryClusterMember.article_id == Article.id)
        .where(StoryClusterMember.cluster_id == cluster.id)
        .order_by(desc(StoryClusterMember.score), desc(Article.crawled_at))
        .limit(limit)
    )
    members = [ArticleBrief.model_validate(a) for a in rows.scalars().all()]
    return {
        "cluster": {
            "id": cluster.id,
            "cluster_key": cluster.cluster_key,
            "label": cluster.label,
            "category": cluster.category,
            "geography": cluster.geography,
        },
        "members": members,
    }


@router.get("/{article_id}/relations")
async def article_relations(
    article_id: int,
    relation_type: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """
    Return explicit relation edges (sequence/impact/contrast/duplicate/related).
    """
    stmt = (
        select(ArticleRelation, Article)
        .join(Article, Article.id == ArticleRelation.to_article_id)
        .where(ArticleRelation.from_article_id == article_id)
        .order_by(desc(ArticleRelation.score), desc(Article.created_at))
        .limit(limit)
    )
    if relation_type:
        stmt = stmt.where(ArticleRelation.relation_type == relation_type)

    rows = await db.execute(stmt)
    items = []
    for rel, target in rows.all():
        items.append(
            {
                "relation_type": rel.relation_type,
                "score": rel.score,
                "metadata": rel.metadata_json or {},
                "article": ArticleBrief.model_validate(target),
            }
        )
    return items
