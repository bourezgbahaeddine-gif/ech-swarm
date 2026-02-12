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
from app.models import Article, NewsStatus, NewsCategory, UrgencyLevel
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


class RouterAgent:
    """
    Router Agent — classifies and routes news articles.
    Rule-based first (free), AI only when uncertain.
    This can reduce AI calls by 50-80%.
    """

    async def process_batch(self, db: AsyncSession, limit: int = 50) -> dict:
        """Process a batch of NEW articles through triage."""
        stats = {"processed": 0, "candidates": 0, "ai_calls": 0, "breaking": 0}

        # Get unprocessed articles
        result = await db.execute(
            select(Article)
            .where(Article.status == NewsStatus.NEW)
            .order_by(Article.crawled_at.desc())
            .with_for_update(skip_locked=True)
            .limit(limit)
        )
        articles = result.scalars().all()

        for article in articles:
            try:
                await self._classify_article(db, article, stats)
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

    async def _classify_article(self, db: AsyncSession, article: Article, stats: dict):
        """Classify a single article using rules + AI fallback."""

        text = f"{article.original_title} {article.original_content or ''}"

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
        is_candidate = (
            article.importance_score >= 5
            or article.is_breaking
            or article.urgency in [UrgencyLevel.HIGH, UrgencyLevel.BREAKING]
        )

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


# Singleton
router_agent = RouterAgent()
