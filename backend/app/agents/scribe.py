"""
Echorouk Editorial OS - Scribe Agent (الوكيل الكاتب)
=================================================
Transforms approved source content into polished editorial drafts.
Single responsibility: writing and formatting only.
"""

from datetime import datetime
import re
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.domain.news.state_machine import can_transition
from app.models import Article, ArticleVector, EditorialDraft, NewsStatus
from app.services.article_index_service import article_index_service
from app.services.ai_service import ai_service
from app.services.cache_service import cache_service
from app.services.embedding_service import embedding_service
from app.services.echorouk_archive_service import echorouk_archive_service

logger = get_logger("agent.scribe")
settings = get_settings()


class ScribeAgent:
    """
    Writes and formats news articles from approved handoffs.
    """

    @staticmethod
    def _new_work_id() -> str:
        return f"WRK-{datetime.utcnow():%Y%m%d}-{uuid4().hex[:10].upper()}"

    @staticmethod
    def _sanitize_generated_html(body_html: str, headline: str) -> str:
        html = (body_html or "").strip()
        if not html:
            return f"<h1>{headline}</h1><p></p>"

        html = re.sub(r"```[\s\S]*?```", "", html)
        html = re.sub(r"<!--\s*wp:[\s\S]*?-->", "", html, flags=re.IGNORECASE)
        html = re.sub(r"<!--\s*/wp:[\s\S]*?-->", "", html, flags=re.IGNORECASE)
        html = re.sub(r"<!--[\s\S]*?-->", "", html)
        html = re.sub(r"<script[\s\S]*?</script>", "", html, flags=re.IGNORECASE)
        html = re.sub(r"<style[\s\S]*?</style>", "", html, flags=re.IGNORECASE)

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

    @staticmethod
    def _route_urgency(article: Article) -> str:
        if bool(getattr(article, "is_breaking", False)):
            return "high"
        raw = str(getattr(article, "urgency", "") or "").strip().lower()
        if raw in {"high", "breaking", "critical", "urgent"}:
            return "high"
        if raw in {"low"}:
            return "low"
        return "normal"

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
            content = article.original_content or article.summary or article.original_title
            category = article.category.value if article.category else "general"
            support_articles = await self._retrieve_supporting_articles(db, article, content)
            context_block = self._format_supporting_context(support_articles)
            content_with_context = f"{context_block}\n\n{content}" if context_block else content

            result_data = await ai_service.rewrite_article(
                content=content_with_context,
                category=category,
                style="echorouk",
                route_context={"queue_name": "ai_scribe", "urgency": self._route_urgency(article)},
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
            if not can_transition(article.status, NewsStatus.DRAFT_GENERATED):
                return {"error": f"Invalid transition to draft_generated from {article.status.value}"}
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

            logger.info(
                "scribe_draft_generated",
                article_id=article.id,
                work_id=draft.work_id,
                version=draft.version,
                supporting_context=len(support_articles),
            )

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

    async def _retrieve_supporting_articles(
        self,
        db: AsyncSession,
        article: Article,
        text: str,
        limit: int = 3,
    ) -> list[dict]:
        if not text:
            return []

        query_vec, _ = await embedding_service.embed_query(text[:1200])
        stmt = (
            select(
                Article.id,
                Article.title_ar,
                Article.original_title,
                Article.summary,
                Article.source_name,
                Article.original_url,
                Article.category,
                ArticleVector.embedding.cosine_distance(query_vec).label("dist"),
            )
            .join(ArticleVector, ArticleVector.article_id == Article.id)
            .where(
                ArticleVector.vector_type == "summary",
                Article.status != NewsStatus.ARCHIVED,
                Article.id != article.id,
            )
            .order_by(ArticleVector.embedding.cosine_distance(query_vec))
            .limit(limit * 4)
        )
        rows = await db.execute(stmt)
        candidates = {}
        for row in rows.fetchall():
            article_row = row._mapping
            aid = int(article_row["id"])
            if aid in candidates:
                continue
            candidates[aid] = {
                "id": aid,
                "title": article_row["title_ar"] or article_row["original_title"],
                "summary": article_row["summary"] or "",
                "source": article_row["source_name"],
                "url": article_row["original_url"],
                "category": article_row["category"],
            }
            if len(candidates) >= limit:
                break
        items = list(candidates.values())
        if settings.echorouk_archive_rag_enabled:
            query_seed = "\n".join(
                part
                for part in [
                    article.title_ar or article.original_title or "",
                    article.summary or "",
                    text[:600] if text else "",
                ]
                if part
            ).strip()
            archive_refs = await echorouk_archive_service.semantic_search(
                db,
                q=query_seed or text[:1200],
                limit=max(1, int(settings.echorouk_archive_rag_limit)),
            )
            min_score = float(getattr(settings, "echorouk_archive_rag_min_score", 0.0))
            if min_score > 0:
                archive_refs = [ref for ref in archive_refs if float(ref.get("score") or 0.0) >= min_score]
            if getattr(settings, "echorouk_archive_rag_prefer_category_match", False) and article.category:
                target_category = article.category.value
                matching = [ref for ref in archive_refs if ref.get("category") == target_category]
                if matching:
                    archive_refs = matching
            seen_urls = {str(item.get("url") or "") for item in items}
            for ref in archive_refs:
                url = str(ref.get("url") or "")
                if url and url in seen_urls:
                    continue
                items.append(
                    {
                        "id": ref.get("id"),
                        "title": ref.get("title"),
                        "summary": ref.get("summary") or "",
                        "source": ref.get("source_name") or "archive",
                        "url": url,
                        "category": ref.get("category"),
                        "corpus": ref.get("corpus") or "archive",
                    }
                )
                if url:
                    seen_urls.add(url)
        return items[: limit + max(0, int(settings.echorouk_archive_rag_limit if settings.echorouk_archive_rag_enabled else 0))]

    @staticmethod
    def _format_supporting_context(articles: list[dict]) -> str:
        if not articles:
            return ""
        lines = ["Supporting context:"]
        for idx, art in enumerate(articles, start=1):
            summary = art["summary"][:200].strip()
            title = art["title"] or "untitled"
            source = art["source"] or "publisher"
            url = art["url"] or ""
            corpus = art.get("corpus")
            prefix = f"[{corpus}] " if corpus else ""
            lines.append(f"{idx}. {prefix}{title} ({source}) - {url}")
            if summary:
                lines.append(f"   {summary}")
        return "\n".join(lines)

    async def batch_write(self, db: AsyncSession, limit: int = 10) -> dict:
        """Batch write all approved articles that do not have generated drafts."""
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


scribe_agent = ScribeAgent()
