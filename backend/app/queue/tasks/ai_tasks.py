"""AI-heavy editorial tasks executed by Celery workers."""

from __future__ import annotations

import traceback
from datetime import datetime
from uuid import UUID

import structlog
from celery import Task
from sqlalchemy import desc, func, select

from app.core.database import async_session
from app.core.logging import get_logger
from app.models import Article, EditorialDraft, JobRun
from app.queue.async_runtime import run_async
from app.queue.celery_app import celery_app
from app.services.job_queue_service import job_queue_service
from app.services.link_intelligence_service import link_intelligence_service
from app.services.quality_gate_service import quality_gate_service
from app.services.smart_editor_service import smart_editor_service

logger = get_logger("queue.ai_tasks")


async def _latest_draft_or_none(work_id: str) -> EditorialDraft | None:
    async with async_session() as db:
        row = await db.execute(
            select(EditorialDraft)
            .where(EditorialDraft.work_id == work_id, EditorialDraft.status == "draft")
            .order_by(desc(EditorialDraft.version))
            .limit(1)
        )
        return row.scalar_one_or_none()


async def _create_draft_version(
    *,
    latest: EditorialDraft,
    title: str | None,
    body: str,
    note: str | None,
    updated_by: str,
    change_origin: str = "ai_suggestion",
) -> dict:
    async with async_session() as db:
        latest_db = await db.get(EditorialDraft, latest.id)
        if not latest_db:
            raise RuntimeError("draft_not_found")
        version_result = await db.execute(
            select(func.coalesce(func.max(EditorialDraft.version), 0)).where(EditorialDraft.work_id == latest_db.work_id)
        )
        next_version = int(version_result.scalar_one() or 0) + 1
        new_draft = EditorialDraft(
            article_id=latest_db.article_id,
            work_id=latest_db.work_id,
            source_action=latest_db.source_action,
            parent_draft_id=latest_db.id,
            change_origin=change_origin,
            title=title if title is not None else latest_db.title,
            body=smart_editor_service.sanitize_html(body),
            note=note or latest_db.note,
            status="draft",
            version=next_version,
            created_by=latest_db.created_by or updated_by,
            updated_by=updated_by,
        )
        db.add(new_draft)
        await db.commit()
        await db.refresh(new_draft)
        return {
            "id": new_draft.id,
            "work_id": new_draft.work_id,
            "version": new_draft.version,
            "title": new_draft.title,
            "note": new_draft.note,
        }


async def _load_job(job_id: str) -> JobRun | None:
    async with async_session() as db:
        row = await db.execute(select(JobRun).where(JobRun.id == UUID(job_id)))
        return row.scalar_one_or_none()


async def _mark_running(job_id: str) -> JobRun:
    async with async_session() as db:
        row = await db.execute(select(JobRun).where(JobRun.id == UUID(job_id)))
        job = row.scalar_one_or_none()
        if not job:
            raise RuntimeError("job_not_found")
        await job_queue_service.mark_running(db, job)
        structlog.contextvars.bind_contextvars(
            job_id=job_id,
            request_id=job.request_id or "",
            correlation_id=job.correlation_id or "",
            job_type=job.job_type,
            queue_name=job.queue_name,
        )
        return job


async def _mark_completed(job_id: str, result: dict) -> None:
    async with async_session() as db:
        row = await db.execute(select(JobRun).where(JobRun.id == UUID(job_id)))
        job = row.scalar_one_or_none()
        if not job:
            return
        await job_queue_service.mark_completed(db, job, result)


async def _mark_failed_or_dlq(job_id: str, error: str, tb: str, is_final: bool) -> None:
    async with async_session() as db:
        row = await db.execute(select(JobRun).where(JobRun.id == UUID(job_id)))
        job = row.scalar_one_or_none()
        if not job:
            return
        if is_final:
            await job_queue_service.dead_letter(db, job=job, error=error, traceback_text=tb)
        else:
            await job_queue_service.mark_failed(db, job, error)


async def _execute_editorial_ai_job(job_id: str) -> dict:
    job = await _mark_running(job_id)
    payload = job.payload_json or {}
    op = str(payload.get("operation") or "")
    work_id = str(payload.get("work_id") or "")
    if not op or not work_id:
        raise RuntimeError("invalid_job_payload")

    latest = await _latest_draft_or_none(work_id)
    if not latest:
        raise RuntimeError("draft_not_found")

    async with async_session() as db:
        article_row = await db.execute(select(Article).where(Article.id == latest.article_id))
        article = article_row.scalar_one_or_none()
        if not article:
            raise RuntimeError("article_not_found")

        source_text = "\n".join([article.original_title or "", article.summary or "", article.original_content or ""]).strip()
        draft_title = latest.title or article.title_ar or article.original_title
        draft_html = latest.body or ""

        if op == "rewrite":
            suggestion = await smart_editor_service.rewrite_suggestion(
                source_text=source_text,
                draft_title=draft_title,
                draft_html=draft_html,
                mode=str(payload.get("mode") or "formal"),
                instruction=str(payload.get("instruction") or ""),
            )
            return {"work_id": work_id, "base_version": latest.version, "tool": "rewrite", "suggestion": suggestion}

        if op == "headlines":
            count = max(1, min(int(payload.get("count", 5)), 10))
            suggestions = await smart_editor_service.headline_suggestions(source_text=source_text, draft_title=draft_title)
            return {"work_id": work_id, "base_version": latest.version, "headlines": suggestions[:count]}

        if op == "seo":
            result = await smart_editor_service.seo_suggestions(source_text=source_text, draft_title=draft_title, draft_html=draft_html)
            return {"work_id": work_id, "base_version": latest.version, **result}

        if op == "social":
            variants = await smart_editor_service.social_variants(source_text=source_text, draft_title=draft_title, draft_html=draft_html)
            await quality_gate_service.save_report(
                db,
                article_id=article.id,
                stage="SOCIAL_VARIANTS",
                passed=True,
                score=100,
                blocking_reasons=[],
                actionable_fixes=[],
                report_json={"variants": variants, "work_id": work_id, "version": latest.version},
                created_by=job.actor_username or "worker",
                upsert_by_stage=True,
            )
            await db.commit()
            return {"work_id": work_id, "base_version": latest.version, "variants": variants}

        if op == "claims":
            threshold = float(payload.get("threshold", 0.70))
            report = smart_editor_service.fact_check_report(
                text=smart_editor_service.html_to_text(draft_html),
                source_url=article.original_url,
                threshold=threshold,
            )
            await quality_gate_service.save_report(
                db,
                article_id=article.id,
                stage="FACT_CHECK",
                passed=bool(report["passed"]),
                score=report.get("score"),
                blocking_reasons=report.get("blocking_reasons", []),
                actionable_fixes=report.get("actionable_fixes", []),
                report_json=report,
                created_by=job.actor_username or "worker",
                upsert_by_stage=True,
            )
            await db.commit()
            return report

        if op == "quality":
            report = smart_editor_service.quality_score(title=draft_title, html=draft_html, source_text=source_text)
            await quality_gate_service.save_report(
                db,
                article_id=article.id,
                stage="QUALITY_SCORE",
                passed=bool(report["passed"]),
                score=report.get("score"),
                blocking_reasons=report.get("blocking_reasons", []),
                actionable_fixes=report.get("actionable_fixes", []),
                report_json=report,
                created_by=job.actor_username or "worker",
                upsert_by_stage=True,
            )
            await db.commit()
            return report

        if op == "links_suggest":
            mode = str(payload.get("mode") or "mixed")
            target_count = int(payload.get("target_count") or 6)
            result = await link_intelligence_service.suggest_for_workspace(
                db,
                work_id=work_id,
                mode=mode,
                target_count=target_count,
                actor=None,
            )
            return result

        if op == "apply_suggestion":
            based_on_version = int(payload.get("based_on_version") or 0)
            if based_on_version != latest.version:
                raise RuntimeError(f"version_conflict_current_{latest.version}")
            merged = await _create_draft_version(
                latest=latest,
                title=payload.get("title"),
                body=str(payload.get("body") or ""),
                note=str(payload.get("note") or f"ai_apply:{payload.get('suggestion_tool') or 'rewrite'}"),
                updated_by=job.actor_username or "worker",
                change_origin="ai_suggestion",
            )
            return {"applied": True, "draft": merged}

    raise RuntimeError(f"unknown_operation:{op}")


@celery_app.task(
    bind=True,
    autoretry_for=(TimeoutError, ConnectionError),
    retry_backoff=True,
    retry_backoff_max=120,
    retry_jitter=True,
    max_retries=5,
)
def run_editorial_ai_job(self: Task, job_id: str) -> dict:
    try:
        result = run_async(_execute_editorial_ai_job(job_id))
        run_async(_mark_completed(job_id, result))
        return {"ok": True, "job_id": job_id}
    except Exception as exc:  # noqa: BLE001
        err = str(exc)
        tb = traceback.format_exc()
        is_final = int(getattr(self.request, "retries", 0)) >= int(getattr(self, "max_retries", 5))
        run_async(_mark_failed_or_dlq(job_id, err, tb, is_final))
        logger.error("editorial_ai_job_failed", job_id=job_id, error=err, final=is_final)
        raise
    finally:
        structlog.contextvars.clear_contextvars()
