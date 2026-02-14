"""
Echorouk AI Swarm - Editorial API Routes
========================================
Human-in-the-loop editorial decision and article processing endpoints.
"""

from datetime import datetime
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.scribe import scribe_agent
from app.api.routes.auth import get_current_user
from app.core.database import get_db
from app.core.logging import get_logger
from app.models import Article, EditorDecision, FeedbackLog, NewsCategory, NewsStatus
from app.models.user import User, UserRole
from app.schemas import EditorDecisionCreate, EditorDecisionResponse
from app.services.ai_service import ai_service

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


def _require_roles(user: User, allowed: set[UserRole]) -> None:
    if user.role not in allowed:
        raise HTTPException(status_code=403, detail="??? ???? ???? ???????")


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
    raise HTTPException(status_code=400, detail="???? ??? ?????")


@router.post("/{article_id}/decide", response_model=EditorDecisionResponse)
async def make_decision(
    article_id: int,
    data: EditorDecisionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Submit an editorial decision for an article.
    approve/reject: editor-in-chief/director
    rewrite: any newsroom role
    """
    _can_review_decision(current_user, data.decision)

    result = await db.execute(select(Article).where(Article.id == article_id))
    article = result.scalar_one_or_none()

    if not article:
        raise HTTPException(404, "Article not found")

    if article.status not in [NewsStatus.CANDIDATE, NewsStatus.CLASSIFIED]:
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
        article.status = NewsStatus.APPROVED
        article.reviewed_by = editor_name
        article.reviewed_at = datetime.utcnow()
        if data.edited_title:
            article.title_ar = data.edited_title
        if data.edited_body:
            article.body_html = data.edited_body
    elif data.decision == "reject":
        article.status = NewsStatus.REJECTED
        article.reviewed_by = editor_name
        article.reviewed_at = datetime.utcnow()
        article.rejection_reason = data.reason
    elif data.decision == "rewrite":
        article.body_html = None
        article.status = NewsStatus.APPROVED

    await db.commit()

    logger.info(
        "editorial_decision",
        article_id=article_id,
        decision=data.decision,
        editor=editor_name,
        role=current_user.role.value,
    )

    return EditorDecisionResponse.model_validate(decision)


@router.post("/{article_id}/process")
async def process_article(
    article_id: int,
    payload: ArticleProcessRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Process article with role-scoped actions and save outputs as interactive drafts."""
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

        if payload.action == "summarize":
            prompt = (
                "Summarize this news item in Arabic as 3 clear editorial bullets, neutral tone.\n\n"
                f"{text}"
            )
        elif payload.action == "translate":
            target = payload.value or "Arabic (MSA)"
            prompt = f"Translate the following text to {target} while preserving journalistic accuracy:\n\n{text}"
        elif payload.action == "proofread":
            prompt = f"Proofread the following text and return only the corrected version:\n\n{text}"
        elif payload.action == "fact_check":
            prompt = (
                "Fact-check this article and return: (1) claims needing verification, "
                "(2) possible contradictions, (3) safer publishable wording.\n\n"
                f"{text}"
            )
        else:
            prompt = f"Write 2 short social media variants for this news without sensationalism:\n\n{text}"

        output = await ai_service.generate_text(prompt)
        if not output or not output.strip():
            raise HTTPException(
                status_code=503,
                detail="????? ???????? ??????. ???? ?? ??????? GEMINI_API_KEY ?? ???? ??????.",
            )

        process_decision = EditorDecision(
            article_id=article_id,
            editor_name=current_user.full_name_ar,
            decision=f"process:{payload.action}",
            reason=f"executed_by:{current_user.role.value}",
        )
        draft_decision = EditorDecision(
            article_id=article_id,
            editor_name=current_user.full_name_ar,
            decision=f"draft:{payload.action}",
            reason="auto_from_process",
            original_ai_title=article.title_ar or article.original_title,
            edited_title=article.title_ar or article.original_title,
            original_ai_body=article.body_html or article.original_content or article.summary,
            edited_body=output,
        )
        db.add(process_decision)
        db.add(draft_decision)
        await db.commit()
        await db.refresh(draft_decision)

        return {
            "article_id": article_id,
            "action": payload.action,
            "result": output,
            "draft": {
                "id": draft_decision.id,
                "title": draft_decision.edited_title,
                "body": draft_decision.edited_body,
            },
        }

    if payload.action in {"change_category", "change_priority", "assign"}:
        _require_roles(current_user, {UserRole.director, UserRole.editor_chief})
        if payload.action == "change_category":
            if not payload.value:
                raise HTTPException(400, "value ?????")
            try:
                article.category = NewsCategory(payload.value)
            except ValueError:
                raise HTTPException(400, "????? ??? ????")
        elif payload.action == "change_priority":
            if payload.value is None:
                raise HTTPException(400, "value ?????")
            try:
                score = int(payload.value)
            except ValueError:
                raise HTTPException(400, "priority ??? ?? ???? ?????")
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
            article.status = NewsStatus.PUBLISHED
            article.published_at = datetime.utcnow()
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
        return {"article_id": article_id, "action": payload.action, "updated": True}

    raise HTTPException(400, "????? ??? ?????")


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
        select(EditorDecision)
        .where(EditorDecision.article_id == article_id, EditorDecision.decision.like("draft:%"))
        .order_by(EditorDecision.decided_at.desc())
    )
    drafts = result.scalars().all()
    return [
        {
            "id": d.id,
            "article_id": d.article_id,
            "source_action": (d.decision or "").replace("draft:", "", 1),
            "editor_name": d.editor_name,
            "title": d.edited_title,
            "body": d.edited_body,
            "note": d.reason,
            "created_at": d.decided_at,
        }
        for d in drafts
    ]


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
    draft = EditorDecision(
        article_id=article_id,
        editor_name=current_user.full_name_ar,
        decision=f"draft:{source_action}",
        reason=payload.note or "manual_draft",
        original_ai_title=article.title_ar or article.original_title,
        edited_title=payload.title or article.title_ar or article.original_title,
        original_ai_body=article.body_html or article.original_content or article.summary,
        edited_body=payload.body,
    )
    db.add(draft)
    await db.commit()
    await db.refresh(draft)
    return {
        "id": draft.id,
        "article_id": draft.article_id,
        "source_action": source_action,
        "editor_name": draft.editor_name,
        "title": draft.edited_title,
        "body": draft.edited_body,
        "note": draft.reason,
        "created_at": draft.decided_at,
    }


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
        select(EditorDecision).where(
            EditorDecision.id == draft_id,
            EditorDecision.article_id == article_id,
            EditorDecision.decision.like("draft:%"),
        )
    )
    draft = draft_result.scalar_one_or_none()
    if not draft:
        raise HTTPException(404, "Draft not found")

    if draft.edited_title:
        article.title_ar = draft.edited_title
    if draft.edited_body:
        article.body_html = draft.edited_body

    db.add(
        EditorDecision(
            article_id=article_id,
            editor_name=current_user.full_name_ar,
            decision="process:apply_draft",
            reason=f"draft_id:{draft_id}",
            original_ai_title=draft.original_ai_title,
            edited_title=draft.edited_title,
            original_ai_body=draft.original_ai_body,
            edited_body=draft.edited_body,
        )
    )
    await db.commit()
    return {"article_id": article_id, "draft_id": draft_id, "applied": True}


@router.get("/{article_id}/decisions", response_model=list[EditorDecisionResponse])
async def get_decisions(
    article_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all editorial decisions for an article."""
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
    """Trigger article generation for an approved article."""
    _require_roles(current_user, {UserRole.director, UserRole.editor_chief, UserRole.journalist})
    result = await scribe_agent.write_article(db, article_id)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result
