"""
Echorouk AI Swarm — RSS Bridge Routes
=====================================
Expose RSS feeds for stored articles by source.
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models import Source, Article, NewsStatus, NewsCategory
from app.utils.text_processing import sanitize_input, truncate_text

router = APIRouter(prefix="/rss", tags=["RSS Bridge"])


def _rfc2822(dt: Optional[datetime]) -> str:
    if not dt:
        return datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S GMT")
    return dt.strftime("%a, %d %b %Y %H:%M:%S GMT")


def _xml_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


@router.get("/sources", summary="List RSS bridge URLs for all sources")
async def list_rss_sources(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Source).order_by(Source.priority.desc()))
    sources = result.scalars().all()
    return [
        {
            "source_id": s.id,
            "name": s.name,
            "slug": s.slug,
            "rss_bridge": f"/api/v1/rss/source/{s.id}",
        }
        for s in sources
    ]


@router.get("/source/{source_id}", summary="Get RSS feed for a single source")
@router.get("/source/{source_id}.xml", summary="Get RSS feed for a single source (xml)")
async def rss_for_source(
    source_id: int,
    limit: int = 50,
    status: Optional[str] = None,
    category: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    src_res = await db.execute(select(Source).where(Source.id == source_id))
    source = src_res.scalar_one_or_none()
    if not source:
        raise HTTPException(404, "Source not found")

    query = select(Article).where(Article.source_id == source_id)
    if status:
        try:
            query = query.where(Article.status == NewsStatus(status))
        except ValueError:
            raise HTTPException(400, f"Invalid status: {status}")
    if category:
        try:
            query = query.where(Article.category == NewsCategory(category))
        except ValueError:
            raise HTTPException(400, f"Invalid category: {category}")

    art_res = await db.execute(
        query.order_by(desc(Article.created_at)).limit(limit)
    )
    articles = art_res.scalars().all()

    channel_title = _xml_escape(source.name)
    channel_link = _xml_escape(source.url or "")
    channel_desc = _xml_escape(source.description or f"RSS bridge for {source.name}")

    items = []
    for a in articles:
        title = a.title_ar or a.original_title
        link = a.original_url
        if not title or not link:
            continue
        description = a.summary or a.original_content or ""
        description = truncate_text(sanitize_input(description), 800)
        items.append(
            f"""
    <item>
      <title>{_xml_escape(title)}</title>
      <link>{_xml_escape(link)}</link>
      <guid>{_xml_escape(a.unique_hash)}</guid>
      <pubDate>{_rfc2822(a.published_at or a.crawled_at or a.created_at)}</pubDate>
      <description>{_xml_escape(description)}</description>
    </item>"""
        )

    rss = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>{channel_title}</title>
    <link>{channel_link}</link>
    <description>{channel_desc}</description>
    <lastBuildDate>{_rfc2822(datetime.utcnow())}</lastBuildDate>
    {''.join(items)}
  </channel>
</rss>"""

    return Response(content=rss, media_type="application/rss+xml; charset=utf-8")


@router.get("/source/by-name/{source_name}", summary="Get RSS feed by source name")
@router.get("/source/by-name/{source_name}.xml", summary="Get RSS feed by source name (xml)")
async def rss_for_source_name(
    source_name: str,
    limit: int = 50,
    status: Optional[str] = None,
    category: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    src_res = await db.execute(
        select(Source).where(Source.name == source_name)
    )
    source = src_res.scalar_one_or_none()
    if not source:
        raise HTTPException(404, "Source not found")

    return await rss_for_source(source.id, limit=limit, status=status, category=category, db=db)


@router.get("/source/by-slug/{source_slug}", summary="Get RSS feed by source slug")
@router.get("/source/by-slug/{source_slug}.xml", summary="Get RSS feed by source slug (xml)")
async def rss_for_source_slug(
    source_slug: str,
    limit: int = 50,
    status: Optional[str] = None,
    category: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    src_res = await db.execute(
        select(Source).where(Source.slug == source_slug)
    )
    source = src_res.scalar_one_or_none()
    if not source:
        raise HTTPException(404, "Source not found")

    return await rss_for_source(source.id, limit=limit, status=status, category=category, db=db)
