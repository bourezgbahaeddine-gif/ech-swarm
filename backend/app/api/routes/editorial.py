from datetime import datetime
import re
from typing import Literal, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.scribe import scribe_agent
from app.api.routes.auth import get_current_user
from app.core.database import get_db
from app.core.logging import get_logger
from app.models import Article, EditorDecision, EditorialDraft, FeedbackLog, NewsCategory, NewsStatus
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
        r"(?im)^alternative phrasing.*$",
        r"(?im)^explanation of choices.*$",
        r"(?im)^\*\*alternative phrasing.*$",
        r"(?im)^\*\*explanation of choices.*$",
    ]
    for pattern in patterns:
        cleaned = re.sub(pattern, "", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned


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

        if payload.action == "summarize":
            prompt = f"??? ???? ?????? ?? 3 ???? ??????? ?????:\n\n{text}"
        elif payload.action == "translate":
            target = payload.value or "??????? ??????"
            prompt = f"???? ???? ?????? ??? {target} ?????? ?????:\n\n{text}"
        elif payload.action == "proofread":
            prompt = f"??? ???? ?????? ????? ???????? ?? ?????? ??? ??????:\n\n{text}"
        elif payload.action == "fact_check":
            prompt = (
                "??? ??????? ?????? ???? ??????? ???? ?????? ???:\n"
                "???? ????? ????:\n- ...\n"
                "??????? ?????/?????:\n- ...\n"
                "????? ???? ?????:\n...\n\n"
                f"????:\n{text}"
            )
        else:
            prompt = f"???? ?????? ??????? ???????? ????? ??? ???? ??????:\n\n{text}"

        output = _clean_editorial_output(await ai_service.generate_text(prompt))
        if not output or not output.strip():
            raise HTTPException(status_code=503, detail="AI service returned empty output")

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
        await db.commit()
        await db.refresh(draft_decision)

        return {
            "article_id": article_id,
            "action": payload.action,
            "result": output,
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

    raise HTTPException(400, "unsupported action")


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
