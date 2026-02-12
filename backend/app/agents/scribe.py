"""
Echorouk AI Swarm — Scribe Agent (الوكيل الكاتب)
====================================================
Content Layer: Transforms raw + context into a polished
news article in Echorouk style.

Single Responsibility: Write & Format only.
"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models import Article, NewsStatus
from app.services.ai_service import ai_service
from app.services.cache_service import cache_service

logger = get_logger("agent.scribe")
settings = get_settings()


class ScribeAgent:
    """
    The Scribe Agent — writes and formats news articles.
    Transforms raw data + AI analysis into polished content.
    Only operates on APPROVED articles (cost optimization).
    """

    async def write_article(self, db: AsyncSession, article_id: int) -> dict:
        """Generate a full article for an approved news item."""

        result = await db.execute(
            select(Article).where(Article.id == article_id)
        )
        article = result.scalar_one_or_none()

        if not article:
            return {"error": "Article not found"}

        if article.status != NewsStatus.APPROVED:
            return {"error": f"Article is not approved (status: {article.status})"}
        if article.body_html:
            return {"error": "Article already written"}

        try:
            # Build content from available data
            content = article.original_content or article.summary or article.original_title
            category = article.category.value if article.category else "general"

            # Call AI for rewriting
            result_data = await ai_service.rewrite_article(
                content=content,
                category=category,
                style="echorouk",
            )

            await cache_service.increment_counter("ai_calls_today")

            # Update article
            article.title_ar = result_data.get("headline", article.title_ar)
            article.body_html = result_data.get("body_html", "")
            article.seo_title = result_data.get("seo_title", "")
            article.seo_description = result_data.get("seo_description", "")

            if result_data.get("tags"):
                article.keywords = result_data["tags"]

            article.ai_model_used = "groq/gemini-flash"
            article.updated_at = datetime.utcnow()

            await db.commit()

            logger.info("article_written",
                        article_id=article.id,
                        title=article.title_ar[:60] if article.title_ar else "")

            return {
                "success": True,
                "article_id": article.id,
                "headline": article.title_ar,
                "seo_title": article.seo_title,
            }

        except Exception as e:
            logger.error("scribe_error", article_id=article_id, error=str(e))
            return {"error": str(e)}

    async def batch_write(self, db: AsyncSession, limit: int = 10) -> dict:
        """Batch write all approved articles that don't have body_html yet."""
        stats = {"written": 0, "errors": 0}

        result = await db.execute(
            select(Article)
            .where(
                Article.status == NewsStatus.APPROVED,
                Article.body_html == None,
            )
            .order_by(Article.importance_score.desc())
            .limit(limit)
        )
        articles = result.scalars().all()

        for article in articles:
            result = await self.write_article(db, article.id)
            if "error" in result:
                stats["errors"] += 1
            else:
                stats["written"] += 1

        logger.info("scribe_batch_complete", **stats)
        return stats


# Singleton
scribe_agent = ScribeAgent()
