from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import async_session
from app.core.logging import get_logger
from app.models.news import Article, EditorialDraft, NewsCategory, NewsStatus
from app.models.script import ScriptOutput, ScriptOutputFormat, ScriptProject, ScriptProjectStatus, ScriptProjectType
from app.models.story import Story
from app.repositories.script_repository import script_repository
from app.services.ai_service import ai_service

logger = get_logger("services.script_studio")

_BULLETIN_ALLOWED_STATUSES = {
    NewsStatus.APPROVED,
    NewsStatus.APPROVED_HANDOFF,
    NewsStatus.DRAFT_GENERATED,
    NewsStatus.READY_FOR_CHIEF_APPROVAL,
    NewsStatus.APPROVAL_REQUEST_WITH_RESERVATIONS,
    NewsStatus.READY_FOR_MANUAL_PUBLISH,
    NewsStatus.PUBLISHED,
}

_SENSATIONAL_TERMS = [
    "صدمة",
    "كارثة",
    "فضيحة",
    "لا يصدق",
    "شاهد",
    "urgent",
    "shocking",
    "you won't believe",
    "incroyable",
]


def _safe_article_title(article: Article) -> str:
    return (article.title_ar or article.original_title or "").strip() or f"Article #{article.id}"


def _parse_category(value: str | None) -> NewsCategory | None:
    if not value:
        return None
    normalized = value.strip().lower()
    if not normalized or normalized == "all":
        return None
    try:
        return NewsCategory(normalized)
    except ValueError:
        return None


def _to_word_count(text: str) -> int:
    return len(re.findall(r"\S+", text or ""))


class ScriptStudioService:
    async def select_bulletin_articles(
        self,
        db: AsyncSession,
        *,
        since: datetime,
        geo: str = "ALL",
        category: str = "all",
        desks: list[str] | None = None,
        max_items: int = 10,
    ) -> list[Article]:
        stmt = (
            select(Article)
            .where(
                Article.status.in_(tuple(_BULLETIN_ALLOWED_STATUSES)),
                or_(Article.created_at >= since, Article.updated_at >= since),
            )
            .order_by(desc(Article.importance_score), desc(Article.updated_at), desc(Article.id))
            .limit(max(1, min(max_items, 30)))
        )

        geo_upper = (geo or "ALL").strip().upper()
        if geo_upper == "DZ":
            stmt = stmt.where(Article.category == NewsCategory.LOCAL_ALGERIA)
        elif geo_upper in {"WORLD", "INTL", "INTERNATIONAL"}:
            stmt = stmt.where(
                or_(
                    Article.category.is_(None),
                    Article.category != NewsCategory.LOCAL_ALGERIA,
                )
            )

        category_enum = _parse_category(category)
        if category_enum is not None:
            stmt = stmt.where(Article.category == category_enum)

        desk_enums = [_parse_category(value) for value in (desks or [])]
        desk_enums = [value for value in desk_enums if value is not None]
        if desk_enums:
            stmt = stmt.where(Article.category.in_(desk_enums))

        rows = await db.execute(stmt)
        return list(rows.scalars().all())

    async def build_input_context(self, db: AsyncSession, project: ScriptProject) -> dict[str, Any]:
        params = project.params_json if isinstance(project.params_json, dict) else {}
        if project.article_id:
            article = await db.get(Article, project.article_id)
            if not article:
                raise RuntimeError("script_source_article_not_found")
            return {
                "scope": "article",
                "project_id": project.id,
                "article": self._article_to_context(article),
                "params": params,
            }

        if project.story_id:
            story_row = await db.execute(
                select(Story)
                .options(selectinload(Story.items))
                .where(Story.id == project.story_id)
            )
            story = story_row.scalar_one_or_none()
            if not story:
                raise RuntimeError("script_source_story_not_found")

            article_ids = [item.article_id for item in (story.items or []) if item.article_id]
            draft_ids = [item.draft_id for item in (story.items or []) if item.draft_id]

            article_map: dict[int, Article] = {}
            draft_map: dict[int, EditorialDraft] = {}

            if article_ids:
                article_rows = await db.execute(select(Article).where(Article.id.in_(article_ids)))
                article_map = {row.id: row for row in article_rows.scalars().all()}
            if draft_ids:
                draft_rows = await db.execute(select(EditorialDraft).where(EditorialDraft.id.in_(draft_ids)))
                draft_map = {row.id: row for row in draft_rows.scalars().all()}

            timeline: list[dict[str, Any]] = []
            for item in (story.items or []):
                if item.article_id and item.article_id in article_map:
                    article = article_map[item.article_id]
                    timeline.append(
                        {
                            "type": "article",
                            "id": article.id,
                            "title": _safe_article_title(article),
                            "summary": (article.summary or "").strip(),
                            "source_name": article.source_name,
                            "url": article.original_url,
                            "status": article.status.value if article.status else None,
                            "created_at": article.created_at.isoformat() if article.created_at else None,
                        }
                    )
                elif item.draft_id and item.draft_id in draft_map:
                    draft = draft_map[item.draft_id]
                    timeline.append(
                        {
                            "type": "draft",
                            "id": draft.id,
                            "title": (draft.title or "Draft").strip(),
                            "summary": (draft.note or "").strip(),
                            "work_id": draft.work_id,
                            "status": draft.status,
                            "created_at": draft.created_at.isoformat() if draft.created_at else None,
                        }
                    )

            timeline.sort(key=lambda row: row.get("created_at") or "", reverse=True)
            return {
                "scope": "story",
                "project_id": project.id,
                "story": {
                    "id": story.id,
                    "story_key": story.story_key,
                    "title": story.title,
                    "summary": story.summary,
                    "category": story.category,
                    "geography": story.geography,
                    "status": story.status.value if story.status else None,
                },
                "timeline": timeline[:25],
                "params": params,
            }

        selected_article_ids = [int(value) for value in params.get("selected_article_ids", []) if str(value).isdigit()]
        articles: list[Article] = []
        if selected_article_ids:
            rows = await db.execute(
                select(Article)
                .where(Article.id.in_(selected_article_ids))
                .order_by(desc(Article.importance_score), desc(Article.updated_at), desc(Article.id))
            )
            articles = list(rows.scalars().all())

        if not articles:
            period_hours = int(params.get("period_hours") or 24)
            articles = await self.select_bulletin_articles(
                db,
                since=datetime.utcnow() - timedelta(hours=max(1, period_hours)),
                geo=str(params.get("geo") or "ALL"),
                category=str(params.get("category") or "all"),
                desks=[str(v) for v in (params.get("desks") or [])],
                max_items=int(params.get("max_items") or 10),
            )

        return {
            "scope": "bulletin",
            "project_id": project.id,
            "items": [self._article_to_context(article) for article in articles],
            "params": params,
        }

    def _article_to_context(self, article: Article) -> dict[str, Any]:
        return {
            "id": article.id,
            "title": _safe_article_title(article),
            "summary": (article.summary or "").strip(),
            "body": (article.original_content or article.body_html or "").strip()[:8000],
            "source_name": article.source_name,
            "url": article.original_url,
            "status": article.status.value if article.status else None,
            "category": article.category.value if article.category else None,
            "importance_score": article.importance_score,
            "entities": article.entities if isinstance(article.entities, list) else [],
            "keywords": article.keywords if isinstance(article.keywords, list) else [],
            "created_at": article.created_at.isoformat() if article.created_at else None,
            "updated_at": article.updated_at.isoformat() if article.updated_at else None,
        }

    async def generate_project_output(
        self,
        *,
        script_id: int,
        target_version: int,
        actor_username: str | None,
    ) -> dict[str, Any]:
        actor_value = actor_username or "system"

        async with async_session() as db:
            project = await script_repository.get_project_by_id(db, script_id)
            if not project:
                raise RuntimeError("script_project_not_found")
            project.status = ScriptProjectStatus.generating
            project.updated_by = actor_value
            await db.commit()

        try:
            async with async_session() as db:
                project = await script_repository.get_project_by_id(db, script_id)
                if not project:
                    raise RuntimeError("script_project_not_found")

                existing_output_row = await db.execute(
                    select(ScriptOutput).where(ScriptOutput.script_id == script_id, ScriptOutput.version == target_version)
                )
                existing_output = existing_output_row.scalar_one_or_none()
                if existing_output:
                    project.status = ScriptProjectStatus.ready_for_review
                    project.updated_by = actor_value
                    await db.commit()
                    return {
                        "script_id": script_id,
                        "status": project.status.value,
                        "version": existing_output.version,
                        "reused": True,
                    }

                context = await self.build_input_context(db, project)
                output_json = await self._generate_output_json(
                    project_type=project.type,
                    context=context,
                    params=project.params_json if isinstance(project.params_json, dict) else {},
                )
                quality = self.run_quality_gates(
                    project_type=project.type,
                    output_json=output_json,
                    params=project.params_json if isinstance(project.params_json, dict) else {},
                )

                created_output = await script_repository.create_output(
                    db,
                    script_id=script_id,
                    version=target_version,
                    content_json=output_json,
                    content_text=self._render_text_output(project.type, output_json),
                    output_format=ScriptOutputFormat.json,
                    quality_issues_json=quality["issues"],
                )
                project.status = ScriptProjectStatus.ready_for_review
                project.updated_by = actor_value
                await db.commit()

                return {
                    "script_id": script_id,
                    "status": project.status.value,
                    "version": created_output.version,
                    "quality_passed": quality["passed"],
                    "issues_count": len(quality["issues"]),
                    "reused": False,
                }
        except Exception:
            logger.exception("script_generation_failed", script_id=script_id)
            async with async_session() as db:
                project = await script_repository.get_project_by_id(db, script_id)
                if project:
                    project.status = ScriptProjectStatus.generating
                    project.updated_by = actor_value
                    await db.commit()
            raise

    async def _generate_output_json(
        self,
        *,
        project_type: ScriptProjectType,
        context: dict[str, Any],
        params: dict[str, Any],
    ) -> dict[str, Any]:
        language = str(params.get("language") or "ar")
        tone = str(params.get("tone") or "neutral")
        prompt = self._build_generation_prompt(project_type=project_type, context=context, language=language, tone=tone)
        generated = await ai_service.generate_json(prompt)
        if not isinstance(generated, dict) or not generated:
            return self._fallback_output(project_type=project_type, context=context, params=params)
        return self._normalize_output(project_type=project_type, output=generated, context=context, params=params)

    def _build_generation_prompt(
        self,
        *,
        project_type: ScriptProjectType,
        context: dict[str, Any],
        language: str,
        tone: str,
    ) -> str:
        schemas = {
            ScriptProjectType.story_script: {
                "hook": "string",
                "context": "string",
                "what_happened": "string",
                "why_it_matters": "string",
                "known_unknown": "string",
                "quotes": [{"text": "string", "source": "string"}],
                "timeline": [{"time": "string", "event": "string"}],
                "close": "string",
                "social_short": "string",
                "anchor_notes": "string",
            },
            ScriptProjectType.video_script: {
                "vo_script": "string",
                "scenes": [{"idx": 1, "duration_s": 12, "visual": "string", "on_screen_text": "string", "vo_line": "string"}],
                "captions_srt": "string",
                "assets_list": [{"type": "archive|photo|broll", "hint": "string"}],
                "thumbnail_ideas": ["string"],
            },
            ScriptProjectType.bulletin_daily: {
                "opening": "string",
                "headlines": ["string"],
                "segments": [{"title": "string", "vo": "string", "duration_s": 25}],
                "transitions": ["string"],
                "closing": "string",
                "social_summary": "string",
            },
            ScriptProjectType.bulletin_weekly: {
                "opening": "string",
                "headlines": ["string"],
                "segments": [{"title": "string", "vo": "string", "duration_s": 25}],
                "transitions": ["string"],
                "closing": "string",
                "social_summary": "string",
            },
        }
        schema = schemas[project_type]
        return (
            "You are a newsroom script producer.\n"
            f"Output language: {language}\n"
            f"Tone: {tone}\n"
            "Return ONLY valid JSON object. No markdown, no code block.\n"
            f"Required schema:\n{json.dumps(schema, ensure_ascii=False)}\n\n"
            f"Context:\n{json.dumps(context, ensure_ascii=False)}"
        )

    def _normalize_output(
        self,
        *,
        project_type: ScriptProjectType,
        output: dict[str, Any],
        context: dict[str, Any],
        params: dict[str, Any],
    ) -> dict[str, Any]:
        fallback = self._fallback_output(project_type=project_type, context=context, params=params)
        normalized = dict(fallback)
        for key in fallback.keys():
            if key in output and output[key] not in (None, ""):
                normalized[key] = output[key]
        return normalized

    def _fallback_output(
        self,
        *,
        project_type: ScriptProjectType,
        context: dict[str, Any],
        params: dict[str, Any],
    ) -> dict[str, Any]:
        tone = str(params.get("tone") or "neutral")
        if project_type == ScriptProjectType.story_script:
            article = context.get("article") or {}
            title = article.get("title") or context.get("story", {}).get("title") or "News update"
            summary = article.get("summary") or context.get("story", {}).get("summary") or ""
            return {
                "hook": title,
                "context": summary or f"Brief context about {title}.",
                "what_happened": summary or "Details were collected from newsroom sources.",
                "why_it_matters": "The development may influence public-facing decisions and coverage priorities.",
                "known_unknown": "Some details are still being verified by the editorial desk.",
                "quotes": [],
                "timeline": [],
                "close": "Editors will continue verification before publishing final narrative.",
                "social_short": f"{title} - update in progress.",
                "anchor_notes": f"Tone={tone}. Keep language factual and avoid unverified claims.",
            }

        if project_type == ScriptProjectType.video_script:
            article = context.get("article") or {}
            title = article.get("title") or context.get("story", {}).get("title") or "Video package"
            vo_line = article.get("summary") or f"Newsroom summary for {title}."
            return {
                "vo_script": f"{title}. {vo_line}",
                "scenes": [
                    {
                        "idx": 1,
                        "duration_s": int(params.get("length_seconds") or 45),
                        "visual": "Anchor shot with relevant headline card",
                        "on_screen_text": title,
                        "vo_line": vo_line,
                    }
                ],
                "captions_srt": "1\n00:00:00,000 --> 00:00:05,000\n" + title,
                "assets_list": [{"type": "archive", "hint": "Use related newsroom photo/video archive"}],
                "thumbnail_ideas": [title],
            }

        items = context.get("items") or []
        headlines = [str(item.get("title") or "").strip() for item in items[:8] if str(item.get("title") or "").strip()]
        segments = [
            {
                "title": headline,
                "vo": f"Update: {headline}",
                "duration_s": max(20, int((int(params.get('duration_minutes') or 5) * 60) / max(1, len(headlines) or 1))),
            }
            for headline in headlines
        ]
        return {
            "opening": "Here is your newsroom bulletin summary.",
            "headlines": headlines,
            "segments": segments,
            "transitions": ["Next update." for _ in range(max(0, len(segments) - 1))],
            "closing": "End of bulletin. Await editorial approval before publication.",
            "social_summary": "Top verified updates prepared for editorial review.",
        }

    def run_quality_gates(
        self,
        *,
        project_type: ScriptProjectType,
        output_json: dict[str, Any],
        params: dict[str, Any],
    ) -> dict[str, Any]:
        required_sections = {
            ScriptProjectType.story_script: [
                "hook",
                "context",
                "what_happened",
                "why_it_matters",
                "known_unknown",
                "quotes",
                "timeline",
                "close",
                "social_short",
                "anchor_notes",
            ],
            ScriptProjectType.video_script: ["vo_script", "scenes", "captions_srt", "assets_list", "thumbnail_ideas"],
            ScriptProjectType.bulletin_daily: ["opening", "headlines", "segments", "transitions", "closing", "social_summary"],
            ScriptProjectType.bulletin_weekly: ["opening", "headlines", "segments", "transitions", "closing", "social_summary"],
        }

        issues: list[dict[str, Any]] = []

        for section in required_sections[project_type]:
            value = output_json.get(section)
            if value in (None, "", [], {}):
                issues.append(
                    {
                        "code": f"missing_{section}",
                        "message": f"Required section `{section}` is missing or empty.",
                        "severity": "blocker",
                    }
                )

        if project_type == ScriptProjectType.story_script:
            for index, quote in enumerate(output_json.get("quotes") or []):
                if not isinstance(quote, dict):
                    issues.append(
                        {
                            "code": "invalid_quote_shape",
                            "message": f"Quote #{index + 1} must be an object.",
                            "severity": "warn",
                        }
                    )
                    continue
                text = str(quote.get("text") or "").strip()
                source = str(quote.get("source") or "").strip()
                if text and not source:
                    issues.append(
                        {
                            "code": "quote_without_source",
                            "message": f"Quote #{index + 1} has text but no source.",
                            "severity": "blocker",
                        }
                    )

            words = _to_word_count(
                " ".join(
                    str(output_json.get(key) or "")
                    for key in ["hook", "context", "what_happened", "why_it_matters", "close", "social_short"]
                )
            )
            if words < 80:
                issues.append(
                    {
                        "code": "script_too_short",
                        "message": "Story script is too short for newsroom use.",
                        "severity": "warn",
                        "details": {"words": words},
                    }
                )

        if project_type == ScriptProjectType.video_script:
            scenes = output_json.get("scenes") or []
            if isinstance(scenes, list):
                total_duration = 0
                for scene in scenes:
                    if not isinstance(scene, dict):
                        continue
                    total_duration += int(scene.get("duration_s") or 0)
                expected_duration = int(params.get("length_seconds") or 60)
                if total_duration <= 0:
                    issues.append(
                        {
                            "code": "video_no_duration",
                            "message": "Video scenes do not include valid durations.",
                            "severity": "blocker",
                        }
                    )
                elif total_duration > expected_duration * 2:
                    issues.append(
                        {
                            "code": "video_duration_excess",
                            "message": "Scene durations exceed requested length by a large margin.",
                            "severity": "warn",
                            "details": {"total_duration": total_duration, "expected": expected_duration},
                        }
                    )

        if project_type in {ScriptProjectType.bulletin_daily, ScriptProjectType.bulletin_weekly}:
            segments = output_json.get("segments") or []
            if len(segments) == 0:
                issues.append(
                    {
                        "code": "bulletin_empty_segments",
                        "message": "Bulletin has no segments.",
                        "severity": "blocker",
                    }
                )

        text_blob = json.dumps(output_json, ensure_ascii=False).lower()
        sensational_hits = [term for term in _SENSATIONAL_TERMS if term in text_blob]
        if sensational_hits:
            issues.append(
                {
                    "code": "neutrality_lint",
                    "message": "Potential sensational terms detected. Review tone.",
                    "severity": "warn",
                    "details": {"hits": sensational_hits[:6]},
                }
            )

        passed = not any(issue.get("severity") == "blocker" for issue in issues)
        return {"passed": passed, "issues": issues}

    def _render_text_output(self, project_type: ScriptProjectType, output_json: dict[str, Any]) -> str:
        if project_type == ScriptProjectType.video_script:
            return str(output_json.get("vo_script") or "").strip()
        if project_type in {ScriptProjectType.bulletin_daily, ScriptProjectType.bulletin_weekly}:
            opening = str(output_json.get("opening") or "").strip()
            segments = output_json.get("segments") or []
            segment_lines = []
            for segment in segments:
                if isinstance(segment, dict):
                    segment_lines.append(f"- {segment.get('title')}: {segment.get('vo')}")
            closing = str(output_json.get("closing") or "").strip()
            return "\n".join([opening, *segment_lines, closing]).strip()
        return "\n".join(
            [
                str(output_json.get("hook") or "").strip(),
                str(output_json.get("what_happened") or "").strip(),
                str(output_json.get("why_it_matters") or "").strip(),
                str(output_json.get("close") or "").strip(),
            ]
        ).strip()


script_studio_service = ScriptStudioService()
