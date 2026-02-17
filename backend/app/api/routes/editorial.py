from datetime import datetime
import re
from typing import Literal, Optional
from uuid import uuid4

import asyncio
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.scribe import scribe_agent
from app.api.routes.auth import get_current_user
from app.core.database import get_db, async_session
from app.core.logging import get_logger
from app.models import Article, ArticleQualityReport, EditorDecision, EditorialDraft, FeedbackLog, NewsCategory, NewsStatus
from app.models.user import User, UserRole
from app.schemas import EditorDecisionCreate, EditorDecisionResponse
from app.services.article_index_service import article_index_service
from app.services.ai_service import ai_service
from app.services.quality_gate_service import quality_gate_service
from app.services.trend_signal_service import bump_keyword_interactions, extract_keywords

logger = get_logger("api.editorial")
router = APIRouter(prefix="/editorial", tags=["Editorial"])


class ArticleProcessRequest(BaseModel):
    action: Literal[
        "summarize",
        "translate",
        "proofread",
        "fact_check",
        "social_summary",
        "change_category",
        "change_priority",
        "assign",
        "publish_now",
        "unpublish",
    ]
    value: Optional[str] = Field(default=None, max_length=5000)


class DraftUpsertRequest(BaseModel):
    title: Optional[str] = Field(default=None, max_length=1024)
    body: str = Field(..., min_length=1, max_length=20000)
    note: Optional[str] = Field(default=None, max_length=1000)
    source_action: Optional[str] = Field(default=None, max_length=100)


class DraftUpdateRequest(BaseModel):
    title: Optional[str] = Field(default=None, max_length=1024)
    body: str = Field(..., min_length=1, max_length=20000)
    note: Optional[str] = Field(default=None, max_length=1000)
    version: int = Field(..., ge=1)


def _require_roles(user: User, allowed: set[UserRole]) -> None:
    if user.role not in allowed:
        raise HTTPException(status_code=403, detail="??? ????")


def _can_review_decision(user: User, decision: str) -> None:
    if decision in {"approve", "reject"}:
        _require_roles(user, {UserRole.director, UserRole.editor_chief})
        return
    if decision == "rewrite":
        _require_roles(
            user,
            {
                UserRole.director,
                UserRole.editor_chief,
                UserRole.journalist,
                UserRole.social_media,
                UserRole.print_editor,
            },
        )
        return
    raise HTTPException(status_code=400, detail="???? ??? ????")


def _clean_editorial_output(text: str) -> str:
    cleaned = (text or "").strip()
    patterns = [
        r"(?im)^here\b.*$",
        r"(?im)^sure\b.*$",
        r"(?im)^okay\b.*$",
        r"(?im)^as requested\b.*$",
        r"(?im)^note\b.*$",
        r"(?im)^explanation\b.*$",
        r"(?im)^changes\b.*$",
        r"(?im)^comments?\b.*$",
        r"(?im)^ملاحظة\b.*$",
        r"(?im)^شرح\b.*$",
        r"(?im)^تعليق\b.*$",
        r"(?im)^alternative phrasing.*$",
        r"(?im)^explanation of choices.*$",
        r"(?im)^\*\*alternative phrasing.*$",
        r"(?im)^\*\*explanation of choices.*$",
    ]
    for pattern in patterns:
        cleaned = re.sub(pattern, "", cleaned)
    cleaned = re.sub(r"```[\s\S]*?```", "", cleaned)
    cleaned = re.sub(r"(?im)^\s*(json|output|result)\s*:\s*$", "", cleaned)
    cleaned = re.sub(r"(?im)^(final answer|response)\s*:\s*", "", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned


def _editorial_prompt(action: str, text: str, value: str | None) -> str:
    common = (
        "Role: Senior newsroom editor at Echorouk.\n"
        "Rules:\n"
        "- Return only final editorial text.\n"
        "- No explanations, no side comments, no meta text.\n"
        "- No markdown code fences.\n"
        "- Keep journalistic tone, clear and publishable.\n\n"
    )
    if action == "summarize":
        return (
            common
            + "Task: Produce a concise newsroom summary in Arabic (3 short paragraphs).\n"
            + "Focus on facts, context, and why it matters.\n\n"
            + f"Source text:\n{text}"
        )
    if action == "translate":
        target = (value or "العربية").strip()
        return (
            common
            + f"Task: Translate the source text into {target} with newsroom style.\n"
            + "Preserve facts, names, numbers, and chronology.\n\n"
            + f"Source text:\n{text}"
        )
    if action == "proofread":
        return (
            common
            + "Task: Proofread and rewrite the text in Arabic for publication.\n"
            + "Fix grammar, punctuation, and clarity only.\n\n"
            + f"Source text:\n{text}"
        )
    if action == "fact_check":
        return (
            common
            + "Task: Build a compact fact-check brief in Arabic using this structure exactly:\n"
            + "ادعاءات قابلة للتحقق:\n- ...\n"
            + "ما يلزم التحقق منه:\n- ...\n"
            + "مصادر مقترحة للتحقق:\n- ...\n"
            + "حكم مبدئي:\n...\n\n"
            + f"Source text:\n{text}"
        )
    if action == "social_summary":
        return (
            common
            + "Task: Write 3 short social posts in Arabic (X/Telegram/Facebook style), factual and professional.\n"
            + "No hashtags spam.\n\n"
            + f"Source text:\n{text}"
        )
    return f"{common}Source text:\n{text}"


def _draft_to_dict(draft: EditorialDraft) -> dict:
    return {
        "id": draft.id,
        "article_id": draft.article_id,
        "work_id": draft.work_id,
        "source_action": draft.source_action,
        "title": draft.title,
        "body": draft.body,
        "note": draft.note,
        "status": draft.status,
        "version": draft.version,
        "created_by": draft.created_by,
        "updated_by": draft.updated_by,
        "applied_by": draft.applied_by,
        "applied_at": draft.applied_at,
        "created_at": draft.created_at,
        "updated_at": draft.updated_at,
    }


def _new_work_id() -> str:
    return f"WRK-{datetime.utcnow():%Y%m%d}-{uuid4().hex[:10].upper()}"


def _resolve_latest_draft_by_work_id_stmt(work_id: str):
    return (
        select(EditorialDraft)
        .where(EditorialDraft.work_id == work_id)
        .order_by(EditorialDraft.version.desc(), EditorialDraft.updated_at.desc(), EditorialDraft.id.desc())
        .limit(1)
    )


@router.post("/{article_id}/decide", response_model=EditorDecisionResponse)
async def make_decision(
    article_id: int,
    data: EditorDecisionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _can_review_decision(current_user, data.decision)

    result = await db.execute(select(Article).where(Article.id == article_id))
    article = result.scalar_one_or_none()
    if not article:
        raise HTTPException(404, "Article not found")

    if article.status not in [NewsStatus.CANDIDATE, NewsStatus.CLASSIFIED, NewsStatus.APPROVED_HANDOFF]:
        raise HTTPException(400, f"Article cannot be reviewed in state: {article.status}")

    editor_name = current_user.full_name_ar
    decision = EditorDecision(
        article_id=article_id,
        editor_name=editor_name,
        decision=data.decision,
        reason=data.reason,
        original_ai_title=article.title_ar,
        edited_title=data.edited_title,
        original_ai_body=article.body_html,
        edited_body=data.edited_body,
    )
    db.add(decision)

    if data.edited_title and article.title_ar and data.edited_title != article.title_ar:
        db.add(
            FeedbackLog(
                article_id=article_id,
                field_name="title",
                original_value=article.title_ar,
                corrected_value=data.edited_title,
                correction_type="style",
            )
        )

    if data.edited_body and article.body_html and data.edited_body != article.body_html:
        db.add(
            FeedbackLog(
                article_id=article_id,
                field_name="body",
                original_value=article.body_html[:500],
                corrected_value=data.edited_body[:500],
                correction_type="content",
            )
        )

    if data.decision == "approve":
        article.status = NewsStatus.APPROVED_HANDOFF
        article.reviewed_by = editor_name
        article.reviewed_at = datetime.utcnow()
        if data.edited_title:
            article.title_ar = data.edited_title
        await bump_keyword_interactions(extract_keywords(article.title_ar or article.original_title), weight=2)
    elif data.decision == "reject":
        article.status = NewsStatus.REJECTED
        article.reviewed_by = editor_name
        article.reviewed_at = datetime.utcnow()
        article.rejection_reason = data.reason
    elif data.decision == "rewrite":
        article.body_html = None
        article.status = NewsStatus.APPROVED
        await bump_keyword_interactions(extract_keywords(article.title_ar or article.original_title), weight=1)

    await db.commit()

    logger.info(
        "editorial_decision",
        article_id=article_id,
        decision=data.decision,
        editor=editor_name,
        role=current_user.role.value,
    )

    return EditorDecisionResponse.model_validate(decision)


@router.post("/{article_id}/handoff")
async def handoff_to_scribe(
    article_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_roles(current_user, {UserRole.director, UserRole.editor_chief})

    result = await db.execute(select(Article).where(Article.id == article_id))
    article = result.scalar_one_or_none()
    if not article:
        raise HTTPException(404, "Article not found")
    if article.status not in [NewsStatus.CANDIDATE, NewsStatus.CLASSIFIED, NewsStatus.APPROVED, NewsStatus.APPROVED_HANDOFF, NewsStatus.DRAFT_GENERATED]:
        raise HTTPException(400, f"Article cannot be handed off in state: {article.status}")

    if article.status in [NewsStatus.CANDIDATE, NewsStatus.CLASSIFIED]:
        article.status = NewsStatus.APPROVED_HANDOFF
        article.reviewed_by = current_user.full_name_ar
        article.reviewed_at = datetime.utcnow()
        db.add(
            EditorDecision(
                article_id=article_id,
                editor_name=current_user.full_name_ar,
                decision="approve",
                reason="handoff_to_scribe_v2",
                original_ai_title=article.title_ar,
                original_ai_body=article.body_html,
            )
        )
        await db.commit()
    await bump_keyword_interactions(extract_keywords(article.title_ar or article.original_title), weight=2)

    scribe_result = await scribe_agent.write_article(db, article_id, source_action="approved_handoff")
    if "error" in scribe_result:
        raise HTTPException(400, scribe_result["error"])

    return {
        "article_id": article_id,
        "status": NewsStatus.DRAFT_GENERATED.value,
        "work_id": scribe_result.get("work_id"),
        "draft_id": scribe_result.get("draft_id"),
        "version": scribe_result.get("version"),
    }


@router.post("/{article_id}/process")
async def process_article(
    article_id: int,
    payload: ArticleProcessRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Article).where(Article.id == article_id))
    article = result.scalar_one_or_none()
    if not article:
        raise HTTPException(404, "Article not found")

    newsroom_roles = {
        UserRole.director,
        UserRole.editor_chief,
        UserRole.journalist,
        UserRole.social_media,
        UserRole.print_editor,
    }
    text = article.original_content or article.summary or article.original_title

    if payload.action in {"summarize", "translate", "proofread", "fact_check", "social_summary"}:
        _require_roles(current_user, newsroom_roles)

        prompt = _editorial_prompt(payload.action, text, payload.value)

        output = _clean_editorial_output(await ai_service.generate_text(prompt))
        if not output or not output.strip():
            raise HTTPException(status_code=503, detail="AI service returned empty output")

        readability = quality_gate_service.readability_report(output)

        process_decision = EditorDecision(
            article_id=article_id,
            editor_name=current_user.full_name_ar,
            decision=f"process:{payload.action}",
            reason=f"executed_by:{current_user.role.value}",
        )
        version_result = await db.execute(
            select(func.coalesce(func.max(EditorialDraft.version), 0)).where(
                EditorialDraft.article_id == article_id,
                EditorialDraft.source_action == payload.action,
            )
        )
        next_version = int(version_result.scalar_one() or 0) + 1
        draft_decision = EditorialDraft(
            article_id=article_id,
            work_id=_new_work_id(),
            source_action=payload.action,
            title=article.title_ar or article.original_title,
            body=output,
            note="auto_from_process",
            status="draft",
            version=next_version,
            created_by=current_user.full_name_ar,
            updated_by=current_user.full_name_ar,
        )
        db.add(process_decision)
        db.add(draft_decision)
        await quality_gate_service.save_report(
            db,
            article_id=article_id,
            stage="READABILITY",
            passed=bool(readability["passed"]),
            score=readability.get("score"),
            blocking_reasons=readability.get("blocking_reasons", []),
            actionable_fixes=readability.get("actionable_fixes", []),
            report_json=readability,
            created_by=current_user.full_name_ar,
        )
        await db.commit()
        await db.refresh(draft_decision)

        return {
            "article_id": article_id,
            "action": payload.action,
            "result": output,
            "readability_report": readability,
            "draft": _draft_to_dict(draft_decision),
        }

    if payload.action in {"change_category", "change_priority", "assign"}:
        _require_roles(current_user, {UserRole.director, UserRole.editor_chief})
        if payload.action == "change_category":
            if not payload.value:
                raise HTTPException(400, "value required")
            try:
                article.category = NewsCategory(payload.value)
            except ValueError:
                raise HTTPException(400, "invalid category")
        elif payload.action == "change_priority":
            if payload.value is None:
                raise HTTPException(400, "value required")
            try:
                score = int(payload.value)
            except ValueError:
                raise HTTPException(400, "priority must be int")
            article.importance_score = max(0, min(10, score))
        else:
            article.reviewed_by = payload.value or current_user.full_name_ar

        db.add(
            EditorDecision(
                article_id=article_id,
                editor_name=current_user.full_name_ar,
                decision=f"process:{payload.action}",
                reason=f"value:{payload.value or ''}",
            )
        )
        await db.commit()
        return {"article_id": article_id, "action": payload.action, "updated": True}

    if payload.action in {"publish_now", "unpublish"}:
        _require_roles(current_user, {UserRole.director})
        if payload.action == "publish_now":
            audit = await quality_gate_service.technical_audit(db, article)
            await quality_gate_service.save_report(
                db,
                article_id=article_id,
                stage="SEO_TECH",
                passed=bool(audit["passed"]),
                score=audit.get("score"),
                blocking_reasons=audit.get("blocking_reasons", []),
                actionable_fixes=audit.get("actionable_fixes", []),
                report_json=audit,
                created_by=current_user.full_name_ar,
            )
            if not audit["passed"]:
                await db.commit()
                raise HTTPException(
                    status_code=400,
                    detail={
                        "message": "Technical audit failed",
                        "blocking_reasons": audit.get("blocking_reasons", []),
                        "actionable_fixes": audit.get("actionable_fixes", []),
                    },
                )
            article.status = NewsStatus.PUBLISHED
            article.published_at = datetime.utcnow()
            await bump_keyword_interactions(extract_keywords(article.title_ar or article.original_title), weight=3)
        else:
            article.status = NewsStatus.APPROVED
            article.published_at = None
            article.published_url = None
        db.add(
            EditorDecision(
                article_id=article_id,
                editor_name=current_user.full_name_ar,
                decision=f"process:{payload.action}",
                reason="director_override",
            )
        )
        await db.commit()
        if payload.action == "publish_now":
            async def _guardian_job(article_id: int, created_by: str) -> None:
                async with async_session() as bg_db:
                    art_row = await bg_db.execute(select(Article).where(Article.id == article_id))
                    bg_article = art_row.scalar_one_or_none()
                    if not bg_article:
                        return
                    await quality_gate_service.guardian_check_with_retry(bg_db, bg_article, created_by)

            asyncio.create_task(_guardian_job(article_id, current_user.full_name_ar))
        return {"article_id": article_id, "action": payload.action, "updated": True}

    raise HTTPException(400, "unsupported action")


@router.post("/{article_id}/quality/readability")
async def run_readability_check(
    article_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_roles(
        current_user,
        {UserRole.director, UserRole.editor_chief, UserRole.journalist, UserRole.social_media, UserRole.print_editor},
    )
    article_res = await db.execute(select(Article).where(Article.id == article_id))
    article = article_res.scalar_one_or_none()
    if not article:
        raise HTTPException(404, "Article not found")
    text = article.body_html or article.summary or article.original_content or article.original_title
    report = quality_gate_service.readability_report(text)
    await quality_gate_service.save_report(
        db,
        article_id=article_id,
        stage="READABILITY",
        passed=bool(report["passed"]),
        score=report.get("score"),
        blocking_reasons=report.get("blocking_reasons", []),
        actionable_fixes=report.get("actionable_fixes", []),
        report_json=report,
        created_by=current_user.full_name_ar,
    )
    await db.commit()
    return report


@router.post("/{article_id}/quality/technical")
async def run_technical_audit(
    article_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_roles(current_user, {UserRole.director, UserRole.editor_chief})
    article_res = await db.execute(select(Article).where(Article.id == article_id))
    article = article_res.scalar_one_or_none()
    if not article:
        raise HTTPException(404, "Article not found")
    report = await quality_gate_service.technical_audit(db, article)
    await quality_gate_service.save_report(
        db,
        article_id=article_id,
        stage="SEO_TECH",
        passed=bool(report["passed"]),
        score=report.get("score"),
        blocking_reasons=report.get("blocking_reasons", []),
        actionable_fixes=report.get("actionable_fixes", []),
        report_json=report,
        created_by=current_user.full_name_ar,
    )
    await db.commit()
    return report


@router.post("/{article_id}/quality/guardian")
async def run_guardian_check(
    article_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_roles(current_user, {UserRole.director, UserRole.editor_chief})
    article_res = await db.execute(select(Article).where(Article.id == article_id))
    article = article_res.scalar_one_or_none()
    if not article:
        raise HTTPException(404, "Article not found")
    url = article.published_url or article.original_url or ""
    report = await quality_gate_service.guardian_check(url)
    await quality_gate_service.save_report(
        db,
        article_id=article_id,
        stage="POST_PUBLISH",
        passed=bool(report["passed"]),
        score=report.get("score"),
        blocking_reasons=report.get("blocking_reasons", []),
        actionable_fixes=report.get("actionable_fixes", []),
        report_json=report,
        created_by=current_user.full_name_ar,
    )
    await db.commit()
    return report


@router.get("/{article_id}/quality/reports")
async def get_quality_reports(
    article_id: int,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_roles(
        current_user,
        {UserRole.director, UserRole.editor_chief, UserRole.journalist, UserRole.social_media, UserRole.print_editor},
    )
    rows = await db.execute(
        select(ArticleQualityReport)
        .where(ArticleQualityReport.article_id == article_id)
        .order_by(ArticleQualityReport.created_at.desc(), ArticleQualityReport.id.desc())
        .limit(max(1, min(limit, 100)))
    )
    reports = rows.scalars().all()
    return [
        {
            "id": r.id,
            "stage": r.stage,
            "passed": bool(r.passed),
            "score": r.score,
            "blocking_reasons": r.blocking_reasons or [],
            "actionable_fixes": r.actionable_fixes or [],
            "report_json": r.report_json or {},
            "created_by": r.created_by,
            "created_at": r.created_at,
        }
        for r in reports
    ]


@router.get("/workspace/drafts")
async def workspace_drafts(
    status: str = "draft",
    article_id: Optional[int] = None,
    source_action: Optional[str] = None,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_roles(
        current_user,
        {
            UserRole.director,
            UserRole.editor_chief,
            UserRole.journalist,
            UserRole.social_media,
            UserRole.print_editor,
        },
    )

    query = select(EditorialDraft).where(EditorialDraft.status == status)
    if article_id is not None:
        query = query.where(EditorialDraft.article_id == article_id)
    if source_action:
        query = query.where(EditorialDraft.source_action == source_action)

    result = await db.execute(
        query
        .order_by(EditorialDraft.updated_at.desc(), EditorialDraft.id.desc())
        .limit(max(1, min(limit, 500)))
    )
    drafts = result.scalars().all()
    return [_draft_to_dict(d) for d in drafts]


@router.get("/workspace/drafts/{work_id}")
async def workspace_draft_by_work_id(
    work_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_roles(
        current_user,
        {
            UserRole.director,
            UserRole.editor_chief,
            UserRole.journalist,
            UserRole.social_media,
            UserRole.print_editor,
        },
    )

    result = await db.execute(_resolve_latest_draft_by_work_id_stmt(work_id))
    draft = result.scalar_one_or_none()
    if not draft:
        raise HTTPException(404, "Draft not found")
    return _draft_to_dict(draft)


@router.post("/workspace/drafts/{work_id}/apply")
async def apply_draft_by_work_id(
    work_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_roles(
        current_user,
        {
            UserRole.director,
            UserRole.editor_chief,
            UserRole.journalist,
            UserRole.social_media,
            UserRole.print_editor,
        },
    )

    draft_result = await db.execute(_resolve_latest_draft_by_work_id_stmt(work_id))
    draft = draft_result.scalar_one_or_none()
    if not draft:
        raise HTTPException(404, "Draft not found")
    if draft.status != "draft":
        raise HTTPException(409, "Draft already applied or archived")

    article_result = await db.execute(select(Article).where(Article.id == draft.article_id))
    article = article_result.scalar_one_or_none()
    if not article:
        raise HTTPException(404, "Article not found")

    if draft.title:
        article.title_ar = draft.title
    if draft.body:
        article.body_html = draft.body
    draft.status = "applied"
    draft.applied_by = current_user.full_name_ar
    draft.applied_at = datetime.utcnow()
    draft.updated_by = current_user.full_name_ar

    db.add(
        EditorDecision(
            article_id=article.id,
            editor_name=current_user.full_name_ar,
            decision="process:apply_draft",
            reason=f"work_id:{work_id}",
            edited_title=draft.title,
            edited_body=draft.body,
        )
    )
    await article_index_service.upsert_article(db, article)
    await db.commit()
    return {"article_id": article.id, "work_id": work_id, "applied": True, "draft": _draft_to_dict(draft)}


@router.post("/workspace/drafts/{work_id}/archive")
async def archive_draft_by_work_id(
    work_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_roles(
        current_user,
        {
            UserRole.director,
            UserRole.editor_chief,
            UserRole.journalist,
            UserRole.social_media,
            UserRole.print_editor,
        },
    )

    draft_result = await db.execute(_resolve_latest_draft_by_work_id_stmt(work_id))
    draft = draft_result.scalar_one_or_none()
    if not draft:
        raise HTTPException(404, "Draft not found")
    if draft.status == "archived":
        return {"work_id": work_id, "archived": True, "draft": _draft_to_dict(draft)}

    draft.status = "archived"
    draft.updated_by = current_user.full_name_ar
    await db.commit()
    return {"work_id": work_id, "archived": True, "draft": _draft_to_dict(draft)}


@router.post("/workspace/drafts/{work_id}/regenerate")
async def regenerate_draft_by_work_id(
    work_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_roles(
        current_user,
        {
            UserRole.director,
            UserRole.editor_chief,
            UserRole.journalist,
            UserRole.social_media,
            UserRole.print_editor,
        },
    )

    draft_result = await db.execute(_resolve_latest_draft_by_work_id_stmt(work_id))
    latest = draft_result.scalar_one_or_none()
    if not latest:
        raise HTTPException(404, "Draft not found")

    article_result = await db.execute(select(Article).where(Article.id == latest.article_id))
    article = article_result.scalar_one_or_none()
    if not article:
        raise HTTPException(404, "Article not found")

    if article.status not in [NewsStatus.APPROVED, NewsStatus.APPROVED_HANDOFF, NewsStatus.DRAFT_GENERATED]:
        article.status = NewsStatus.APPROVED_HANDOFF
        await db.commit()

    scribe_result = await scribe_agent.write_article(
        db,
        latest.article_id,
        source_action=latest.source_action or "approved_handoff",
        fixed_work_id=work_id,
    )
    if "error" in scribe_result:
        raise HTTPException(400, scribe_result["error"])

    return {
        "article_id": latest.article_id,
        "work_id": work_id,
        "draft_id": scribe_result.get("draft_id"),
        "version": scribe_result.get("version"),
        "regenerated": True,
    }


@router.get("/{article_id}/drafts")
async def list_drafts(
    article_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_roles(
        current_user,
        {
            UserRole.director,
            UserRole.editor_chief,
            UserRole.journalist,
            UserRole.social_media,
            UserRole.print_editor,
        },
    )
    result = await db.execute(
        select(EditorialDraft)
        .where(EditorialDraft.article_id == article_id)
        .order_by(EditorialDraft.updated_at.desc(), EditorialDraft.id.desc())
    )
    drafts = result.scalars().all()
    return [_draft_to_dict(d) for d in drafts]


@router.get("/{article_id}/drafts/{draft_id}")
async def get_draft(
    article_id: int,
    draft_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_roles(
        current_user,
        {
            UserRole.director,
            UserRole.editor_chief,
            UserRole.journalist,
            UserRole.social_media,
            UserRole.print_editor,
        },
    )
    result = await db.execute(
        select(EditorialDraft).where(
            EditorialDraft.id == draft_id,
            EditorialDraft.article_id == article_id,
        )
    )
    draft = result.scalar_one_or_none()
    if not draft:
        raise HTTPException(404, "Draft not found")
    return _draft_to_dict(draft)


@router.post("/{article_id}/drafts")
async def create_draft(
    article_id: int,
    payload: DraftUpsertRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_roles(
        current_user,
        {
            UserRole.director,
            UserRole.editor_chief,
            UserRole.journalist,
            UserRole.social_media,
            UserRole.print_editor,
        },
    )
    article_result = await db.execute(select(Article).where(Article.id == article_id))
    article = article_result.scalar_one_or_none()
    if not article:
        raise HTTPException(404, "Article not found")

    source_action = payload.source_action or "manual"
    version_result = await db.execute(
        select(func.coalesce(func.max(EditorialDraft.version), 0)).where(
            EditorialDraft.article_id == article_id,
            EditorialDraft.source_action == source_action,
        )
    )
    next_version = int(version_result.scalar_one() or 0) + 1
    draft = EditorialDraft(
        article_id=article_id,
        work_id=_new_work_id(),
        source_action=source_action,
        title=payload.title or article.title_ar or article.original_title,
        body=payload.body,
        note=payload.note or "manual_draft",
        status="draft",
        version=next_version,
        created_by=current_user.full_name_ar,
        updated_by=current_user.full_name_ar,
    )
    db.add(draft)
    await db.commit()
    await db.refresh(draft)
    return _draft_to_dict(draft)


@router.put("/{article_id}/drafts/{draft_id}")
async def update_draft(
    article_id: int,
    draft_id: int,
    payload: DraftUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_roles(
        current_user,
        {
            UserRole.director,
            UserRole.editor_chief,
            UserRole.journalist,
            UserRole.social_media,
            UserRole.print_editor,
        },
    )

    draft_result = await db.execute(
        select(EditorialDraft).where(
            EditorialDraft.id == draft_id,
            EditorialDraft.article_id == article_id,
        )
    )
    draft = draft_result.scalar_one_or_none()
    if not draft:
        raise HTTPException(404, "Draft not found")
    if draft.status != "draft":
        raise HTTPException(409, "Cannot update non-draft state")
    if payload.version != draft.version:
        raise HTTPException(409, f"Draft version conflict. current={draft.version}")

    draft.title = payload.title or draft.title
    draft.body = payload.body
    draft.note = payload.note
    draft.updated_by = current_user.full_name_ar
    draft.version += 1
    await db.commit()
    await db.refresh(draft)
    return _draft_to_dict(draft)


@router.post("/{article_id}/drafts/{draft_id}/apply")
async def apply_draft(
    article_id: int,
    draft_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_roles(
        current_user,
        {
            UserRole.director,
            UserRole.editor_chief,
            UserRole.journalist,
            UserRole.social_media,
            UserRole.print_editor,
        },
    )
    article_result = await db.execute(select(Article).where(Article.id == article_id))
    article = article_result.scalar_one_or_none()
    if not article:
        raise HTTPException(404, "Article not found")

    draft_result = await db.execute(
        select(EditorialDraft).where(
            EditorialDraft.id == draft_id,
            EditorialDraft.article_id == article_id,
        )
    )
    draft = draft_result.scalar_one_or_none()
    if not draft:
        raise HTTPException(404, "Draft not found")
    if draft.status != "draft":
        raise HTTPException(409, "Draft already applied or archived")

    if draft.title:
        article.title_ar = draft.title
    if draft.body:
        article.body_html = draft.body
    draft.status = "applied"
    draft.applied_by = current_user.full_name_ar
    draft.applied_at = datetime.utcnow()
    draft.updated_by = current_user.full_name_ar

    db.add(
        EditorDecision(
            article_id=article_id,
            editor_name=current_user.full_name_ar,
            decision="process:apply_draft",
            reason=f"draft_id:{draft_id}",
            edited_title=draft.title,
            edited_body=draft.body,
        )
    )
    await article_index_service.upsert_article(db, article)
    await db.commit()
    return {"article_id": article_id, "draft_id": draft_id, "applied": True, "draft": _draft_to_dict(draft)}


@router.get("/{article_id}/decisions", response_model=list[EditorDecisionResponse])
async def get_decisions(
    article_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_roles(
        current_user,
        {
            UserRole.director,
            UserRole.editor_chief,
            UserRole.journalist,
            UserRole.social_media,
            UserRole.print_editor,
        },
    )
    result = await db.execute(
        select(EditorDecision)
        .where(EditorDecision.article_id == article_id)
        .order_by(EditorDecision.decided_at.desc())
    )
    decisions = result.scalars().all()
    return [EditorDecisionResponse.model_validate(d) for d in decisions]


@router.post("/{article_id}/generate")
async def generate_article(
    article_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_roles(current_user, {UserRole.director, UserRole.editor_chief, UserRole.journalist})
    result = await scribe_agent.write_article(db, article_id)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result
