"""
Echorouk Editorial OS — Router Agent (الموجّه)
=============================================
Triage Layer: Rule-based routing + AI classification.
Cost Optimization: Rules first, AI only when uncertain.
"""

import re
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select, update, and_
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
    "\u0639\u0627\u062c\u0644",
    "\u0647\u0627\u0645",
    "\u0627\u0644\u0622\u0646",
    "\u062a\u0646\u0628\u064a\u0647",
    "\u062e\u0627\u0635",
    "\u0641\u0648\u0631\u0627",
    "\u0641\u0648\u0631\u064b\u0627",
    "\u0627\u0646\u0641\u0631\u0627\u062f",
    "\u0645\u062a\u0627\u0628\u0639\u0629",
    "\u0637\u0627\u0631\u0626",
    "breaking",
    "urgent",
    "alerte",
]

BREAKING_ACTION_TERMS = [
    "\u0642\u0631\u0627\u0631",
    "\u0642\u0631\u0627\u0631\u0627\u062a",
    "\u0642\u0631\u0631",
    "\u0628\u064a\u0627\u0646",
    "\u0628\u064a\u0627\u0646 \u0631\u0633\u0645\u064a",
    "\u0628\u064a\u0627\u0646 \u0647\u0627\u0645",
    "\u0627\u062c\u062a\u0645\u0627\u0639",
    "\u0627\u062c\u062a\u0645\u0627\u0639 \u0627\u0644\u062d\u0643\u0648\u0645\u0629",
    "\u064a\u0639\u0644\u0646",
    "\u062a\u0639\u0644\u0646",
    "\u062a\u0639\u0644\u064a\u0645\u0627\u062a",
    "\u0625\u062c\u0631\u0627\u0621\u0627\u062a",
    "\u062d\u0631\u0643\u0629 \u0627\u0644\u0648\u0644\u0627\u0629",
    "\u0646\u0634\u0631\u064a\u0629 \u062e\u0627\u0635\u0629",
    "\u062a\u0637\u0648\u0631\u0627\u062a",
    "\u0627\u0644\u0645\u0648\u0642\u0641 \u0627\u0644\u062c\u0632\u0627\u0626\u0631\u064a",
    "\u0627\u0643\u062a\u0634\u0627\u0641\u0627\u062a",
    "\u0627\u062a\u0641\u0627\u0642\u064a\u0627\u062a",
    "\u0646\u062a\u0627\u0626\u062c \u0627\u0644\u0628\u0643\u0627\u0644\u0648\u0631\u064a\u0627",
    "\u0645\u0633\u0627\u0628\u0642\u0627\u062a \u0627\u0644\u062a\u0648\u0638\u064a\u0641",
    "\u0633\u0639\u0631 \u0627\u0644\u0635\u0631\u0641",
    "\u0642\u0631\u0627\u0631\u0627\u062a \u0645\u0627\u0644\u064a\u0629",
    "\u0627\u0644\u062a\u0636\u062e\u0645",
]

BREAKING_EVENT_TERMS = [
    "\u0632\u0644\u0632\u0627\u0644",
    "\u0627\u0646\u0641\u062c\u0627\u0631",
    "\u0627\u063a\u062a\u064a\u0627\u0644",
    "\u062d\u0631\u0627\u0626\u0642",
    "\u0641\u064a\u0636\u0627\u0646\u0627\u062a",
    "\u062d\u0627\u062f\u062b \u062e\u0637\u064a\u0631",
    "\u0627\u0646\u0642\u0637\u0627\u0639 \u0648\u0627\u0633\u0639",
    "\u0648\u0641\u0627\u0629",
    "seisme",
    "explosion",
    "attentat",
]

BREAKING_GOVERNANCE_TERMS = [
    "\u0631\u0626\u0627\u0633\u0629 \u0627\u0644\u062c\u0645\u0647\u0648\u0631\u064a\u0629",
    "\u0627\u0644\u0631\u0626\u064a\u0633 \u0639\u0628\u062f \u0627\u0644\u0645\u062c\u064a\u062f \u062a\u0628\u0648\u0646",
    "\u0627\u0644\u0631\u0626\u064a\u0633 \u062a\u0628\u0648\u0646",
    "\u062a\u0628\u0648\u0646",
    "\u0642\u0631\u0627\u0631\u0627\u062a \u0633\u064a\u0627\u062f\u064a\u0629",
    "\u0627\u0644\u0648\u0632\u064a\u0631 \u0627\u0644\u0623\u0648\u0644",
    "\u0646\u0630\u064a\u0631 \u0627\u0644\u0639\u0631\u0628\u0627\u0648\u064a",
    "\u0627\u0644\u0648\u0632\u0627\u0631\u0629 \u0627\u0644\u0623\u0648\u0644\u0649",
    "\u0645\u062c\u0644\u0633 \u0627\u0644\u0648\u0632\u0631\u0627\u0621",
]

BREAKING_DEFENSE_TERMS = [
    "\u0648\u0632\u0627\u0631\u0629 \u0627\u0644\u062f\u0641\u0627\u0639 \u0627\u0644\u0648\u0637\u0646\u064a",
    "\u0627\u0644\u062c\u064a\u0634 \u0627\u0644\u0648\u0637\u0646\u064a \u0627\u0644\u0634\u0639\u0628\u064a",
    "\u0627\u0644\u0641\u0631\u064a\u0642 \u0623\u0648\u0644 \u0627\u0644\u0633\u0639\u064a\u062f \u0634\u0646\u0642\u0631\u064a\u062d\u0629",
    "\u0634\u0646\u0642\u0631\u064a\u062d\u0629",
    "\u0628\u064a\u0627\u0646 \u0648\u0632\u0627\u0631\u0629 \u0627\u0644\u062f\u0641\u0627\u0639",
]

BREAKING_INTERIOR_TERMS = [
    "\u0648\u0632\u0627\u0631\u0629 \u0627\u0644\u062f\u0627\u062e\u0644\u064a\u0629 \u0648\u0627\u0644\u062c\u0645\u0627\u0639\u0627\u062a \u0627\u0644\u0645\u062d\u0644\u064a\u0629",
    "\u0625\u0628\u0631\u0627\u0647\u064a\u0645 \u0645\u0631\u0627\u062f",
    "\u062d\u0631\u0643\u0629 \u0627\u0644\u0648\u0644\u0627\u0629",
    "\u0627\u0644\u062d\u0645\u0627\u064a\u0629 \u0627\u0644\u0645\u062f\u0646\u064a\u0629",
]

BREAKING_WEATHER_TERMS = [
    "\u0627\u0644\u062f\u064a\u0648\u0627\u0646 \u0627\u0644\u0648\u0637\u0646\u064a \u0644\u0644\u0623\u0631\u0635\u0627\u062f \u0627\u0644\u062c\u0648\u064a\u0629",
    "\u0646\u0634\u0631\u064a\u0629 \u062e\u0627\u0635\u0629",
    "\u0623\u062d\u0648\u0627\u0644 \u0627\u0644\u0637\u0642\u0633",
    "\u0623\u0645\u0637\u0627\u0631 \u063a\u0632\u064a\u0631\u0629",
    "\u0631\u064a\u0627\u062d \u0642\u0648\u064a\u0629",
    "\u0639\u0627\u0635\u0641\u0629",
    "\u0639\u0627\u0635\u0641\u0629 \u062b\u0644\u062c\u064a\u0629",
    "\u0641\u064a\u0636\u0627\u0646\u0627\u062a",
]

BREAKING_FOREIGN_AFFAIRS_TERMS = [
    "\u0648\u0632\u0627\u0631\u0629 \u0627\u0644\u062e\u0627\u0631\u062c\u064a\u0629",
    "\u0623\u062d\u0645\u062f \u0639\u0637\u0627\u0641",
    "\u0627\u0644\u0623\u0632\u0645\u0629 \u0627\u0644\u0625\u0642\u0644\u064a\u0645\u064a\u0629",
    "\u0627\u0644\u0645\u0648\u0642\u0641 \u0627\u0644\u062c\u0632\u0627\u0626\u0631\u064a",
    "\u0627\u0644\u0633\u0627\u062d\u0644",
    "\u0627\u0644\u0627\u062a\u062d\u0627\u062f \u0627\u0644\u0625\u0641\u0631\u064a\u0642\u064a",
]

BREAKING_EDUCATION_TERMS = [
    "\u0648\u0632\u0627\u0631\u0629 \u0627\u0644\u062a\u0631\u0628\u064a\u0629",
    "\u0628\u0644\u0639\u0627\u0628\u062f",
    "\u0646\u062a\u0627\u0626\u062c \u0627\u0644\u0628\u0643\u0627\u0644\u0648\u0631\u064a\u0627",
    "\u0646\u062a\u0627\u0626\u062c \u0627\u0644\u062a\u0639\u0644\u064a\u0645 \u0627\u0644\u0645\u062a\u0648\u0633\u0637",
    "\u0645\u0633\u0627\u0628\u0642\u0627\u062a \u0627\u0644\u062a\u0648\u0638\u064a\u0641",
]

BREAKING_ENERGY_TERMS = [
    "\u0633\u0648\u0646\u0627\u0637\u0631\u0627\u0643",
    "\u062d\u0634\u064a\u0634\u064a",
    "\u0627\u0643\u062a\u0634\u0627\u0641\u0627\u062a \u0646\u0641\u0637\u064a\u0629",
    "\u0627\u062a\u0641\u0627\u0642\u064a\u0627\u062a \u0637\u0627\u0642\u0629",
    "\u0635\u0641\u0642\u0629 \u063a\u0627\u0632",
]

BREAKING_HUMANITARIAN_TERMS = [
    "\u0627\u0644\u0647\u0644\u0627\u0644 \u0627\u0644\u0623\u062d\u0645\u0631 \u0627\u0644\u062c\u0632\u0627\u0626\u0631\u064a",
    "\u0627\u0628\u062a\u0633\u0627\u0645 \u062d\u0645\u0644\u0627\u0648\u064a",
    "\u0645\u0633\u0627\u0639\u062f\u0627\u062a \u0625\u0646\u0633\u0627\u0646\u064a\u0629",
    "\u0642\u0627\u0641\u0644\u0629 \u0645\u0633\u0627\u0639\u062f\u0627\u062a",
]

BREAKING_FINANCE_TERMS = [
    "\u0628\u0646\u0643 \u0627\u0644\u062c\u0632\u0627\u0626\u0631",
    "\u0633\u0639\u0631 \u0627\u0644\u0635\u0631\u0641",
    "\u0642\u0631\u0627\u0631\u0627\u062a \u0645\u0627\u0644\u064a\u0629",
    "\u0627\u0644\u062a\u0636\u062e\u0645",
    "\u0627\u062d\u062a\u064a\u0627\u0637\u064a \u0627\u0644\u0635\u0631\u0641",
]

BREAKING_SIGNAL_GROUPS = [
    BREAKING_GOVERNANCE_TERMS,
    BREAKING_DEFENSE_TERMS,
    BREAKING_INTERIOR_TERMS,
    BREAKING_WEATHER_TERMS,
    BREAKING_FOREIGN_AFFAIRS_TERMS,
    BREAKING_EDUCATION_TERMS,
    BREAKING_ENERGY_TERMS,
    BREAKING_HUMANITARIAN_TERMS,
    BREAKING_FINANCE_TERMS,
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

LOW_VALUE_EDITORIAL_PATTERNS = [
    r"\bpromo\b",
    r"\bsponsored\b",
    r"\badvertisement\b",
    r"\bcoupon\b",
    r"\bdiscount\b",
    r"\bcasino\b",
    r"\bbetting\b",
    r"اشتر[يى]",
    r"تخفيضات",
    r"عرض خاص",
    r"ممول",
    r"إعلان",
]

LOCAL_SOURCE_KEYWORDS = [
    "algeria", "algérie", "algerie", "dz", "aps", "tsa", "echorouk", "el khabar", "elwatan",
    "الجزائر", "الجزائرية", "الشروق", "الخبر", "النهار", "وكالة الأنباء الجزائرية",
]

NON_LOCAL_SIGNAL_KEYWORDS = [
    "usa",
    "united states",
    "washington",
    "europe",
    "uk",
    "france",
    "germany",
    "india",
    "china",
    "russia",
    "nigeria",
    "pakistan",
    "south korea",
    "democrats",
    "associated press",
    "ap news",
    "reuters",
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
        await self._expire_stale_breaking_flags(db)

        # Pull a wider pool, lock only article rows, then enrich with sources.
        result = await db.execute(
            select(Article)
            .where(Article.status == NewsStatus.NEW)
            .order_by(Article.crawled_at.desc())
            .with_for_update(skip_locked=True)
            .limit(limit * 4)
        )
        articles = result.scalars().all()
        source_ids = {a.source_id for a in articles if a.source_id is not None}
        source_map: dict[int, Source] = {}
        if source_ids:
            source_rows = await db.execute(select(Source).where(Source.id.in_(source_ids)))
            source_map = {s.id: s for s in source_rows.scalars().all()}
        rows = [(a, source_map.get(a.source_id)) for a in articles]
        selected = self._select_articles_for_batch(rows, limit)
        since_commit = 0

        for article, source in selected:
            try:
                await self._classify_article(db, article, source, stats)
                stats["processed"] += 1
                since_commit += 1
                if since_commit >= 50:
                    # Keep long router runs durable and release row locks progressively.
                    await db.commit()
                    since_commit = 0
            except Exception as e:
                logger.error("router_article_error",
                             article_id=article.id,
                             error=str(e))
                article.status = NewsStatus.CLEANED  # Park it
                article.retry_count += 1

        await db.commit()
        logger.info("router_batch_complete", **stats)
        return stats

    async def _expire_stale_breaking_flags(self, db: AsyncSession) -> None:
        """Demote stale breaking flags after configured TTL."""
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

    async def _classify_article(self, db: AsyncSession, article: Article, source: Optional[Source], stats: dict):
        """Classify a single article using rules + AI fallback."""

        text = f"{article.original_title} {article.original_content or ''}"
        text_lower = text.lower()
        has_local_signal = self._has_local_signal(text_lower, article.source_name or "")

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
        if (
            category is None
            and settings.router_skip_ai_for_non_local_aggregator
            and self._is_google_aggregator(article.source_name or "")
            and not has_local_signal
            and urgency != UrgencyLevel.BREAKING
        ):
            category = NewsCategory.INTERNATIONAL

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

                # Guardrail: avoid classifying clearly non-local stories as local_algeria.
                source_name = source.name if source and source.name else (article.source_name or "")
                local_text = f"{article.original_title or ''} {article.original_content or ''}".lower()
                if article.category == NewsCategory.LOCAL_ALGERIA and self._looks_non_local(local_text, source_name):
                    article.category = NewsCategory.INTERNATIONAL

            except Exception as e:
                logger.warning("ai_classification_failed", error=str(e))
                article.category = NewsCategory.LOCAL_ALGERIA
                article.importance_score = 5
        else:
            # Rule-based category was sufficient
            article.category = category
            article.importance_score = self._estimate_importance(text, category, urgency)
            article.urgency = urgency
            if not article.title_ar:
                article.title_ar = article.original_title
            if not article.summary:
                article.summary = (article.original_content or article.original_title)[:300]

            source_name = source.name if source and source.name else (article.source_name or "")
            local_text = f"{article.original_title or ''} {article.original_content or ''}".lower()
            if article.category == NewsCategory.LOCAL_ALGERIA and self._looks_non_local(local_text, source_name):
                article.category = NewsCategory.INTERNATIONAL

        # ── Step 4: Determine if Candidate ──
        quality_ok, quality_reason = self._editorial_quality_gate(article, text_lower, has_local_signal)
        if not quality_ok:
            # Keep Google News items for monitoring, but do not push them to editorial candidates.
            if self._is_google_aggregator(article.source_name or ""):
                article.status = NewsStatus.CLASSIFIED
            else:
                article.status = NewsStatus.ARCHIVED
            article.importance_score = 0
            article.rejection_reason = f"auto_filtered:{quality_reason}"
            return

        is_candidate = (
            article.importance_score >= settings.editorial_min_importance
            or article.is_breaking
            or article.urgency in [UrgencyLevel.HIGH, UrgencyLevel.BREAKING]
        )
        if settings.editorial_require_local_signal and not (article.is_breaking or article.urgency == UrgencyLevel.BREAKING):
            is_candidate = is_candidate and has_local_signal

        # Google News is used as discovery/monitoring input:
        # do not escalate to candidate unless it is clearly local or breaking.
        if (
            self._is_google_aggregator(article.source_name or "")
            and not has_local_signal
            and not article.is_breaking
            and article.urgency != UrgencyLevel.BREAKING
        ):
            is_candidate = False

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
        source_quota = max(1, int(getattr(settings, "router_source_quota", ROUTER_SOURCE_QUOTA)))
        candidate_quota = max(
            1,
            int(getattr(settings, "router_candidate_source_quota", ROUTER_CANDIDATE_SOURCE_QUOTA)),
        )

        for article, source in rows_sorted:
            if len(selected) >= limit:
                break

            source_key = str(source.id) if source and source.id else (article.source_name or "unknown")
            total_count = per_source_total.get(source_key, 0)
            if total_count >= source_quota:
                continue

            text_lower = f"{article.original_title or ''} {article.original_content or ''}".lower()
            source_name = (source.name if source else article.source_name) or ""
            candidate_like = self._has_local_signal(text_lower, source_name)
            if candidate_like and per_source_candidate_like.get(source_key, 0) >= candidate_quota:
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
        min_hits = max(1, int(getattr(settings, "router_rule_min_hits", 2)))
        if scores[best] >= min_hits:
            return best
        return None  # Low confidence → use AI

    def _rule_based_urgency(self, text: str) -> UrgencyLevel:
        """Detect urgency level from newsroom-oriented breaking signals."""
        if not text:
            return UrgencyLevel.LOW

        text_lower = text.lower()

        marker_hits = sum(1 for kw in BREAKING_KEYWORDS if kw in text_lower)
        action_hits = sum(1 for kw in BREAKING_ACTION_TERMS if kw in text_lower)
        event_hits = sum(1 for kw in BREAKING_EVENT_TERMS if kw in text_lower)

        domain_hits = 0
        entity_hits = 0
        for group in BREAKING_SIGNAL_GROUPS:
            group_hits = sum(1 for kw in group if kw in text_lower)
            if group_hits > 0:
                domain_hits += 1
                entity_hits += group_hits

        authority_groups = [
            BREAKING_GOVERNANCE_TERMS,
            BREAKING_DEFENSE_TERMS,
            BREAKING_INTERIOR_TERMS,
            BREAKING_FINANCE_TERMS,
        ]
        authority_hits = sum(
            1 for group in authority_groups if any(kw in text_lower for kw in group)
        )

        score = (
            marker_hits * 3
            + min(action_hits, 4)
            + (min(event_hits, 3) * 2)
            + (domain_hits * 2)
            + (authority_hits * 2)
            + (1 if entity_hits >= 3 else 0)
        )

        # Strong newsroom rule: urgent marker + official/domain signal/action => Breaking.
        if marker_hits >= 1 and (
            domain_hits >= 1 or event_hits >= 1 or action_hits >= 2 or authority_hits >= 1
        ):
            return UrgencyLevel.BREAKING

        # Official authority domain with concrete action => Breaking.
        if authority_hits >= 1 and action_hits >= 1:
            return UrgencyLevel.BREAKING

        # Multi-domain official signal with concrete action => Breaking.
        if domain_hits >= 2 and (action_hits >= 1 or marker_hits >= 1):
            return UrgencyLevel.BREAKING

        # Multiple high-impact incident signals should break immediately.
        if event_hits >= 2:
            return UrgencyLevel.BREAKING

        if score >= 8:
            return UrgencyLevel.BREAKING
        if score >= 3 or marker_hits >= 1 or event_hits >= 1:
            return UrgencyLevel.HIGH

        return UrgencyLevel.MEDIUM

    def _estimate_importance(self, text: str, category: Optional[NewsCategory], urgency: Optional[UrgencyLevel] = None) -> int:
        """Estimate importance score using heuristics."""
        score = 5  # Default

        text_lower = text.lower()

        # Algeria-specific content gets a boost
        algeria_keywords = [
            "\u0627\u0644\u062c\u0632\u0627\u0626\u0631",
            "\u062c\u0632\u0627\u0626\u0631\u064a",
            "algeria",
            "algerie",
            "dz",
        ]
        if any(kw in text_lower for kw in algeria_keywords):
            score += 2

        # Breaking / high urgency boost
        if urgency == UrgencyLevel.BREAKING:
            score += 3
        elif urgency == UrgencyLevel.HIGH:
            score += 2
        elif any(kw in text_lower for kw in BREAKING_KEYWORDS):
            score += 1

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

    def _looks_non_local(self, text_lower: str, source_name: str) -> bool:
        if self._has_local_signal(text_lower, source_name):
            return False
        src = (source_name or "").lower()
        if self._is_google_aggregator(src):
            return True
        return any(k in text_lower for k in NON_LOCAL_SIGNAL_KEYWORDS)

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

        return False, ""

    def _is_arabic_source(self, article: Article, source: Optional[Source]) -> bool:
        src_lang = (source.language if source and source.language else "").lower()
        if src_lang == "ar":
            return True
        source_name = (source.name if source else article.source_name) or ""
        source_name = source_name.lower()
        return any(k in source_name for k in ["عربي", "العربية", "الجزيرة", "سكاي نيوز عربية", "الخبر", "الشروق", "النهار"])

    def _editorial_quality_gate(self, article: Article, text_lower: str, has_local_signal: bool) -> tuple[bool, str]:
        """
        Additional quality gate before pushing to editorial stream.
        """
        if not article.is_breaking and settings.editorial_require_local_signal and not has_local_signal:
            return False, "non_local_editorial_noise"

        for pattern in LOW_VALUE_EDITORIAL_PATTERNS:
            if re.search(pattern, text_lower):
                return False, "promotional_or_ad_noise"

        title = (article.original_title or "").strip()
        if len(title) < 16 and not article.is_breaking:
            return False, "weak_headline"

        return True, ""

    @staticmethod
    def _is_google_aggregator(source_name: str) -> bool:
        source_lower = (source_name or "").lower()
        return "google news" in source_lower or "news.google.com" in source_lower


# Singleton
router_agent = RouterAgent()
