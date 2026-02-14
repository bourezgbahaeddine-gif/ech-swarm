"""
Echorouk AI Swarm — News API Routes
=====================================
CRUD operations for articles with filtering & pagination.
"""

from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, desc, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models import Article, NewsStatus, NewsCategory
from app.schemas import ArticleResponse, ArticleBrief, PaginatedResponse

router = APIRouter(prefix="/news", tags=["News"])


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

    query = select(Article)
    count_query = select(func.count(Article.id))

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


@router.get("/{article_id}", response_model=ArticleResponse)
async def get_article(article_id: int, db: AsyncSession = Depends(get_db)):
    """Get a single article by ID."""
    result = await db.execute(select(Article).where(Article.id == article_id))
    article = result.scalar_one_or_none()
    if not article:
        raise HTTPException(404, "Article not found")
    return ArticleResponse.model_validate(article)


@router.get("/breaking/latest")
async def get_breaking_news(
    limit: int = Query(5, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
):
    """Get latest breaking news."""
    result = await db.execute(
        select(Article)
        .where(Article.is_breaking == True)
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
