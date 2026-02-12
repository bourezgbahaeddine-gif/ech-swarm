"""
Echorouk AI Swarm — Editorial API Routes
==========================================
Human-in-the-loop editorial decision endpoints.
Approve, reject, rewrite articles + feedback tracking.
"""

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.logging import get_logger
from app.models import Article, EditorDecision, FeedbackLog, NewsStatus
from app.schemas import EditorDecisionCreate, EditorDecisionResponse
from app.agents.scribe import scribe_agent

logger = get_logger("api.editorial")
router = APIRouter(prefix="/editorial", tags=["Editorial"])


@router.post("/{article_id}/decide", response_model=EditorDecisionResponse)
async def make_decision(
    article_id: int,
    data: EditorDecisionCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Submit an editorial decision for a candidate article.
    Actions: approve | reject | rewrite
    """
    result = await db.execute(select(Article).where(Article.id == article_id))
    article = result.scalar_one_or_none()

    if not article:
        raise HTTPException(404, "Article not found")

    if article.status not in [NewsStatus.CANDIDATE, NewsStatus.CLASSIFIED]:
        raise HTTPException(400, f"Article cannot be reviewed in state: {article.status}")

    # Record the decision
    decision = EditorDecision(
        article_id=article_id,
        editor_name=data.editor_name,
        decision=data.decision,
        reason=data.reason,
        original_ai_title=article.title_ar,
        edited_title=data.edited_title,
        original_ai_body=article.body_html,
        edited_body=data.edited_body,
    )
    db.add(decision)

    # ── Track RLHF Feedback ──
    if data.edited_title and article.title_ar and data.edited_title != article.title_ar:
        feedback = FeedbackLog(
            article_id=article_id,
            field_name="title",
            original_value=article.title_ar,
            corrected_value=data.edited_title,
            correction_type="style",
        )
        db.add(feedback)

    if data.edited_body and article.body_html and data.edited_body != article.body_html:
        feedback = FeedbackLog(
            article_id=article_id,
            field_name="body",
            original_value=article.body_html[:500],
            corrected_value=data.edited_body[:500],
            correction_type="content",
        )
        db.add(feedback)

    # ── Update Article Status ──
    if data.decision == "approve":
        article.status = NewsStatus.APPROVED
        article.reviewed_by = data.editor_name
        article.reviewed_at = datetime.utcnow()

        # Apply editor changes if present
        if data.edited_title:
            article.title_ar = data.edited_title
        if data.edited_body:
            article.body_html = data.edited_body

    elif data.decision == "reject":
        article.status = NewsStatus.REJECTED
        article.reviewed_by = data.editor_name
        article.reviewed_at = datetime.utcnow()
        article.rejection_reason = data.reason

    elif data.decision == "rewrite":
        # Trigger re-generation
        article.body_html = None  # Clear for re-generation
        article.status = NewsStatus.APPROVED  # Will be picked up by scribe

    await db.commit()

    logger.info(
        "editorial_decision",
        article_id=article_id,
        decision=data.decision,
        editor=data.editor_name,
    )

    return EditorDecisionResponse.model_validate(decision)


@router.get("/{article_id}/decisions", response_model=list[EditorDecisionResponse])
async def get_decisions(article_id: int, db: AsyncSession = Depends(get_db)):
    """Get all editorial decisions for an article."""
    result = await db.execute(
        select(EditorDecision)
        .where(EditorDecision.article_id == article_id)
        .order_by(EditorDecision.decided_at.desc())
    )
    decisions = result.scalars().all()
    return [EditorDecisionResponse.model_validate(d) for d in decisions]


@router.post("/{article_id}/generate")
async def generate_article(article_id: int, db: AsyncSession = Depends(get_db)):
    """Trigger article generation for an approved article."""
    result = await scribe_agent.write_article(db, article_id)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result
