"""
Echorouk Editorial OS -- Sources API Routes
======================================
CRUD operations for RSS/news sources.
"""

from typing import Optional
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models import Source
from app.schemas import SourceCreate, SourceResponse, SourceUpdate
from app.services.cache_service import cache_service

router = APIRouter(prefix="/sources", tags=["Sources"])


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
