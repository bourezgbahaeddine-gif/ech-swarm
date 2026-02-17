"""
Echorouk AI Swarm — Scribe Agent (الوكيل الكاتب)
====================================================
Content Layer: Transforms raw + context into a polished
news article in Echorouk style.

Single Responsibility: Write & Format only.
"""

from datetime import datetime
import re
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models import Article, EditorialDraft, NewsStatus
from app.services.article_index_service import article_index_service
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

    @staticmethod
    def _new_work_id() -> str:
        return f"WRK-{datetime.utcnow():%Y%m%d}-{uuid4().hex[:10].upper()}"

    @staticmethod
    def _sanitize_generated_html(body_html: str, headline: str) -> str:
        html = (body_html or "").strip()
        if not html:
            return f"<h1>{headline}</h1><p></p>"

        # Remove markdown fences and WordPress/Gutenberg comments.
        html = re.sub(r"```[\s\S]*?```", "", html)
        html = re.sub(r"<!--\s*wp:[\s\S]*?-->", "", html, flags=re.IGNORECASE)
        html = re.sub(r"<!--\s*/wp:[\s\S]*?-->", "", html, flags=re.IGNORECASE)
        html = re.sub(r"<!--[\s\S]*?-->", "", html)
        html = re.sub(r"<script[\s\S]*?</script>", "", html, flags=re.IGNORECASE)
        html = re.sub(r"<style[\s\S]*?</style>", "", html, flags=re.IGNORECASE)

        # Remove side-comment lines and prompt-template leftovers.
        html = re.sub(r"(?im)^(note|ملاحظة|explanation|comment|output)\s*:\s*.*$", "", html)
        html = re.sub(r"\[[^\]\n]{2,160}\]", "", html)
        html = re.sub(r"\?{3,}", "", html)
        html = re.sub(r"(?im)^\s*[-*]\s+", "", html)
        html = re.sub(r"\n{3,}", "\n\n", html).strip()

        if "<h1" not in html.lower():
            html = f"<h1>{headline}</h1>\n{html}"

        has_internal_link = bool(
            re.search(r'href\s*=\s*["\'](?:/|https?://(?:www\.)?echoroukonline\.com)', html, flags=re.IGNORECASE)
        )
        if not has_internal_link:
            html += '\n<p>للمزيد تابع آخر المستجدات عبر <a href="/news">قسم الأخبار</a>.</p>'

        return html.strip()

    async def write_article(
        self,
        db: AsyncSession,
        article_id: int,
        source_action: str = "approved_handoff",
        fixed_work_id: str | None = None,
    ) -> dict:
        """Generate an editorial draft from an approved handoff."""

        result = await db.execute(
            select(Article).where(Article.id == article_id)
        )
        article = result.scalar_one_or_none()

        if not article:
            return {"error": "Article not found"}

        if article.status not in [NewsStatus.APPROVED, NewsStatus.APPROVED_HANDOFF, NewsStatus.DRAFT_GENERATED]:
            return {"error": f"Article is not in writable state (status: {article.status})"}

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

            generated_title = result_data.get("headline", article.title_ar) or article.original_title
            generated_body = result_data.get("body_html", "") or content
            generated_seo_title = result_data.get("seo_title", "") or generated_title
            generated_seo_description = result_data.get("seo_description", "") or (article.summary or "")
            generated_body = self._sanitize_generated_html(generated_body, generated_title)

            if result_data.get("tags"):
                article.keywords = result_data["tags"]

            article.ai_model_used = "groq/gemini-flash"
            article.title_ar = generated_title
            article.seo_title = generated_seo_title
            article.seo_description = generated_seo_description
            article.status = NewsStatus.DRAFT_GENERATED
            article.updated_at = datetime.utcnow()

            if fixed_work_id:
                version_stmt = (
                    select(func.coalesce(func.max(EditorialDraft.version), 0))
                    .where(EditorialDraft.work_id == fixed_work_id)
                )
            else:
                version_stmt = (
                    select(func.coalesce(func.max(EditorialDraft.version), 0))
                    .where(
                        EditorialDraft.article_id == article.id,
                        EditorialDraft.source_action == source_action,
                    )
                )
            version_result = await db.execute(version_stmt)
            next_version = int(version_result.scalar_one() or 0) + 1

            draft = EditorialDraft(
                article_id=article.id,
                work_id=fixed_work_id or self._new_work_id(),
                source_action=source_action,
                change_origin="regenerate" if fixed_work_id else "ai_suggestion",
                title=generated_title,
                body=generated_body,
                note="auto_from_scribe_v2",
                status="draft",
                version=next_version,
                created_by="Scribe Agent",
                updated_by="Scribe Agent",
            )
            db.add(draft)
            await article_index_service.upsert_article(db, article)

            await db.commit()
            await db.refresh(draft)

            logger.info("scribe_draft_generated",
                        article_id=article.id,
                        work_id=draft.work_id,
                        version=draft.version)

            return {
                "success": True,
                "article_id": article.id,
                "headline": generated_title,
                "seo_title": generated_seo_title,
                "draft_id": draft.id,
                "work_id": draft.work_id,
                "version": draft.version,
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
                Article.status.in_([NewsStatus.APPROVED_HANDOFF, NewsStatus.APPROVED]),
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
