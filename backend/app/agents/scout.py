"""
Echorouk AI Swarm — Scout Agent (الوكيل الكشّاف)
====================================================
Ingestion Layer: Fetches news from 300+ RSS sources,
normalizes data, and applies deduplication.

Single Responsibility: Fetch & Store RAW only.
"""

import time
import asyncio
import random
from datetime import datetime
from typing import Optional, Iterable
from urllib.parse import urljoin, urlparse

import feedparser
import aiohttp
from bs4 import BeautifulSoup
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import async_session
from app.core.logging import get_logger
from app.models import Article, Source, PipelineRun, FailedJob, NewsStatus
from app.utils.hashing import generate_unique_hash, generate_trace_id
from app.utils.text_processing import sanitize_input, truncate_text
from app.services.cache_service import cache_service

logger = get_logger("agent.scout")
settings = get_settings()


class ScoutAgent:
    """
    The Scout Agent — responsible for RSS ingestion.
    Fetches, normalizes, deduplicates, and stores RAW news.
    """

    async def run(self, db: AsyncSession) -> dict:
        """Execute a full scout run across all enabled sources."""
        run = PipelineRun(
            run_type="scout",
            started_at=datetime.utcnow(),
            status="running",
        )
        db.add(run)
        await db.commit()

        stats = {
            "total": 0,
            "new": 0,
            "duplicates": 0,
            "errors": 0,
        }
        max_new_per_run = settings.scout_max_new_per_run

        try:
            # Get enabled sources
            result = await db.execute(
                select(Source).where(Source.enabled == True).order_by(Source.priority.desc())
            )
            sources = result.scalars().all()

            if not sources:
                logger.warning("no_sources_enabled")
                run.status = "success"
                run.finished_at = datetime.utcnow()
                run.details = {"warning": "No enabled sources"}
                await db.commit()
                return stats

            logger.info("scout_run_started", sources_count=len(sources))

            # Shuffle sources to avoid starvation and keep feed balanced
            random.shuffle(sources)

            # Process sources in batches to avoid overwhelming the network
            batch_size = settings.scout_batch_size
            semaphore = asyncio.Semaphore(settings.scout_concurrency)
            async with aiohttp.ClientSession() as session:
                for i in range(0, len(sources), batch_size):
                    batch = sources[i:i + batch_size]
                    tasks = [
                        self._fetch_source(source.id, stats, session, semaphore)
                        for source in batch
                    ]
                    await asyncio.gather(*tasks, return_exceptions=True)

                    # Global cap to keep editorial feed smooth
                    if stats["new"] >= max_new_per_run:
                        logger.info("scout_run_cap_reached", max_new=max_new_per_run)
                        break

                    # Small delay between batches (backpressure)
                    if i + batch_size < len(sources):
                        await asyncio.sleep(0.5)

            # Update run record
            run.status = "success"
            run.finished_at = datetime.utcnow()
            run.total_items = stats["total"]
            run.new_items = stats["new"]
            run.duplicates = stats["duplicates"]
            run.errors = stats["errors"]
            await db.commit()

            logger.info("scout_run_complete", **stats)

        except Exception as e:
            run.status = "failed"
            run.finished_at = datetime.utcnow()
            run.details = {"error": str(e)}
            await db.commit()
            logger.error("scout_run_failed", error=str(e))

        return stats

    async def _fetch_source(
        self,
        source_id: int,
        stats: dict,
        session: aiohttp.ClientSession,
        semaphore: asyncio.Semaphore,
    ):
        """Fetch and process a single source (RSS or scraper)."""
        async with async_session() as db:
            source = await db.get(Source, source_id)
            if not source:
                return
            try:
                async with semaphore:
                    entries = []
                    if (source.method or "rss") == "rss":
                        feed_url = source.rss_url or source.url
                        feed = await self._parse_feed(feed_url, session=session)
                        if feed and feed.entries:
                            entries = feed.entries
                    else:
                        entries = await self._scrape_source(source, session=session)

                    if not entries:
                        return

                # Limit per source to keep editorial feed balanced
                max_per_source = self._source_limit(source)
                for idx, entry in enumerate(entries):
                    if idx >= max_per_source:
                        break
                    stats["total"] += 1
                    try:
                        await self._process_entry(db, entry, source, stats)
                    except Exception as e:
                        stats["errors"] += 1
                        logger.warning("entry_process_error", source=source.name, error=str(e))

                # Update source metadata
                source.last_fetched_at = datetime.utcnow()
                source.error_count = 0
                await db.commit()

            except Exception as e:
                stats["errors"] += 1
                source.error_count = (source.error_count or 0) + 1
                logger.error("source_fetch_error", source=source.name, error=str(e))

                # Log to DLQ
                dlq = FailedJob(
                    job_type="scout_fetch",
                    payload={"source_id": source.id, "source_url": source.url},
                    error_message=str(e),
                )
                db.add(dlq)
                await db.commit()

    async def _parse_feed(
        self,
        url: str,
        session: aiohttp.ClientSession,
        timeout: int = None,
    ) -> Optional[feedparser.FeedParserDict]:
        """Parse an RSS feed with timeout and error handling."""
        timeout = timeout or settings.rss_fetch_timeout
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                if resp.status != 200:
                    logger.warning("feed_http_error", url=url, status=resp.status)
                    return None
                content = await resp.text()
                return feedparser.parse(content)
        except asyncio.TimeoutError:
            logger.warning("feed_timeout", url=url)
            return None
        except Exception as e:
            logger.error("feed_parse_error", url=url, error=str(e))
            return None

    async def _scrape_source(
        self,
        source: Source,
        session: aiohttp.ClientSession,
        timeout: int = None,
    ) -> list[dict]:
        """Lightweight scraper: extract recent links and titles from homepage."""
        timeout = timeout or settings.rss_fetch_timeout
        url = source.url
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                if resp.status != 200:
                    logger.warning("scrape_http_error", url=url, status=resp.status)
                    return []
                html = await resp.text()
        except asyncio.TimeoutError:
            logger.warning("scrape_timeout", url=url)
            return []
        except Exception as e:
            logger.error("scrape_error", url=url, error=str(e))
            return []

        soup = BeautifulSoup(html, "html.parser")
        anchors = soup.find_all("a", href=True)

        base = urlparse(url)
        seen = set()
        items: list[dict] = []
        for a in anchors:
            title = (a.get_text() or "").strip()
            href = a.get("href")
            if not title or len(title) < 8:
                continue

            link = urljoin(url, href)
            parsed = urlparse(link)
            if parsed.scheme not in {"http", "https"}:
                continue
            if parsed.netloc and parsed.netloc != base.netloc:
                continue
            if link in seen:
                continue

            # Skip non-article links by heuristic
            if any(x in link for x in ["/tag/", "/tags/", "/category/", "/author/", "/video/", "#"]):
                continue

            seen.add(link)
            items.append({"title": title, "link": link})

            if len(items) >= 30:
                break

        return items

    def _source_limit(self, source: Source) -> int:
        """Compute per-source cap based on priority and credibility."""
        priority = source.priority or 5  # 1..10
        credibility = (source.credibility or "medium").lower()
        source_type = (source.source_type or "").lower()

        cred_weight = {
            "official": 1.3,
            "high": 1.15,
            "medium": 1.0,
            "low": 0.8,
        }.get(credibility, 1.0)

        type_weight = {
            "official": 1.2,
            "agency": 1.1,
            "media": 1.0,
            "aggregator": 0.9,
            "business": 1.0,
            "tech": 1.0,
        }.get(source_type, 1.0)

        # Base cap with gentle scaling; keep within a reasonable range
        base = 6 + int((priority - 5) * 0.8)
        cap = int(base * cred_weight * type_weight)

        # Freshness boost: sources not fetched recently get a small bump
        if source.last_fetched_at is None:
            cap += 3
        else:
            age_hours = (datetime.utcnow() - source.last_fetched_at).total_seconds() / 3600.0
            if age_hours >= 24:
                cap += 3
            elif age_hours >= 6:
                cap += 2

        return max(4, min(18, cap))

    async def _process_entry(self, db: AsyncSession, entry, source: Source, stats: dict):
        """Process a single feed entry: normalize, dedup, store."""

        # Extract fields with fallbacks
        title = ""
        link = ""
        if isinstance(entry, dict):
            title = (entry.get("title") or "").strip()
            link = (entry.get("link") or "").strip()
        else:
            title = entry.get("title", "").strip()
            link = entry.get("link", "").strip()

        if not title or not link:
            return

        # ── Deduplication Gate ──

        # Step 1: Hash-based exact dedup
        unique_hash = generate_unique_hash(source.name, link, title)

        # Check Redis cache first (fast path)
        if await cache_service.is_url_processed(unique_hash):
            stats["duplicates"] += 1
            return

        # Check database (slow path)
        existing = await db.execute(
            select(Article.id).where(Article.unique_hash == unique_hash)
        )
        if existing.scalar_one_or_none():
            stats["duplicates"] += 1
            await cache_service.mark_url_processed(unique_hash)
            return

        # Step 2: Fuzzy title dedup (Levenshtein)
        from app.utils.hashing import is_duplicate_title
        recent_titles = await cache_service.get_recent_titles(50)
        if is_duplicate_title(title, recent_titles, settings.dedup_similarity_threshold):
            stats["duplicates"] += 1
            return

        # ── Normalize & Store ──

        # Parse publication date
        published_at = None
        if not isinstance(entry, dict):
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                try:
                    published_at = datetime(*entry.published_parsed[:6])
                except (ValueError, TypeError):
                    pass

        # Get content
        content = ""
        if isinstance(entry, dict):
            content = entry.get("summary") or ""
        else:
            if hasattr(entry, "summary"):
                content = entry.summary
            elif hasattr(entry, "content") and entry.content:
                content = entry.content[0].get("value", "")

        # Sanitize all inputs (Zero Trust)
        title = sanitize_input(title)
        content = sanitize_input(content)
        trace_id = generate_trace_id()

        # Create article
        article = Article(
            unique_hash=unique_hash,
            original_title=title,
            original_url=link,
            original_content=truncate_text(content, 10000),
            published_at=published_at,
            crawled_at=datetime.utcnow(),
            created_at=datetime.utcnow(),
            source_id=source.id,
            source_name=source.name,
            status=NewsStatus.NEW,
            trace_id=trace_id,
        )

        try:
            db.add(article)
            await db.flush()
            
            # Update caches
            await cache_service.mark_url_processed(unique_hash, article.id)
            await cache_service.add_recent_title(title)
            
            stats["new"] += 1
            logger.info(
                "article_ingested",
                trace_id=trace_id,
                source=source.name,
                title=title[:80],
            )
        except Exception as e:
            # Handle unique constraint violations gracefully
            if "IntegrityError" in type(e).__name__ or "UniqueViolationError" in str(e):
                await db.rollback()
                stats["duplicates"] += 1
                await cache_service.mark_url_processed(unique_hash)
                logger.info("duplicate_detected_on_insert", unique_hash=unique_hash)
            else:
                raise e

    async def fetch_single_source(self, db: AsyncSession, source_id: int) -> dict:
        """Fetch a single source on-demand."""
        result = await db.execute(select(Source).where(Source.id == source_id))
        source = result.scalar_one_or_none()
        if not source:
            return {"error": "Source not found"}

        stats = {"total": 0, "new": 0, "duplicates": 0, "errors": 0}
        await self._fetch_source(db, source, stats)
        await db.commit()
        return stats


# Singleton
scout_agent = ScoutAgent()
