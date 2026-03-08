from __future__ import annotations

import asyncio
import html
import json
import re
import ssl
from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import urljoin, urlparse, urlunparse

import aiohttp
import certifi
import trafilatura
from bs4 import BeautifulSoup
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models import (
    ArchiveCrawlState,
    ArchiveCrawlUrl,
    Article,
    ArticleProfile,
    ArticleVector,
    NewsCategory,
    NewsStatus,
    Source,
    UrgencyLevel,
)
from app.services.article_index_service import article_index_service
from app.services.embedding_service import embedding_service
from app.utils.hashing import generate_unique_hash
from app.utils.text_processing import sanitize_input, truncate_text

logger = get_logger("services.echorouk_archive")
settings = get_settings()

ARCHIVE_SOURCE_KEY = "echorouk_archive"
ARCHIVE_CORPUS = "echorouk_archive"
DEFAULT_HEADERS = {"User-Agent": "Mozilla/5.0 (EchoroukArchiveBot/1.0)"}
ARTICLE_TYPE_HINTS = {"article", "newsarticle", "reportage"}
SECTION_CATEGORY_MAP = {
    "algeria": NewsCategory.LOCAL_ALGERIA,
    "economy": NewsCategory.ECONOMY,
    "sport": NewsCategory.SPORTS,
    "world": NewsCategory.INTERNATIONAL,
    "opinion": NewsCategory.POLITICS,
    "culture": NewsCategory.CULTURE,
    "society": NewsCategory.SOCIETY,
    "health": NewsCategory.HEALTH,
    "technology": NewsCategory.TECHNOLOGY,
    "environment": NewsCategory.ENVIRONMENT,
}
NON_ARTICLE_PREFIXES = {
    "tag",
    "tags",
    "author",
    "category",
    "live",
    "francais",
    "english",
    "video",
    "videos",
    "podcast",
    "search",
    "echorouk-yawmi",
}
ASSET_SUFFIXES = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".pdf", ".mp4", ".mp3")


def _aiohttp_ssl_context() -> ssl.SSLContext:
    return ssl.create_default_context(cafile=certifi.where())


def _canonicalize_url(url: str) -> str:
    parsed = urlparse((url or "").strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    path = re.sub(r"/{2,}", "/", parsed.path or "/")
    if path != "/" and path.endswith("/"):
        path = path[:-1]
    normalized = parsed._replace(scheme="https", netloc=host, path=path, params="", query="", fragment="")
    return urlunparse(normalized)


def _path_segments(url: str) -> list[str]:
    path = urlparse(url).path.strip("/")
    return [segment for segment in path.split("/") if segment]


def _safe_text(value: str | None) -> str:
    return sanitize_input(value or "")


def _meta_content(soup: BeautifulSoup, *selectors: tuple[str, str]) -> str:
    for attr, key in selectors:
        node = soup.find("meta", attrs={attr: key})
        if node and node.get("content"):
            value = _safe_text(node.get("content"))
            if value:
                return value
    return ""


def _extract_json_ld(soup: BeautifulSoup) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = (script.string or script.get_text() or "").strip()
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, list):
            items.extend(x for x in payload if isinstance(x, dict))
        elif isinstance(payload, dict):
            graph = payload.get("@graph")
            if isinstance(graph, list):
                items.extend(x for x in graph if isinstance(x, dict))
            else:
                items.append(payload)
    return items


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    text_value = str(value).strip()
    if not text_value:
        return None
    normalized = text_value.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(normalized)
        return dt.replace(tzinfo=None) if dt.tzinfo else dt
    except ValueError:
        pass
    try:
        dt = parsedate_to_datetime(text_value)
        return dt.replace(tzinfo=None) if dt.tzinfo else dt
    except (TypeError, ValueError, IndexError):
        return None


def _paragraphs_to_html(text_value: str) -> str:
    paragraphs = [segment.strip() for segment in re.split(r"\n{2,}", text_value or "") if segment.strip()]
    return "\n".join(f"<p>{html.escape(segment)}</p>" for segment in paragraphs[:24])


def _extract_text_content(html_text: str, soup: BeautifulSoup) -> str:
    extracted = trafilatura.extract(
        html_text,
        include_comments=False,
        include_images=False,
        include_links=False,
        include_tables=False,
        output_format="txt",
    )
    if extracted:
        clean = _safe_text(extracted)
        if len(clean) >= 250:
            return clean

    main_node = soup.find("article") or soup.find("main") or soup.find("div", attrs={"role": "main"})
    if not main_node:
        return ""
    paragraphs = [
        _safe_text(p.get_text(" ", strip=True))
        for p in main_node.find_all(["p", "h2", "h3"])
    ]
    return "\n\n".join(segment for segment in paragraphs if len(segment) >= 20)


def _category_from_url(url: str) -> NewsCategory | None:
    segments = _path_segments(url)
    for segment in segments:
        if segment in SECTION_CATEGORY_MAP:
            return SECTION_CATEGORY_MAP[segment]
    return None


def _article_candidate(url: str) -> bool:
    canonical = _canonicalize_url(url)
    if not canonical:
        return False
    parsed = urlparse(canonical)
    if parsed.netloc != "echoroukonline.com":
        return False
    path = parsed.path or "/"
    if path == "/" or path.startswith("/wp-"):
        return False
    if path.endswith(ASSET_SUFFIXES):
        return False
    if "/page/" in path:
        return False
    segments = _path_segments(canonical)
    if not segments:
        return False
    if segments[0] in NON_ARTICLE_PREFIXES:
        return False
    if len(segments) == 1 and segments[0] in SECTION_CATEGORY_MAP:
        return False
    return True


def _listing_candidate(url: str) -> bool:
    canonical = _canonicalize_url(url)
    if not canonical:
        return False
    parsed = urlparse(canonical)
    if parsed.netloc != "echoroukonline.com":
        return False
    segments = _path_segments(canonical)
    if not segments:
        return True
    if len(segments) == 1 and segments[0] in SECTION_CATEGORY_MAP:
        return True
    if "page" in segments:
        return True
    return False


@dataclass
class ArticlePayload:
    canonical_url: str
    title: str
    summary: str
    content: str
    published_at: datetime | None
    author: str
    category: NewsCategory | None


class EchoroukArchiveService:
    def __init__(self) -> None:
        self._base_url = settings.echorouk_archive_base_url

    async def ensure_state(self, db: AsyncSession) -> ArchiveCrawlState:
        result = await db.execute(
            select(ArchiveCrawlState).where(ArchiveCrawlState.source_key == ARCHIVE_SOURCE_KEY)
        )
        state = result.scalar_one_or_none()
        if state:
            return state

        state = ArchiveCrawlState(
            source_key=ARCHIVE_SOURCE_KEY,
            source_name=settings.echorouk_archive_source_name,
            base_url=self._base_url,
            status="idle",
            stats_json=self._blank_stats(),
        )
        db.add(state)
        await db.flush()
        await self._seed_frontier(db, state)
        return state

    async def archive_status(self, db: AsyncSession) -> dict[str, Any]:
        state = await self.ensure_state(db)
        queue_rows = await db.execute(
            select(ArchiveCrawlUrl.url_type, ArchiveCrawlUrl.status, func.count(ArchiveCrawlUrl.id))
            .where(ArchiveCrawlUrl.state_id == state.id)
            .group_by(ArchiveCrawlUrl.url_type, ArchiveCrawlUrl.status)
        )
        counts: dict[str, dict[str, int]] = {}
        for url_type, status, count in queue_rows.all():
            counts.setdefault(str(url_type), {})[str(status)] = int(count or 0)

        recent_failures = await db.execute(
            select(ArchiveCrawlUrl)
            .where(
                ArchiveCrawlUrl.state_id == state.id,
                ArchiveCrawlUrl.status.in_(["failed", "skipped"]),
            )
            .order_by(ArchiveCrawlUrl.updated_at.desc())
            .limit(10)
        )

        return {
            "source_key": state.source_key,
            "status": state.status,
            "seeded_at": state.seeded_at,
            "last_run_started_at": state.last_run_started_at,
            "last_run_finished_at": state.last_run_finished_at,
            "last_error": state.last_error,
            "stats": state.stats_json or {},
            "queue": counts,
            "recent_failures": [
                {
                    "url": row.url,
                    "url_type": row.url_type,
                    "status": row.status,
                    "attempts": row.attempts,
                    "last_http_status": row.last_http_status,
                    "last_error": row.last_error,
                    "updated_at": row.updated_at,
                }
                for row in recent_failures.scalars().all()
            ],
        }

    async def prepare_refresh(self, db: AsyncSession) -> int:
        state = await self.ensure_state(db)
        refreshed = 0
        now = datetime.utcnow()

        for url in settings.echorouk_archive_sections_list:
            canonical = _canonicalize_url(url)
            if not canonical:
                continue

            result = await db.execute(
                select(ArchiveCrawlUrl).where(
                    ArchiveCrawlUrl.state_id == state.id,
                    ArchiveCrawlUrl.url == canonical,
                )
            )
            row = result.scalar_one_or_none()
            if row is None:
                refreshed += await self._enqueue_url(
                    db,
                    state,
                    url=canonical,
                    url_type="listing",
                    depth=0,
                    discovered_from_url=None,
                    priority=5,
                )
                continue

            if row.status == "processing":
                continue

            row.status = "discovered"
            row.priority = 5
            row.depth = 0
            row.last_error = None
            row.updated_at = now
            refreshed += 1

        if refreshed:
            await db.commit()
        return refreshed

    async def semantic_search(self, db: AsyncSession, q: str, limit: int = 5) -> list[dict[str, Any]]:
        query = (q or "").strip()
        if len(query) < 2:
            return []

        query_vec, _ = await embedding_service.embed_query(query)
        stmt = (
            select(
                Article,
                ArticleVector.embedding.cosine_distance(query_vec).label("dist"),
            )
            .join(ArticleVector, ArticleVector.article_id == Article.id)
            .join(ArticleProfile, ArticleProfile.article_id == Article.id)
            .where(
                ArticleVector.vector_type.in_(["title", "summary"]),
                text("article_profiles.metadata_json ->> 'corpus' = 'echorouk_archive'"),
            )
            .order_by(ArticleVector.embedding.cosine_distance(query_vec))
            .limit(max(limit * 4, 20))
        )
        rows = await db.execute(stmt)

        best_by_article: dict[int, tuple[Article, float]] = {}
        for article, dist in rows.all():
            previous = best_by_article.get(article.id)
            distance = float(dist)
            if previous is None or distance < previous[1]:
                best_by_article[article.id] = (article, distance)

        ranked = sorted(best_by_article.values(), key=lambda item: item[1])[:limit]
        return [
            {
                "id": article.id,
                "title": article.title_ar or article.original_title,
                "summary": article.summary or "",
                "url": article.original_url,
                "source_name": article.source_name,
                "published_at": article.published_at.isoformat() if article.published_at else None,
                "score": round(max(0.0, 1.0 - min(distance, 2.0) / 2.0), 4),
                "corpus": ARCHIVE_CORPUS,
            }
            for article, distance in ranked
        ]

    async def run_batch(
        self,
        db: AsyncSession,
        *,
        listing_pages: int | None = None,
        article_pages: int | None = None,
    ) -> dict[str, Any]:
        state = await self.ensure_state(db)
        source = await self._ensure_source(db)
        listing_limit = max(1, int(listing_pages or settings.echorouk_archive_max_listing_pages_per_run))
        article_limit = max(1, int(article_pages or settings.echorouk_archive_max_articles_per_run))

        state.status = "running"
        state.last_run_started_at = datetime.utcnow()
        state.last_error = None
        await db.commit()

        stats = {
            "listing_pages_requested": listing_limit,
            "article_pages_requested": article_limit,
            "listing_pages_processed": 0,
            "article_pages_processed": 0,
            "article_pages_indexed": 0,
            "article_pages_failed": 0,
            "article_pages_skipped": 0,
            "urls_discovered": 0,
        }

        connector = aiohttp.TCPConnector(ssl=_aiohttp_ssl_context())
        timeout = aiohttp.ClientTimeout(total=settings.echorouk_archive_request_timeout_seconds)

        try:
            async with aiohttp.ClientSession(connector=connector, timeout=timeout, headers=DEFAULT_HEADERS) as session:
                listing_rows = await self._claim_urls(db, state, url_type="listing", limit=listing_limit)
                for row in listing_rows:
                    page_stats = await self._process_listing_url(db, state, row, session)
                    stats["listing_pages_processed"] += 1
                    stats["urls_discovered"] += page_stats["urls_discovered"]
                    await self._sleep_between_requests()

                article_rows = await self._claim_urls(db, state, url_type="article", limit=article_limit)
                for row in article_rows:
                    result = await self._process_article_url(db, source, row, session)
                    stats["article_pages_processed"] += 1
                    stats["article_pages_indexed"] += int(result == "indexed")
                    stats["article_pages_failed"] += int(result == "failed")
                    stats["article_pages_skipped"] += int(result == "skipped")
                    await self._sleep_between_requests()

            state.status = "idle"
            state.last_run_finished_at = datetime.utcnow()
            state.stats_json = self._merge_stats(state.stats_json or {}, stats)
            await db.commit()
            return {"ok": True, **stats, "state_id": state.id}
        except Exception as exc:  # noqa: BLE001
            state.status = "failed"
            state.last_error = str(exc)
            state.last_run_finished_at = datetime.utcnow()
            state.stats_json = self._merge_stats(state.stats_json or {}, stats)
            await db.commit()
            logger.error("echorouk_archive_batch_failed", error=str(exc))
            raise

    async def _process_listing_url(
        self,
        db: AsyncSession,
        state: ArchiveCrawlState,
        row: ArchiveCrawlUrl,
        session: aiohttp.ClientSession,
    ) -> dict[str, int]:
        html_text, http_status = await self._fetch_html(session, row.url)
        row.last_http_status = http_status
        if not html_text:
            row.status = "failed"
            row.last_error = f"http_error:{http_status}"
            row.updated_at = datetime.utcnow()
            await db.commit()
            return {"urls_discovered": 0}

        discovered = 0
        article_urls, next_listing_urls = self._parse_listing_page(row.url, html_text)
        for url in article_urls:
            discovered += await self._enqueue_url(
                db,
                state,
                url=url,
                url_type="article",
                depth=row.depth + 1,
                discovered_from_url=row.url,
                priority=20,
            )
        for url in next_listing_urls:
            if row.depth + 1 > settings.echorouk_archive_max_listing_depth:
                break
            discovered += await self._enqueue_url(
                db,
                state,
                url=url,
                url_type="listing",
                depth=row.depth + 1,
                discovered_from_url=row.url,
                priority=10,
            )

        row.status = "fetched"
        row.fetched_at = datetime.utcnow()
        row.last_error = None
        row.updated_at = datetime.utcnow()
        await db.commit()
        return {"urls_discovered": discovered}

    async def _process_article_url(
        self,
        db: AsyncSession,
        source: Source,
        row: ArchiveCrawlUrl,
        session: aiohttp.ClientSession,
    ) -> str:
        html_text, http_status = await self._fetch_html(session, row.url)
        row.last_http_status = http_status
        if not html_text:
            row.status = "failed"
            row.last_error = f"http_error:{http_status}"
            row.updated_at = datetime.utcnow()
            await db.commit()
            return "failed"

        payload = self._parse_article_page(row.url, html_text)
        if payload is None:
            row.status = "skipped"
            row.last_error = "not_article_or_content_too_short"
            row.updated_at = datetime.utcnow()
            await db.commit()
            return "skipped"

        article = await self._upsert_article(db, source, payload)
        row.status = "indexed"
        row.canonical_url = payload.canonical_url
        row.article_id = article.id
        row.fetched_at = datetime.utcnow()
        row.indexed_at = datetime.utcnow()
        row.last_error = None
        row.updated_at = datetime.utcnow()
        await db.commit()
        logger.info("echorouk_archive_article_indexed", article_id=article.id, url=payload.canonical_url)
        return "indexed"

    async def _upsert_article(self, db: AsyncSession, source: Source, payload: ArticlePayload) -> Article:
        canonical_url = payload.canonical_url
        existing = await db.execute(
            select(Article).where(Article.original_url == canonical_url).limit(1)
        )
        article = existing.scalar_one_or_none()
        if article is None:
            article = Article(
                unique_hash=generate_unique_hash(source.name, canonical_url, payload.title),
                original_title=payload.title,
                original_url=canonical_url,
                source_id=source.id,
                source_name=source.name,
                crawled_at=datetime.utcnow(),
                status=NewsStatus.ARCHIVED,
                urgency=UrgencyLevel.LOW,
                is_breaking=False,
                importance_score=2,
            )
            db.add(article)

        article.original_title = payload.title
        article.original_url = canonical_url
        article.original_content = payload.content
        article.published_at = payload.published_at or article.published_at
        article.source_id = source.id
        article.source_name = source.name
        article.title_ar = payload.title
        article.summary = truncate_text(payload.summary or payload.content, 420)
        article.body_html = _paragraphs_to_html(payload.content)
        article.category = payload.category or article.category
        article.updated_at = datetime.utcnow()
        if article.status in {None, NewsStatus.ARCHIVED}:
            article.status = NewsStatus.ARCHIVED

        await db.flush()
        await article_index_service.upsert_article(
            db,
            article,
            profile_metadata={
                "corpus": ARCHIVE_CORPUS,
                "origin_site": "echoroukonline.com",
                "ingest_type": "archive_backfill",
                "archive_author": payload.author,
            },
        )
        return article

    async def _ensure_source(self, db: AsyncSession) -> Source:
        result = await db.execute(
            select(Source).where(Source.url == settings.echorouk_archive_base_url).limit(1)
        )
        source = result.scalar_one_or_none()
        if source:
            return source

        source = Source(
            name=settings.echorouk_archive_source_name,
            method="scraper",
            url=settings.echorouk_archive_base_url,
            language="ar",
            category="general",
            credibility="high",
            priority=7,
            enabled=True,
            fetch_interval_minutes=60,
        )
        db.add(source)
        await db.commit()
        await db.refresh(source)
        return source

    async def _seed_frontier(self, db: AsyncSession, state: ArchiveCrawlState) -> None:
        seeded = 0
        for url in settings.echorouk_archive_sections_list:
            seeded += await self._enqueue_url(
                db,
                state,
                url=url,
                url_type="listing",
                depth=0,
                discovered_from_url=None,
                priority=10,
            )
        if seeded and state.seeded_at is None:
            state.seeded_at = datetime.utcnow()
            state.stats_json = self._merge_stats(state.stats_json or {}, {"seeded_listing_urls": seeded})
        await db.commit()

    async def _claim_urls(
        self,
        db: AsyncSession,
        state: ArchiveCrawlState,
        *,
        url_type: str,
        limit: int,
    ) -> list[ArchiveCrawlUrl]:
        rows = await db.execute(
            select(ArchiveCrawlUrl)
            .where(
                ArchiveCrawlUrl.state_id == state.id,
                ArchiveCrawlUrl.url_type == url_type,
                ArchiveCrawlUrl.status == "discovered",
            )
            .order_by(ArchiveCrawlUrl.priority.asc(), ArchiveCrawlUrl.depth.asc(), ArchiveCrawlUrl.id.asc())
            .limit(limit)
        )
        items = rows.scalars().all()
        now = datetime.utcnow()
        for item in items:
            item.status = "processing"
            item.attempts = int(item.attempts or 0) + 1
            item.updated_at = now
        await db.commit()
        return items

    async def _enqueue_url(
        self,
        db: AsyncSession,
        state: ArchiveCrawlState,
        *,
        url: str,
        url_type: str,
        depth: int,
        discovered_from_url: str | None,
        priority: int,
    ) -> int:
        canonical = _canonicalize_url(url)
        if not canonical:
            return 0

        result = await db.execute(
            select(ArchiveCrawlUrl.id).where(
                ArchiveCrawlUrl.state_id == state.id,
                ArchiveCrawlUrl.url == canonical,
            )
        )
        if result.scalar_one_or_none():
            return 0

        db.add(
            ArchiveCrawlUrl(
                state_id=state.id,
                url=canonical,
                url_type=url_type,
                depth=max(0, depth),
                discovered_from_url=discovered_from_url,
                priority=priority,
                status="discovered",
            )
        )
        await db.flush()
        return 1

    async def _fetch_html(self, session: aiohttp.ClientSession, url: str) -> tuple[str, int]:
        try:
            async with session.get(url, allow_redirects=True) as response:
                text_value = await response.text()
                return text_value, int(response.status)
        except asyncio.TimeoutError:
            logger.warning("echorouk_archive_timeout", url=url)
            return "", 0
        except Exception as exc:  # noqa: BLE001
            logger.warning("echorouk_archive_fetch_failed", url=url, error=str(exc))
            return "", 0

    def _parse_listing_page(self, base_url: str, html_text: str) -> tuple[list[str], list[str]]:
        soup = BeautifulSoup(html_text or "", "html.parser")
        article_urls: list[str] = []
        next_listing_urls: list[str] = []
        seen_articles: set[str] = set()
        seen_listings: set[str] = set()

        for link in soup.find_all("link", attrs={"rel": True, "href": True}):
            rel_values = {str(value).lower() for value in (link.get("rel") or [])}
            href = _canonicalize_url(urljoin(base_url, link.get("href")))
            if "next" in rel_values and href and href not in seen_listings and _listing_candidate(href):
                seen_listings.add(href)
                next_listing_urls.append(href)

        for anchor in soup.find_all("a", href=True):
            href = _canonicalize_url(urljoin(base_url, anchor.get("href")))
            if not href:
                continue
            if _article_candidate(href):
                if href not in seen_articles:
                    seen_articles.add(href)
                    article_urls.append(href)
                continue
            if _listing_candidate(href) and href != _canonicalize_url(base_url):
                if href not in seen_listings:
                    seen_listings.add(href)
                    next_listing_urls.append(href)

        return article_urls, next_listing_urls

    def _parse_article_page(self, base_url: str, html_text: str) -> ArticlePayload | None:
        soup = BeautifulSoup(html_text or "", "html.parser")
        json_ld_items = _extract_json_ld(soup)

        canonical_node = soup.find("link", attrs={"rel": "canonical"})
        canonical_url = _canonicalize_url(canonical_node.get("href") if canonical_node else base_url) or _canonicalize_url(base_url)
        if not _article_candidate(canonical_url):
            return None

        og_type = _meta_content(soup, ("property", "og:type"))
        schema_types = {
            str(item.get("@type", "")).lower()
            for item in json_ld_items
            if item.get("@type")
        }
        is_article = og_type.lower() in ARTICLE_TYPE_HINTS or bool(schema_types & ARTICLE_TYPE_HINTS)

        h1 = soup.find("h1")
        title = (
            _meta_content(soup, ("property", "og:title"), ("name", "twitter:title"))
            or _safe_text(h1.get_text(" ", strip=True) if h1 else "")
        )
        if title.endswith(" - الشروق أونلاين"):
            title = title[: -len(" - الشروق أونلاين")].strip()

        summary = _meta_content(
            soup,
            ("name", "description"),
            ("property", "og:description"),
            ("name", "twitter:description"),
        )

        published_at = _parse_datetime(
            _meta_content(soup, ("property", "article:published_time"), ("name", "article:published_time"))
        )
        if published_at is None:
            for item in json_ld_items:
                published_at = _parse_datetime(item.get("datePublished"))
                if published_at:
                    break
        if published_at is None:
            time_node = soup.find("time")
            if time_node:
                published_at = _parse_datetime(time_node.get("datetime") or time_node.get_text(" ", strip=True))

        author = _meta_content(soup, ("name", "author"))
        if not author:
            for item in json_ld_items:
                author_data = item.get("author")
                if isinstance(author_data, dict):
                    author = _safe_text(author_data.get("name"))
                elif isinstance(author_data, list):
                    for person in author_data:
                        if isinstance(person, dict) and person.get("name"):
                            author = _safe_text(person.get("name"))
                            break
                if author:
                    break

        content = _extract_text_content(html_text, soup)
        if not summary:
            summary = truncate_text(content, 300)

        category = _category_from_url(canonical_url)
        if category is None:
            for item in json_ld_items:
                category = _category_from_url(str(item.get("articleSection") or ""))
                if category:
                    break

        if not title or len(content) < 250:
            return None
        if not is_article and len(content) < 400:
            return None

        return ArticlePayload(
            canonical_url=canonical_url,
            title=title,
            summary=summary,
            content=content,
            published_at=published_at,
            author=author,
            category=category,
        )

    @staticmethod
    def _blank_stats() -> dict[str, int]:
        return {
            "seeded_listing_urls": 0,
            "listing_pages_processed": 0,
            "article_pages_processed": 0,
            "article_pages_indexed": 0,
            "article_pages_failed": 0,
            "article_pages_skipped": 0,
            "urls_discovered": 0,
        }

    @staticmethod
    def _merge_stats(existing: dict[str, Any], delta: dict[str, Any]) -> dict[str, Any]:
        merged = dict(existing or {})
        for key, value in delta.items():
            if isinstance(value, int):
                merged[key] = int(merged.get(key, 0)) + value
            else:
                merged[key] = value
        return merged

    async def _sleep_between_requests(self) -> None:
        delay_ms = max(0, int(settings.echorouk_archive_delay_ms))
        if delay_ms:
            await asyncio.sleep(delay_ms / 1000.0)


echorouk_archive_service = EchoroukArchiveService()
