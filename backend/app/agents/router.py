"""
Echorouk AI Swarm — Router Agent (الموجّه)
=============================================
Triage Layer: Rule-based routing + AI classification.
Cost Optimization: Rules first, AI only when uncertain.
"""

import re
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models import Article, Source, NewsStatus, NewsCategory, UrgencyLevel
from app.services.ai_service import ai_service
from app.services.cache_service import cache_service
from app.services.notification_service import notification_service

logger = get_logger("agent.router")
settings = get_settings()


# ── Rule-Based Keyword Maps (Free, no AI cost) ──

CATEGORY_KEYWORDS = {
    NewsCategory.POLITICS: [
        "رئيس", "وزير", "برلمان", "حكومة", "انتخابات", "دبلوماسي", "سفير",
        "تبون", "رئاسة", "مجلس", "قانون", "مرسوم", "سيادي",
        "president", "minister", "parliament", "election", "politique",
    ],
    NewsCategory.ECONOMY: [
        "اقتصاد", "بنك", "ميزانية", "نفط", "غاز", "سوناطراك", "بورصة",
        "تضخم", "دينار", "استثمار", "تجارة", "صادرات", "واردات",
        "économie", "banque", "pétrole", "sonatrach", "investissement",
    ],
    NewsCategory.SPORTS: [
        "رياضة", "كرة", "منتخب", "بطولة", "لاعب", "هدف", "مباراة",
        "محرز", "بلماضي", "الخضر", "فاف", "دوري",
        "sport", "football", "match", "joueur", "équipe",
    ],
    NewsCategory.TECHNOLOGY: [
        "تكنولوجيا", "إنترنت", "تطبيق", "هاتف", "ذكاء اصطناعي", "رقمنة",
        "technology", "internet", "application", "numérique", "intelligence artificielle",
    ],
    NewsCategory.HEALTH: [
        "صحة", "مستشفى", "طبيب", "دواء", "وباء", "لقاح", "علاج",
        "santé", "hôpital", "médecin", "vaccin",
    ],
    NewsCategory.CULTURE: [
        "ثقافة", "فن", "سينما", "مسرح", "كتاب", "مهرجان", "موسيقى",
        "culture", "cinéma", "festival", "livre",
    ],
    NewsCategory.ENVIRONMENT: [
        "بيئة", "مناخ", "زلزال", "فيضان", "حرائق", "جفاف",
        "environnement", "climat", "séisme", "inondation",
    ],
    NewsCategory.SOCIETY: [
        "مجتمع", "تعليم", "جامعة", "مدرسة", "شباب", "سكن", "نقل",
        "société", "éducation", "université", "transport", "logement",
    ],
}

BREAKING_KEYWORDS = [
    "عاجل", "حصري", "طارئ", "زلزال", "انفجار", "وفاة", "اغتيال",
    "breaking", "urgent", "séisme", "explosion", "attentat",
]

NOISE_PATTERNS = [
    r"\bwordle\b",
    r"\bcrossword\b",
    r"\bnyt mini\b",
    r"\bconnections\b",
    r"\bquordle\b",
    r"\bhints?\b",
    r"\banswers?\b",
    r"\bhoroscope\b",
    r"\bsudoku\b",
]

LOCAL_SIGNAL_KEYWORDS = [
    "الجزائر", "جزائري", "الجزائرية", "algérie", "algerie", "algeria",
    "وهران", "الجزائر العاصمة", "قسنطينة", "سطيف", "عنابة", "تلمسان", "بجاية",
]

LOCAL_SOURCE_KEYWORDS = [
    "algeria", "algérie", "algerie", "dz", "aps", "tsa", "echorouk", "el khabar", "elwatan",
    "الجزائر", "الجزائرية", "الشروق", "الخبر", "النهار", "وكالة الأنباء الجزائرية",
]

ARABIC_CHAR_RE = re.compile(r"[ء-ي]")
ROUTER_SOURCE_QUOTA = 6
ROUTER_CANDIDATE_SOURCE_QUOTA = 3


class RouterAgent:
    """
    Router Agent — classifies and routes news articles.
    Rule-based first (free), AI only when uncertain.
    This can reduce AI calls by 50-80%.
    """

    async def process_batch(self, db: AsyncSession, limit: int = 50) -> dict:
        """Process a batch of NEW articles through triage."""
        stats = {"processed": 0, "candidates": 0, "ai_calls": 0, "breaking": 0}

        # Pull a wider pool, then apply source quotas + local-priority ordering.
        result = await db.execute(
            select(Article, Source)
            .outerjoin(Source, Article.source_id == Source.id)
            .where(Article.status == NewsStatus.NEW)
            .order_by(Article.crawled_at.desc())
            .with_for_update(skip_locked=True)
            .limit(limit * 4)
        )
        rows = result.all()
        selected = self._select_articles_for_batch(rows, limit)

        for article, source in selected:
            try:
                await self._classify_article(db, article, source, stats)
                stats["processed"] += 1
            except Exception as e:
                logger.error("router_article_error",
                             article_id=article.id,
                             error=str(e))
                article.status = NewsStatus.CLEANED  # Park it
                article.retry_count += 1

        await db.commit()
        logger.info("router_batch_complete", **stats)
        return stats

    async def _classify_article(self, db: AsyncSession, article: Article, source: Optional[Source], stats: dict):
        """Classify a single article using rules + AI fallback."""

        text = f"{article.original_title} {article.original_content or ''}"
        text_lower = text.lower()

        # Step 0: Early noise gate (before paying any AI cost)
        noisy, noisy_reason = self._noise_gate(article, text_lower)
        if noisy:
            article.status = NewsStatus.ARCHIVED
            article.importance_score = 0
            article.rejection_reason = f"auto_filtered:{noisy_reason}"
            return

        # Step 0b: Arabic sources should produce Arabic headlines.
        if self._is_arabic_source(article, source) and not ARABIC_CHAR_RE.search(article.original_title or ""):
            article.status = NewsStatus.REJECTED
            article.importance_score = 0
            article.rejection_reason = "auto_filtered:arabic_source_non_arabic_title"
            return

        # ── Step 1: Rule-Based Classification (FREE) ──
        category = self._rule_based_category(text)
        urgency = self._rule_based_urgency(text)

        # ── Step 2: Check if Breaking News ──
        if urgency == UrgencyLevel.BREAKING:
            article.is_breaking = True
            article.urgency = UrgencyLevel.BREAKING
            stats["breaking"] += 1

            # Send immediate alert
            await notification_service.send_breaking_alert(
                title=article.original_title,
                summary=article.original_content[:200] if article.original_content else "",
                source=article.source_name or "Unknown",
                url=article.original_url,
            )

        # ── Step 3: AI Classification (only if rule-based is uncertain) ──
        if category is None:
            # Need AI for classification
            try:
                analysis = await ai_service.analyze_news(
                    text[:4000],
                    source=article.source_name or "",
                )
                stats["ai_calls"] += 1
                await cache_service.increment_counter("ai_calls_today")

                # Apply AI results
                article.title_ar = analysis.title_ar
                article.summary = analysis.summary
                article.category = NewsCategory(analysis.category) if analysis.category in [e.value for e in NewsCategory] else NewsCategory.LOCAL_ALGERIA
                article.importance_score = analysis.importance_score
                article.is_breaking = analysis.is_breaking or article.is_breaking
                article.sentiment = analysis.sentiment
                article.entities = analysis.entities
                article.keywords = analysis.keywords
                article.ai_model_used = settings.gemini_model_flash

                if analysis.is_breaking and not article.is_breaking:
                    article.urgency = UrgencyLevel.BREAKING
                    stats["breaking"] += 1

            except Exception as e:
                logger.warning("ai_classification_failed", error=str(e))
                article.category = NewsCategory.LOCAL_ALGERIA
                article.importance_score = 5
        else:
            # Rule-based category was sufficient
            article.category = category
            article.importance_score = self._estimate_importance(text, category)
            article.urgency = urgency
            if not article.title_ar:
                article.title_ar = article.original_title
            if not article.summary:
                article.summary = (article.original_content or article.original_title)[:300]

        # ── Step 4: Determine if Candidate ──
        has_local_signal = self._has_local_signal(text_lower, article.source_name or "")
        is_candidate = (
            article.importance_score >= settings.editorial_min_importance
            or article.is_breaking
            or article.urgency in [UrgencyLevel.HIGH, UrgencyLevel.BREAKING]
        )
        if settings.editorial_require_local_signal and not (article.is_breaking or article.urgency == UrgencyLevel.BREAKING):
            is_candidate = is_candidate and has_local_signal

        if is_candidate:
            article.status = NewsStatus.CANDIDATE
            stats["candidates"] += 1

            # Notify editors (deduped per article for 12h)
            notify_key = f"candidate_notified:{article.id}"
            already_notified = await cache_service.get(notify_key)
            if not already_notified:
                await notification_service.send_candidate_for_review(
                    article_id=article.id,
                    title=article.title_ar or article.original_title,
                    summary=article.summary or (article.original_content[:200] if article.original_content else ""),
                    source=article.source_name or "Unknown",
                    importance=article.importance_score,
                    category=article.category.value if article.category else "general",
                )
                await cache_service.set(notify_key, "1", ttl=timedelta(hours=12))
        else:
            article.status = NewsStatus.CLASSIFIED
            article.rejection_reason = "auto_filtered:low_editorial_value"

    def _select_articles_for_batch(
        self,
        rows: list[tuple[Article, Optional[Source]]],
        limit: int,
    ) -> list[tuple[Article, Optional[Source]]]:
        """Prioritize local relevance and prevent a single source from flooding the batch."""
        if not rows:
            return []

        def score_row(row: tuple[Article, Optional[Source]]) -> tuple[int, int, datetime]:
            article, source = row
            text = f"{article.original_title or ''} {article.original_content or ''}".lower()
            source_name = (source.name if source else article.source_name) or ""
            has_local_signal = 1 if self._has_local_signal(text, source_name) else 0
            local_source = 1 if any(k in source_name.lower() for k in LOCAL_SOURCE_KEYWORDS) else 0
            crawled = article.crawled_at or datetime.min
            return (local_source, has_local_signal, crawled)

        rows_sorted = sorted(rows, key=score_row, reverse=True)
        selected: list[tuple[Article, Optional[Source]]] = []
        per_source_total: dict[str, int] = {}
        per_source_candidate_like: dict[str, int] = {}

        for article, source in rows_sorted:
            if len(selected) >= limit:
                break

            source_key = str(source.id) if source and source.id else (article.source_name or "unknown")
            total_count = per_source_total.get(source_key, 0)
            if total_count >= ROUTER_SOURCE_QUOTA:
                continue

            text_lower = f"{article.original_title or ''} {article.original_content or ''}".lower()
            source_name = (source.name if source else article.source_name) or ""
            candidate_like = self._has_local_signal(text_lower, source_name)
            if candidate_like and per_source_candidate_like.get(source_key, 0) >= ROUTER_CANDIDATE_SOURCE_QUOTA:
                continue

            selected.append((article, source))
            per_source_total[source_key] = total_count + 1
            if candidate_like:
                per_source_candidate_like[source_key] = per_source_candidate_like.get(source_key, 0) + 1

        return selected

    def _rule_based_category(self, text: str) -> Optional[NewsCategory]:
        """Determine category using keyword matching (no AI cost)."""
        if not text:
            return None

        text_lower = text.lower()
        scores = {}

        for category, keywords in CATEGORY_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in text_lower)
            if score > 0:
                scores[category] = score

        if not scores:
            return None  # Uncertain → needs AI

        # Return category with highest keyword matches
        best = max(scores, key=scores.get)

        # Only trust rule-based if confidence is decent (2+ keywords)
        if scores[best] >= 2:
            return best
        return None  # Low confidence → use AI

    def _rule_based_urgency(self, text: str) -> UrgencyLevel:
        """Detect urgency level from keywords."""
        if not text:
            return UrgencyLevel.LOW

        text_lower = text.lower()
        breaking_count = sum(1 for kw in BREAKING_KEYWORDS if kw in text_lower)

        if breaking_count >= 2:
            return UrgencyLevel.BREAKING
        elif breaking_count == 1:
            return UrgencyLevel.HIGH

        return UrgencyLevel.MEDIUM

    def _estimate_importance(self, text: str, category: Optional[NewsCategory]) -> int:
        """Estimate importance score using heuristics."""
        score = 5  # Default

        # Algeria-specific content gets a boost
        algeria_keywords = ["جزائر", "algérie", "algeria", "الجزائر"]
        if any(kw in text.lower() for kw in algeria_keywords):
            score += 2

        # Breaking keywords boost
        if any(kw in text.lower() for kw in BREAKING_KEYWORDS):
            score += 2

        # Politics & Economy tend to be more important
        if category in [NewsCategory.POLITICS, NewsCategory.ECONOMY]:
            score += 1

        return min(score, 10)

    def _has_local_signal(self, text_lower: str, source_name: str) -> bool:
        if any(k in text_lower for k in LOCAL_SIGNAL_KEYWORDS):
            return True
        src = (source_name or "").lower()
        if any(k in src for k in ["aps", "tsa", "echorouk", "el khabar", "elwatan", "dz", "algerie", "algérie"]):
            return True
        return False

    def _noise_gate(self, article: Article, text_lower: str) -> tuple[bool, str]:
        title = (article.original_title or "").strip()
        content = (article.original_content or "").strip()

        if len(title) < 12:
            return True, "title_too_short"
        if len(content) < 40 and not article.is_breaking:
            return True, "content_too_short"

        for pattern in NOISE_PATTERNS:
            if re.search(pattern, text_lower):
                return True, "game_or_puzzle_noise"

        # Common low-value aggregator stream that floods newsroom
        if (article.source_name or "").lower().startswith("google news") and not self._has_local_signal(text_lower, article.source_name or ""):
            return True, "global_aggregator_non_local"

        return False, ""

    def _is_arabic_source(self, article: Article, source: Optional[Source]) -> bool:
        src_lang = (source.language if source and source.language else "").lower()
        if src_lang == "ar":
            return True
        source_name = (source.name if source else article.source_name) or ""
        source_name = source_name.lower()
        return any(k in source_name for k in ["عربي", "العربية", "الجزيرة", "سكاي نيوز عربية", "الخبر", "الشروق", "النهار"])


# Singleton
router_agent = RouterAgent()
