"""
Echorouk AI Swarm — News API Routes
=====================================
CRUD operations for articles with filtering & pagination.
"""

from datetime import datetime, timedelta
import hashlib
import math
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, desc, and_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.models import Article, ArticleVector, NewsStatus, NewsCategory, UrgencyLevel
from app.schemas import ArticleResponse, ArticleBrief, PaginatedResponse

router = APIRouter(prefix="/news", tags=["News"])
settings = get_settings()


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


@router.get("/", response_model=PaginatedResponse)
async def list_articles(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    category: Optional[str] = None,
    is_breaking: Optional[bool] = None,
    search: Optional[str] = None,
    sort_by: str = Query("created_at", regex="^(created_at|crawled_at|importance_score|published_at)$"),
    db: AsyncSession = Depends(get_db),
):
    """List articles with filtering and pagination."""
    if is_breaking:
        await _expire_stale_breaking_flags(db)

    query = select(Article)
    count_query = select(func.count(Article.id))
    breaking_cutoff = datetime.utcnow() - timedelta(minutes=settings.breaking_news_ttl_minutes)
    actionable_breaking_statuses = [NewsStatus.NEW, NewsStatus.CLASSIFIED, NewsStatus.CANDIDATE]

    # Apply filters
    filters = []
    if status:
        try:
            filters.append(Article.status == NewsStatus(status))
        except ValueError:
            raise HTTPException(400, f"Invalid status: {status}")
    else:
        # Keep newsroom list focused by hiding auto-archived noise by default.
        filters.append(Article.status != NewsStatus.ARCHIVED)
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
                Article.crawled_at >= cutoff,
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


@router.get("/search/semantic")
async def semantic_search(
    q: str = Query(..., min_length=2),
    limit: int = Query(10, ge=1, le=50),
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Semantic retrieval on vectorized title/summary records.
    """
    query_vec = _query_embedding(q, 256)
    stmt = (
        select(Article)
        .join(ArticleVector, ArticleVector.article_id == Article.id)
        .where(ArticleVector.vector_type.in_(["title", "summary"]))
        .order_by(ArticleVector.embedding.cosine_distance(query_vec))
        .limit(limit)
    )
    if status:
        try:
            stmt = stmt.where(Article.status == NewsStatus(status))
        except ValueError:
            raise HTTPException(400, f"Invalid status: {status}")
    else:
        stmt = stmt.where(Article.status != NewsStatus.ARCHIVED)

    rows = await db.execute(stmt)
    items = rows.scalars().all()

    seen = set()
    unique_items = []
    for item in items:
        if item.id in seen:
            continue
        seen.add(item.id)
        unique_items.append(item)
    return [ArticleBrief.model_validate(a) for a in unique_items]


@router.get("/{article_id}", response_model=ArticleResponse)
async def get_article(article_id: int, db: AsyncSession = Depends(get_db)):
    """Get a single article by ID."""
    result = await db.execute(select(Article).where(Article.id == article_id))
    article = result.scalar_one_or_none()
    if not article:
        raise HTTPException(404, "Article not found")
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
