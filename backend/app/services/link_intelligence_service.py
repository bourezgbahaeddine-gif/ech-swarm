"""
Link Intelligence service.
Internal + external link indexing, recommendation, validation, and HTML apply helpers.
"""

from __future__ import annotations

import math
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from email.utils import parsedate_to_datetime
from html import unescape
from typing import Any
from urllib.parse import unquote, urlparse
from urllib.request import Request, urlopen

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models import (
    Article,
    EditorialDraft,
    LinkIndexItem,
    LinkRecommendationItem,
    LinkRecommendationRun,
    TrustedDomain,
)
from app.models.user import User

logger = get_logger("link_intelligence.service")


LINK_MODES = {"internal", "external", "mixed"}
INTERNAL_DOMAINS = {"echoroukonline.com", "www.echoroukonline.com"}
ECHOROUK_FEED_URL = "https://www.echoroukonline.com/feed"
ECHOROUK_NEWS_SITEMAP_URL = "https://www.echoroukonline.com/news-sitemap.xml"

TRUSTED_EXTERNAL_MIN = 0.78
INTERNAL_SCORE_THRESHOLD = 0.16
EXTERNAL_SCORE_THRESHOLD = 0.34


@dataclass
class _ScoredItem:
    item: LinkIndexItem
    score: float
    confidence: float
    anchor_text: str
    reason: str
    placement_hint: str
    rel_attrs: str


class LinkIntelligenceService:
    def __init__(self) -> None:
        self._last_sync_at: datetime | None = None
        self._last_public_sync_at: datetime | None = None

    @staticmethod
    def _now() -> datetime:
        return datetime.utcnow()

    @staticmethod
    def _canonical_url(url: str) -> str:
        value = (url or "").strip()
        if not value:
            return ""
        parsed = urlparse(value)
        scheme = parsed.scheme or "https"
        netloc = (parsed.netloc or "").lower()
        path = parsed.path or "/"
        return f"{scheme}://{netloc}{path}".rstrip("/")

    @staticmethod
    def _extract_domain(url: str) -> str:
        try:
            return (urlparse(url).netloc or "").lower().strip()
        except Exception:
            return ""

    @staticmethod
    def _is_internal(url: str) -> bool:
        domain = LinkIntelligenceService._extract_domain(url)
        return domain in INTERNAL_DOMAINS or domain.endswith(".echoroukonline.com")

    @staticmethod
    def _tokens(text: str) -> set[str]:
        value = (text or "").lower()
        value = re.sub(r"[\u064b-\u065f\u0670]", "", value)
        value = value.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا").replace("ى", "ي").replace("ة", "ه")
        parts = re.split(r"[^a-z0-9\u0600-\u06ff]+", value)
        stop = {"على", "من", "في", "الى", "إلى", "عن", "مع", "هذا", "هذه", "ذلك", "the", "and", "for"}
        return {p for p in parts if len(p) >= 3 and p not in stop}

    @staticmethod
    def _safe_float(v: Any, default: float = 0.0) -> float:
        try:
            return float(v)
        except Exception:
            return default

    @staticmethod
    def _arabic_ratio(text: str) -> float:
        if not text:
            return 0.0
        letters = re.findall(r"[A-Za-z\u0600-\u06ff]", text)
        if not letters:
            return 0.0
        ar_letters = re.findall(r"[\u0600-\u06ff]", text)
        return len(ar_letters) / max(1, len(letters))

    @staticmethod
    def _fetch_text(url: str, timeout: int = 10) -> str:
        req = Request(url, headers={"User-Agent": "Mozilla/5.0 (LinkIntelligenceBot)"})
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
        return raw.decode("utf-8", "ignore")

    @staticmethod
    def _slug_to_title(url: str) -> str:
        path = urlparse(url).path.strip("/")
        if not path:
            return ""
        slug = unquote(path.split("/")[-1])
        slug = re.sub(r"[-_]+", " ", slug)
        slug = re.sub(r"\s+", " ", slug).strip()
        return slug[:200]

    async def _load_trusted_domains(self, db: AsyncSession) -> dict[str, TrustedDomain]:
        rows = await db.execute(select(TrustedDomain).where(TrustedDomain.enabled.is_(True)))
        items = rows.scalars().all()
        return {x.domain.lower(): x for x in items}

    async def sync_index_from_articles(self, db: AsyncSession, *, limit: int = 3000, force: bool = False) -> dict[str, int]:
        if not force and self._last_sync_at and (self._now() - self._last_sync_at) < timedelta(minutes=30):
            return {"upserted": 0, "skipped": 0}

        trusted = await self._load_trusted_domains(db)
        rows = await db.execute(
            select(Article)
            .where(Article.original_url.is_not(None))
            .order_by(desc(Article.updated_at))
            .limit(limit)
        )
        articles = rows.scalars().all()
        if not articles:
            self._last_sync_at = self._now()
            return {"upserted": 0, "skipped": 0}

        by_url: dict[str, LinkIndexItem] = {}
        existing_rows = await db.execute(select(LinkIndexItem))
        for item in existing_rows.scalars().all():
            by_url[item.url] = item

        upserted = 0
        skipped = 0
        now = self._now()
        for article in articles:
            url = self._canonical_url(article.original_url or "")
            if not url:
                skipped += 1
                continue
            domain = self._extract_domain(url)
            is_internal = self._is_internal(url)
            if not is_internal and domain not in trusted:
                skipped += 1
                continue

            title = (article.title_ar or article.original_title or "").strip()
            if len(title) < 5:
                skipped += 1
                continue

            trust = 0.85 if is_internal else (trusted.get(domain).trust_score if trusted.get(domain) else 0.6)
            category = article.category.value if getattr(article.category, "value", None) else (str(article.category) if article.category else None)
            keywords = article.keywords if isinstance(article.keywords, list) else []

            existing = by_url.get(url)
            if existing:
                existing.domain = domain
                existing.link_type = "internal" if is_internal else "external"
                existing.title = title
                existing.summary = (article.summary or "")[:2000]
                existing.category = category
                existing.keywords_json = keywords[:12]
                existing.published_at = article.published_at or article.crawled_at
                existing.authority_score = trust
                existing.source_article_id = article.id
                existing.is_active = True
                existing.last_seen_at = now
                upserted += 1
                continue

            item = LinkIndexItem(
                url=url,
                domain=domain,
                link_type="internal" if is_internal else "external",
                title=title[:1024],
                summary=(article.summary or "")[:2000],
                category=category,
                keywords_json=keywords[:12],
                published_at=article.published_at or article.crawled_at,
                authority_score=trust,
                source_article_id=article.id,
                is_active=True,
                first_seen_at=now,
                last_seen_at=now,
            )
            db.add(item)
            by_url[url] = item
            upserted += 1

        await db.commit()
        self._last_sync_at = now
        logger.info("link_index_sync_done", upserted=upserted, skipped=skipped, total=len(articles))
        return {"upserted": upserted, "skipped": skipped}

    async def sync_internal_from_public_sources(self, db: AsyncSession, *, force: bool = False) -> dict[str, int]:
        if not force and self._last_public_sync_at and (self._now() - self._last_public_sync_at) < timedelta(minutes=45):
            return {"upserted": 0, "feed": 0, "sitemap": 0}

        existing_rows = await db.execute(select(LinkIndexItem))
        by_url: dict[str, LinkIndexItem] = {item.url: item for item in existing_rows.scalars().all()}
        now = self._now()
        upserted = 0
        feed_count = 0
        sitemap_count = 0
        feed_ok = False
        sitemap_ok = False

        def _upsert(url: str, title: str, summary: str | None, published_at: datetime | None) -> None:
            nonlocal upserted
            canon = self._canonical_url(url)
            if not canon or not self._is_internal(canon):
                return
            clean_title = re.sub(r"\s+", " ", (title or "").strip())
            if len(clean_title) < 6:
                clean_title = self._slug_to_title(canon)
            if len(clean_title) < 6:
                return

            existing = by_url.get(canon)
            if existing:
                existing.link_type = "internal"
                existing.domain = self._extract_domain(canon)
                existing.title = clean_title[:1024]
                if summary:
                    existing.summary = summary[:2000]
                if published_at:
                    existing.published_at = published_at
                existing.authority_score = max(0.9, self._safe_float(existing.authority_score, 0.9))
                existing.is_active = True
                existing.last_seen_at = now
                upserted += 1
                return

            item = LinkIndexItem(
                url=canon,
                domain=self._extract_domain(canon),
                link_type="internal",
                title=clean_title[:1024],
                summary=(summary or "")[:2000],
                category=None,
                keywords_json=[],
                published_at=published_at,
                authority_score=0.92,
                source_article_id=None,
                is_active=True,
                first_seen_at=now,
                last_seen_at=now,
            )
            db.add(item)
            by_url[canon] = item
            upserted += 1

        try:
            feed_xml = self._fetch_text(ECHOROUK_FEED_URL, timeout=12)
            root = ET.fromstring(feed_xml)
            channel = root.find("channel")
            if channel is not None:
                for node in channel.findall("item")[:180]:
                    link = (node.findtext("link") or "").strip()
                    title = (node.findtext("title") or "").strip()
                    desc = (node.findtext("description") or "").strip()
                    summary = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", unescape(desc))).strip()
                    pub_dt = None
                    pub_raw = (node.findtext("pubDate") or "").strip()
                    if pub_raw:
                        try:
                            pub_dt = parsedate_to_datetime(pub_raw).replace(tzinfo=None)
                        except Exception:
                            pub_dt = None
                    _upsert(link, title, summary, pub_dt)
                    feed_count += 1
                feed_ok = True
        except Exception as exc:
            logger.warning("link_index_feed_sync_failed", error=str(exc))

        try:
            news_sitemap_xml = self._fetch_text(ECHOROUK_NEWS_SITEMAP_URL, timeout=12)
            root = ET.fromstring(news_sitemap_xml)
            ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9", "news": "http://www.google.com/schemas/sitemap-news/0.9"}
            for node in root.findall("sm:url", ns)[:260]:
                link = (node.findtext("sm:loc", "", ns) or "").strip()
                title = (node.findtext("news:news/news:title", "", ns) or "").strip()
                pub_raw = (node.findtext("news:news/news:publication_date", "", ns) or "").strip()
                pub_dt = None
                if pub_raw:
                    try:
                        pub_dt = datetime.fromisoformat(pub_raw.replace("Z", "+00:00")).replace(tzinfo=None)
                    except Exception:
                        pub_dt = None
                _upsert(link, title, None, pub_dt)
                sitemap_count += 1
            sitemap_ok = True
        except Exception as exc:
            logger.warning("link_index_news_sitemap_sync_failed", error=str(exc))

        await db.commit()
        if feed_ok or sitemap_ok or upserted > 0:
            self._last_public_sync_at = now
        logger.info("link_index_public_sync_done", upserted=upserted, feed=feed_count, sitemap=sitemap_count)
        return {
            "upserted": upserted,
            "feed": feed_count,
            "sitemap": sitemap_count,
            "feed_ok": 1 if feed_ok else 0,
            "sitemap_ok": 1 if sitemap_ok else 0,
        }

    async def _latest_draft(self, db: AsyncSession, work_id: str) -> EditorialDraft | None:
        row = await db.execute(
            select(EditorialDraft)
            .where(EditorialDraft.work_id == work_id, EditorialDraft.status == "draft")
            .order_by(desc(EditorialDraft.version))
            .limit(1)
        )
        return row.scalar_one_or_none()

    def _score_item(
        self,
        *,
        query_tokens: set[str],
        query_title: str,
        query_category: str | None,
        item: LinkIndexItem,
    ) -> _ScoredItem | None:
        if self._arabic_ratio(query_title) >= 0.35 and self._arabic_ratio(item.title or "") < 0.20:
            return None

        title_tokens = self._tokens(item.title or "")
        summary_tokens = self._tokens(item.summary or "")
        kw_tokens = self._tokens(" ".join(item.keywords_json or []))
        item_tokens = title_tokens.union(summary_tokens).union(kw_tokens)
        if not item_tokens:
            return None

        query_title_norm = re.sub(r"\s+", " ", (query_title or "").strip().lower())
        item_title_norm = re.sub(r"\s+", " ", (item.title or "").strip().lower())
        title_sim = SequenceMatcher(None, query_title_norm, item_title_norm).ratio() if query_title_norm and item_title_norm else 0.0

        overlap_set = query_tokens.intersection(item_tokens)
        overlap_count = len(overlap_set)
        if overlap_count == 0 and item.link_type == "internal":
            # Relaxed Arabic matching for internal links to avoid empty results
            title_norm = self._tokens(item.title or "")
            loose_hits: set[str] = set()
            for q in query_tokens:
                if len(q) < 4:
                    continue
                for t in title_norm:
                    if len(t) < 4:
                        continue
                    if q in t or t in q:
                        loose_hits.add(q)
                        break
            if loose_hits:
                overlap_set = loose_hits
                overlap_count = len(loose_hits)
            elif title_sim >= 0.42:
                overlap_set = {"عنوان-مشابه"}
                overlap_count = 1
        if overlap_count == 0:
            return None
        if item.link_type == "external" and overlap_count < 2:
            return None

        overlap_ratio = overlap_count / max(1, len(query_tokens))
        title_overlap = len(query_tokens.intersection(title_tokens)) / max(1, len(query_tokens))
        category_match = 1.0 if query_category and item.category and query_category == item.category else 0.0
        authority = max(0.0, min(1.0, self._safe_float(item.authority_score, 0.5)))

        recency = 0.45
        if item.published_at:
            age_hours = max(0.0, (self._now() - item.published_at).total_seconds() / 3600.0)  # type: ignore[operator]
            recency = math.exp(-age_hours / 220.0)

        score = (
            0.62 * overlap_ratio
            + 0.14 * title_overlap
            + 0.10 * category_match
            + 0.08 * recency
            + 0.06 * authority
            + 0.08 * title_sim
        )
        threshold = INTERNAL_SCORE_THRESHOLD if item.link_type == "internal" else EXTERNAL_SCORE_THRESHOLD
        if score < threshold:
            return None

        confidence = max(0.0, min(1.0, score * 1.28))
        anchor = self._build_anchor(query_tokens, item.title)
        link_kind = "داخلي" if item.link_type == "internal" else "خارجي"
        matched_preview = "، ".join(sorted(list(overlap_set))[:4]) if overlap_set else "تطابق عام"
        reason = f"مطابقة {link_kind}: {matched_preview}"
        placement = (
            "بعد فقرة الخلفية أو سياق الخبر"
            if item.link_type == "internal"
            else "بعد الجملة التي تحتوي تصريحا أو رقما يحتاج توثيقا"
        )
        rel_attrs = "internal" if item.link_type == "internal" else ("noopener noreferrer" if authority >= 0.85 else "noopener noreferrer nofollow")

        return _ScoredItem(
            item=item,
            score=round(score, 4),
            confidence=round(confidence, 4),
            anchor_text=anchor,
            reason=reason,
            placement_hint=placement,
            rel_attrs=rel_attrs,
        )

    def _build_anchor(self, query_tokens: set[str], title: str) -> str:
        clean_title = re.sub(r"\s+", " ", (title or "").strip())
        for tok in sorted(query_tokens, key=len, reverse=True):
            if tok and tok in clean_title:
                return tok[:80]
        words = clean_title.split()
        if not words:
            return "تفاصيل ذات صلة"
        return " ".join(words[: min(5, len(words))])[:120]

    async def suggest_for_workspace(
        self,
        db: AsyncSession,
        *,
        work_id: str,
        mode: str,
        target_count: int,
        actor: User | None,
    ) -> dict[str, Any]:
        if mode not in LINK_MODES:
            raise ValueError("Invalid mode")
        target_count = max(1, min(12, int(target_count)))

        draft = await self._latest_draft(db, work_id)
        if not draft:
            raise ValueError("Draft not found")
        article = None
        if draft.article_id:
            row = await db.execute(select(Article).where(Article.id == draft.article_id))
            article = row.scalar_one_or_none()

        sync_stats = await self.sync_index_from_articles(db)
        public_sync = {"upserted": 0, "feed": 0, "sitemap": 0}
        if mode in {"internal", "mixed"}:
            public_sync = await self.sync_internal_from_public_sources(db)

        body_text = re.sub(r"<[^>]+>", " ", draft.body or "")
        query_title = (draft.title or (article.title_ar if article else "") or (article.original_title if article else "") or "").strip()
        query_category = article.category.value if article and getattr(article.category, "value", None) else None
        query_tokens = self._tokens(query_title)
        if len(query_tokens) < 6:
            body_tokens = self._tokens(body_text)
            for tok in body_tokens:
                query_tokens.add(tok)
                if len(query_tokens) >= 14:
                    break
        if not query_tokens:
            query_tokens = {"الجزائر", "خبر"}

        stmt = select(LinkIndexItem).where(LinkIndexItem.is_active.is_(True))
        if mode == "internal":
            stmt = stmt.where(LinkIndexItem.link_type == "internal")
        elif mode == "external":
            stmt = stmt.where(LinkIndexItem.link_type == "external")
        rows = await db.execute(stmt.order_by(desc(LinkIndexItem.published_at)).limit(2500))
        candidates = rows.scalars().all()
        trusted = await self._load_trusted_domains(db)
        internal_candidates_total = len([c for c in candidates if c.link_type == "internal"])
        external_candidates_total = len([c for c in candidates if c.link_type == "external"])

        if mode in {"internal", "mixed"} and internal_candidates_total == 0:
            retry_sync = await self.sync_internal_from_public_sources(db, force=True)
            public_sync = {
                **public_sync,
                "retry_upserted": retry_sync.get("upserted", 0),
                "retry_feed": retry_sync.get("feed", 0),
                "retry_sitemap": retry_sync.get("sitemap", 0),
                "retry_feed_ok": retry_sync.get("feed_ok", 0),
                "retry_sitemap_ok": retry_sync.get("sitemap_ok", 0),
            }
            rows = await db.execute(stmt.order_by(desc(LinkIndexItem.published_at)).limit(2500))
            candidates = rows.scalars().all()
            internal_candidates_total = len([c for c in candidates if c.link_type == "internal"])
            external_candidates_total = len([c for c in candidates if c.link_type == "external"])

        source_url = self._canonical_url(article.original_url) if article and article.original_url else ""

        scored_internal: list[_ScoredItem] = []
        scored_external: list[_ScoredItem] = []
        for item in candidates:
            if source_url and item.url == source_url:
                continue
            if item.link_type == "external":
                domain = (item.domain or "").lower()
                td = trusted.get(domain)
                if not td:
                    continue
                if self._safe_float(td.trust_score, 0.0) < TRUSTED_EXTERNAL_MIN:
                    continue
            scored = self._score_item(query_tokens=query_tokens, query_title=query_title, query_category=query_category, item=item)
            if not scored:
                continue
            if item.link_type == "internal":
                scored_internal.append(scored)
            else:
                scored_external.append(scored)

        scored_internal.sort(key=lambda x: x.score, reverse=True)
        scored_external.sort(key=lambda x: x.score, reverse=True)

        selected: list[_ScoredItem] = []
        if mode == "internal":
            selected = scored_internal[:target_count]
        elif mode == "external":
            selected = self._dedupe_by_domain(scored_external, target_count)
        else:
            top_external = self._dedupe_by_domain(scored_external, 1)
            allow_external = bool(top_external and top_external[0].score >= 0.42)
            internal_target = target_count - (1 if allow_external else 0)
            selected.extend(scored_internal[: max(0, internal_target)])
            if allow_external:
                selected.extend(top_external[:1])
            if len(selected) < target_count:
                missing = target_count - len(selected)
                backup = scored_internal[len(selected): len(selected) + missing]
                selected.extend(backup)
        selected_before_fallback = len(selected)

        # Hard fallback: never return empty internal suggestions when internal candidates exist
        if mode in {"internal", "mixed"} and not [x for x in selected if x.item.link_type == "internal"]:
            fallback_items = [c for c in candidates if c.link_type == "internal"]
            fallback_items.sort(key=lambda x: x.published_at or datetime.min, reverse=True)
            for fb in fallback_items[: min(8, target_count)]:
                if self._arabic_ratio(fb.title or "") < 0.2:
                    continue
                selected.append(
                    _ScoredItem(
                        item=fb,
                        score=0.2401,
                        confidence=0.41,
                        anchor_text=self._build_anchor(query_tokens, fb.title or ""),
                        reason="مطابقة داخلية احتياطية من أحدث محتوى الشروق",
                        placement_hint="بعد الفقرة التي تشرح خلفية الخبر",
                        rel_attrs="internal",
                    )
                )
                if len([x for x in selected if x.item.link_type == "internal"]) >= max(1, min(3, target_count)):
                    break

        # Deduplicate final list by URL and cap to target_count
        final_selected: list[_ScoredItem] = []
        seen_urls: set[str] = set()
        for rec in selected:
            url_key = rec.item.url
            if url_key in seen_urls:
                continue
            seen_urls.add(url_key)
            final_selected.append(rec)
            if len(final_selected) >= target_count:
                break
        selected = final_selected

        run_id = f"LNK-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{abs(hash((work_id, datetime.utcnow().isoformat()))) % 10_000_000:07d}"
        run = LinkRecommendationRun(
            run_id=run_id,
            work_id=work_id,
            article_id=draft.article_id,
            draft_id=draft.id,
            mode=mode,
            status="completed",
            source_counts_json={
                "internal_candidates_total": internal_candidates_total,
                "external_candidates_total": external_candidates_total,
                "internal_pool": len(scored_internal),
                "external_pool": len(scored_external),
                "internal_selected": len([x for x in selected if x.item.link_type == "internal"]),
                "external_selected": len([x for x in selected if x.item.link_type == "external"]),
                "selected_before_fallback": selected_before_fallback,
                "selected": len(selected),
                "query_terms": sorted(list(query_tokens))[:8],
                "sync": sync_stats,
                "sync_public": public_sync,
            },
            created_by_user_id=actor.id if actor else None,
            created_by_username=actor.username if actor else "system",
            finished_at=self._now(),
        )
        db.add(run)
        await db.flush()

        items_payload: list[dict[str, Any]] = []
        for rec in selected:
            ri = LinkRecommendationItem(
                run_id=run_id,
                link_index_item_id=rec.item.id,
                link_type=rec.item.link_type,
                url=rec.item.url,
                title=rec.item.title[:1024],
                anchor_text=rec.anchor_text[:255],
                placement_hint=rec.placement_hint[:255],
                reason=rec.reason,
                score=rec.score,
                confidence=rec.confidence,
                rel_attrs=rec.rel_attrs[:128] if rec.rel_attrs else None,
                status="suggested",
                metadata_json={
                    "domain": rec.item.domain,
                    "authority_score": rec.item.authority_score,
                    "published_at": rec.item.published_at.isoformat() if rec.item.published_at else None,
                },
            )
            db.add(ri)
            items_payload.append(
                {
                    "id": None,
                    "link_type": ri.link_type,
                    "url": ri.url,
                    "title": ri.title,
                    "anchor_text": ri.anchor_text,
                    "placement_hint": ri.placement_hint,
                    "reason": ri.reason,
                    "score": ri.score,
                    "confidence": ri.confidence,
                    "rel_attrs": ri.rel_attrs,
                    "status": ri.status,
                    "metadata": ri.metadata_json,
                }
            )

        await db.commit()
        # refresh IDs for response
        result_rows = await db.execute(
            select(LinkRecommendationItem).where(LinkRecommendationItem.run_id == run_id).order_by(desc(LinkRecommendationItem.score))
        )
        result_items = result_rows.scalars().all()
        items_payload = [
            {
                "id": it.id,
                "link_type": it.link_type,
                "url": it.url,
                "title": it.title,
                "anchor_text": it.anchor_text,
                "placement_hint": it.placement_hint,
                "reason": it.reason,
                "score": it.score,
                "confidence": it.confidence,
                "rel_attrs": it.rel_attrs,
                "status": it.status,
                "metadata": it.metadata_json or {},
            }
            for it in result_items
        ]
        return {"run_id": run_id, "mode": mode, "work_id": work_id, "items": items_payload, "source_counts": run.source_counts_json}

    @staticmethod
    def _dedupe_by_domain(items: list[_ScoredItem], limit: int) -> list[_ScoredItem]:
        out: list[_ScoredItem] = []
        seen: set[str] = set()
        for rec in items:
            domain = (rec.item.domain or "").lower()
            if domain and domain in seen:
                continue
            out.append(rec)
            if domain:
                seen.add(domain)
            if len(out) >= limit:
                break
        return out

    async def validate_run(self, db: AsyncSession, run_id: str) -> dict[str, Any]:
        rows = await db.execute(
            select(LinkRecommendationItem)
            .where(LinkRecommendationItem.run_id == run_id)
            .order_by(desc(LinkRecommendationItem.score))
            .limit(50)
        )
        items = rows.scalars().all()
        if not items:
            return {"run_id": run_id, "checked": 0, "alive": 0, "dead": 0}

        alive = 0
        dead = 0
        for item in items:
            status_code, ok = self._check_url(item.url)
            meta = dict(item.metadata_json or {})
            meta["http_status"] = status_code
            meta["reachable"] = ok
            item.metadata_json = meta
            if ok:
                alive += 1
            else:
                dead += 1
                item.status = "rejected"
        await db.commit()
        return {"run_id": run_id, "checked": len(items), "alive": alive, "dead": dead}

    @staticmethod
    def _check_url(url: str) -> tuple[int, bool]:
        try:
            req = Request(url, method="HEAD", headers={"User-Agent": "Mozilla/5.0"})
            with urlopen(req, timeout=7) as resp:
                code = int(getattr(resp, "status", 200) or 200)
                return code, 200 <= code < 400
        except Exception:
            try:
                req = Request(url, method="GET", headers={"User-Agent": "Mozilla/5.0"})
                with urlopen(req, timeout=7) as resp:
                    code = int(getattr(resp, "status", 200) or 200)
                    return code, 200 <= code < 400
            except Exception:
                return 0, False

    async def get_run_items(self, db: AsyncSession, run_id: str, item_ids: list[int] | None = None) -> list[LinkRecommendationItem]:
        stmt = select(LinkRecommendationItem).where(
            LinkRecommendationItem.run_id == run_id,
            LinkRecommendationItem.status == "suggested",
        )
        if item_ids:
            stmt = stmt.where(LinkRecommendationItem.id.in_(item_ids))
        rows = await db.execute(stmt.order_by(desc(LinkRecommendationItem.score)))
        return rows.scalars().all()

    async def mark_applied(self, db: AsyncSession, item_ids: list[int]) -> None:
        if not item_ids:
            return
        rows = await db.execute(select(LinkRecommendationItem).where(LinkRecommendationItem.id.in_(item_ids)))
        for item in rows.scalars().all():
            item.status = "applied"
        await db.commit()

    async def history(self, db: AsyncSession, work_id: str, limit: int = 10) -> list[dict[str, Any]]:
        runs_rows = await db.execute(
            select(LinkRecommendationRun)
            .where(LinkRecommendationRun.work_id == work_id)
            .order_by(desc(LinkRecommendationRun.created_at))
            .limit(limit)
        )
        runs = runs_rows.scalars().all()
        out: list[dict[str, Any]] = []
        for run in runs:
            items_rows = await db.execute(
                select(LinkRecommendationItem)
                .where(LinkRecommendationItem.run_id == run.run_id)
                .order_by(desc(LinkRecommendationItem.score))
                .limit(20)
            )
            items = items_rows.scalars().all()
            out.append(
                {
                    "run_id": run.run_id,
                    "mode": run.mode,
                    "status": run.status,
                    "created_at": run.created_at.isoformat() if run.created_at else None,
                    "source_counts": run.source_counts_json or {},
                    "items": [
                        {
                            "id": it.id,
                            "link_type": it.link_type,
                            "url": it.url,
                            "title": it.title,
                            "anchor_text": it.anchor_text,
                            "score": it.score,
                            "confidence": it.confidence,
                            "status": it.status,
                        }
                        for it in items
                    ],
                }
            )
        return out

    def apply_links_to_html(self, body_html: str, items: list[LinkRecommendationItem]) -> tuple[str, int]:
        html = body_html or ""
        if not items:
            return html, 0

        existing_urls = {m.group(1) for m in re.finditer(r'href=["\']([^"\']+)["\']', html, flags=re.IGNORECASE)}
        internal_items = [i for i in items if i.link_type == "internal" and i.url not in existing_urls]
        external_items = [i for i in items if i.link_type == "external" and i.url not in existing_urls]
        if not internal_items and not external_items:
            return html, 0

        sections: list[str] = []
        applied = 0
        if internal_items:
            sections.append("<h2>اقرأ أيضا</h2><ul>")
            for item in internal_items[:5]:
                anchor = self._escape_html(item.anchor_text or item.title or "تفاصيل ذات صلة")
                url = self._escape_html(item.url)
                sections.append(f'<li><a href="{url}">{anchor}</a></li>')
                applied += 1
            sections.append("</ul>")

        if external_items:
            sections.append("<h2>مراجع خارجية موثوقة</h2><ul>")
            for item in external_items[:3]:
                anchor = self._escape_html(item.anchor_text or item.title or "مرجع خارجي")
                url = self._escape_html(item.url)
                rel = self._escape_html(item.rel_attrs or "noopener noreferrer")
                sections.append(f'<li><a href="{url}" target="_blank" rel="{rel}">{anchor}</a></li>')
                applied += 1
            sections.append("</ul>")

        appendix = "".join(sections)
        if "</body>" in html.lower():
            new_html = re.sub(r"</body>", appendix + "</body>", html, count=1, flags=re.IGNORECASE)
            return new_html, applied
        return f"{html}\n{appendix}", applied

    @staticmethod
    def _escape_html(value: str) -> str:
        return (
            (value or "")
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )


link_intelligence_service = LinkIntelligenceService()

