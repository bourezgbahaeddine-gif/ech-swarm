from __future__ import annotations

from datetime import datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.rbac import require_roles
from app.api.envelope import success_envelope
from app.core.database import get_db
from app.models.news import Article
from app.models.script import ScriptOutput, ScriptProjectStatus, ScriptProjectType
from app.models.story import Story
from app.models.user import User, UserRole
from app.repositories.script_repository import script_repository
from app.services.audit_service import audit_service
from app.services.job_queue_service import job_queue_service
from app.services.script_studio_service import script_studio_service

router = APIRouter(prefix="/scripts", tags=["Script Studio"])

SCRIPT_QUEUE_NAME = "ai_scripts"
SCRIPT_JOB_TYPE = "script_generate"

VIEW_ROLES = (
    UserRole.director,
    UserRole.editor_chief,
    UserRole.journalist,
    UserRole.social_media,
    UserRole.print_editor,
)

CHIEF_ROLES = (
    UserRole.director,
    UserRole.editor_chief,
)


class ScriptFromArticleRequest(BaseModel):
    type: Literal["story_script", "video_script"]
    tone: str = Field(default="neutral", max_length=50)
    length_seconds: int = Field(default=75, ge=20, le=900)
    language: str = Field(default="ar", max_length=8)
    style_constraints: list[str] = Field(default_factory=list)


class ScriptFromStoryRequest(BaseModel):
    type: Literal["story_script", "video_script"]
    tone: str = Field(default="neutral", max_length=50)
    length_seconds: int = Field(default=90, ge=20, le=1200)
    language: str = Field(default="ar", max_length=8)
    style_constraints: list[str] = Field(default_factory=list)


class BulletinRequest(BaseModel):
    max_items: int = Field(default=8, ge=1, le=20)
    duration_minutes: int = Field(default=5, ge=1, le=30)
    desks: list[str] = Field(default_factory=list)
    language: str = Field(default="ar", max_length=8)
    tone: str = Field(default="neutral", max_length=50)


class ScriptDecisionRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=2000)


def _serialize_output(output: ScriptOutput) -> dict:
    return {
        "id": output.id,
        "script_id": output.script_id,
        "version": output.version,
        "format": output.format.value if output.format else "json",
        "content_json": output.content_json,
        "content_text": output.content_text,
        "quality_issues": output.quality_issues_json if isinstance(output.quality_issues_json, list) else [],
        "created_at": output.created_at.isoformat() if output.created_at else None,
    }


def _serialize_project(project, *, include_outputs: bool = True) -> dict:
    outputs = list(project.outputs or [])
    outputs.sort(key=lambda row: row.version, reverse=True)
    return {
        "id": project.id,
        "type": project.type.value if project.type else None,
        "status": project.status.value if project.status else None,
        "story_id": project.story_id,
        "article_id": project.article_id,
        "title": project.title,
        "params_json": project.params_json if isinstance(project.params_json, dict) else {},
        "created_by": project.created_by,
        "updated_by": project.updated_by,
        "created_at": project.created_at.isoformat() if project.created_at else None,
        "updated_at": project.updated_at.isoformat() if project.updated_at else None,
        "outputs": [_serialize_output(output) for output in outputs] if include_outputs else [],
    }


def _parse_project_type(value: str | None) -> ScriptProjectType | None:
    if not value:
        return None
    try:
        return ScriptProjectType(value.strip().lower())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid script type") from exc


def _parse_project_status(value: str | None) -> ScriptProjectStatus | None:
    if not value:
        return None
    try:
        return ScriptProjectStatus(value.strip().lower())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid script status") from exc


def _assert_chief_permission(user: User) -> None:
    if user.role not in CHIEF_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to review scripts")


async def _queue_script_generation(
    *,
    db: AsyncSession,
    script_id: int,
    actor: User,
) -> dict:
    allowed, depth, limit_depth = await job_queue_service.check_backpressure(SCRIPT_QUEUE_NAME)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Queue overloaded ({depth}/{limit_depth}). Retry shortly.",
        )

    target_version = await script_repository.get_next_output_version(db, script_id)
    idempotency_key = f"script:{script_id}:v{target_version}"
    job = await job_queue_service.create_job(
        db,
        job_type=SCRIPT_JOB_TYPE,
        queue_name=SCRIPT_QUEUE_NAME,
        payload={
            "script_id": script_id,
            "target_version": target_version,
            "idempotency_key": idempotency_key,
        },
        entity_id=str(script_id),
        actor_user_id=actor.id,
        actor_username=actor.username,
        max_attempts=3,
    )
    await job_queue_service.enqueue_by_job_type(job_type=SCRIPT_JOB_TYPE, job_id=str(job.id))
    return {"job_id": str(job.id), "status": "queued", "target_version": target_version}


@router.get("")
async def list_script_projects(
    limit: int = Query(60, ge=1, le=200),
    type: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(*VIEW_ROLES)),
):
    projects = await script_repository.list_projects(
        db,
        limit=limit,
        project_type=_parse_project_type(type),
        status=_parse_project_status(status_filter),
    )
    return success_envelope([_serialize_project(project, include_outputs=False) for project in projects])


@router.post("/from-article/{article_id}", status_code=status.HTTP_202_ACCEPTED)
async def create_script_from_article(
    article_id: int,
    payload: ScriptFromArticleRequest,
    reuse: Annotated[bool, Query()] = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*VIEW_ROLES)),
):
    row = await db.execute(select(Article).where(Article.id == article_id))
    article = row.scalar_one_or_none()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    project_type = _parse_project_type(payload.type)
    if project_type not in {ScriptProjectType.story_script, ScriptProjectType.video_script}:
        raise HTTPException(status_code=400, detail="Unsupported script type for article source")

    if reuse:
        reusable = await script_repository.get_latest_project_by_source(
            db,
            project_type=project_type,
            article_id=article.id,
        )
        if reusable:
            return success_envelope(
                {"script": _serialize_project(reusable), "job": None},
                meta={"reused": True},
            )

    script_title = f"{'Video Package' if project_type == ScriptProjectType.video_script else 'Story Script'} - {_safe_article_title(article)}"
    params_json = {
        "tone": payload.tone,
        "length_seconds": payload.length_seconds,
        "language": payload.language,
        "style_constraints": payload.style_constraints,
    }
    project = await script_repository.create_project(
        db,
        project_type=project_type,
        title=script_title[:1024],
        params_json=params_json,
        created_by=current_user.username,
        article_id=article.id,
    )
    await audit_service.log_action(
        db,
        action="script_project_create",
        entity_type="script_project",
        entity_id=project.id,
        actor=current_user,
        details={"source": "article", "article_id": article.id, "type": project_type.value},
    )
    queue_meta = await _queue_script_generation(db=db, script_id=project.id, actor=current_user)
    reloaded = await script_repository.get_project_by_id(db, project.id)
    if not reloaded:
        raise HTTPException(status_code=500, detail="Failed to load script project")
    return success_envelope({"script": _serialize_project(reloaded), "job": queue_meta}, status_code=status.HTTP_202_ACCEPTED)


@router.post("/from-story/{story_id}", status_code=status.HTTP_202_ACCEPTED)
async def create_script_from_story(
    story_id: int,
    payload: ScriptFromStoryRequest,
    reuse: Annotated[bool, Query()] = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*VIEW_ROLES)),
):
    story_row = await db.execute(select(Story).where(Story.id == story_id))
    story = story_row.scalar_one_or_none()
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")

    project_type = _parse_project_type(payload.type)
    if project_type not in {ScriptProjectType.story_script, ScriptProjectType.video_script}:
        raise HTTPException(status_code=400, detail="Unsupported script type for story source")

    if reuse:
        reusable = await script_repository.get_latest_project_by_source(
            db,
            project_type=project_type,
            story_id=story.id,
        )
        if reusable:
            return success_envelope(
                {"script": _serialize_project(reusable), "job": None},
                meta={"reused": True},
            )

    params_json = {
        "tone": payload.tone,
        "length_seconds": payload.length_seconds,
        "language": payload.language,
        "style_constraints": payload.style_constraints,
    }
    project = await script_repository.create_project(
        db,
        project_type=project_type,
        title=f"{'Video Package' if project_type == ScriptProjectType.video_script else 'Story Script'} - {story.title}"[:1024],
        params_json=params_json,
        created_by=current_user.username,
        story_id=story.id,
    )
    await audit_service.log_action(
        db,
        action="script_project_create",
        entity_type="script_project",
        entity_id=project.id,
        actor=current_user,
        details={"source": "story", "story_id": story.id, "type": project_type.value},
    )
    queue_meta = await _queue_script_generation(db=db, script_id=project.id, actor=current_user)
    reloaded = await script_repository.get_project_by_id(db, project.id)
    if not reloaded:
        raise HTTPException(status_code=500, detail="Failed to load script project")
    return success_envelope({"script": _serialize_project(reloaded), "job": queue_meta}, status_code=status.HTTP_202_ACCEPTED)


@router.post("/bulletin/daily", status_code=status.HTTP_202_ACCEPTED)
async def generate_daily_bulletin(
    payload: BulletinRequest,
    geo: str = Query(default="ALL"),
    category: str = Query(default="all"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*VIEW_ROLES)),
):
    selected_articles = await script_studio_service.select_bulletin_articles(
        db,
        since=datetime.utcnow() - timedelta(hours=24),
        geo=geo,
        category=category,
        desks=payload.desks,
        max_items=payload.max_items,
    )
    if not selected_articles:
        raise HTTPException(status_code=400, detail="No eligible news items found for daily bulletin window")

    params_json = {
        "max_items": payload.max_items,
        "duration_minutes": payload.duration_minutes,
        "desks": payload.desks,
        "language": payload.language,
        "tone": payload.tone,
        "geo": geo,
        "category": category,
        "period_hours": 24,
        "selected_article_ids": [row.id for row in selected_articles],
    }
    project = await script_repository.create_project(
        db,
        project_type=ScriptProjectType.bulletin_daily,
        title=f"Daily Bulletin - {datetime.utcnow():%Y-%m-%d}",
        params_json=params_json,
        created_by=current_user.username,
    )
    await audit_service.log_action(
        db,
        action="script_project_create",
        entity_type="script_project",
        entity_id=project.id,
        actor=current_user,
        details={"source": "bulletin_daily", "selected_items": len(selected_articles)},
    )
    queue_meta = await _queue_script_generation(db=db, script_id=project.id, actor=current_user)
    reloaded = await script_repository.get_project_by_id(db, project.id)
    if not reloaded:
        raise HTTPException(status_code=500, detail="Failed to load script project")
    return success_envelope({"script": _serialize_project(reloaded), "job": queue_meta}, status_code=status.HTTP_202_ACCEPTED)


@router.post("/bulletin/weekly", status_code=status.HTTP_202_ACCEPTED)
async def generate_weekly_bulletin(
    payload: BulletinRequest,
    geo: str = Query(default="ALL"),
    category: str = Query(default="all"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*VIEW_ROLES)),
):
    selected_articles = await script_studio_service.select_bulletin_articles(
        db,
        since=datetime.utcnow() - timedelta(days=7),
        geo=geo,
        category=category,
        desks=payload.desks,
        max_items=payload.max_items,
    )
    if not selected_articles:
        raise HTTPException(status_code=400, detail="No eligible news items found for weekly bulletin window")

    params_json = {
        "max_items": payload.max_items,
        "duration_minutes": payload.duration_minutes,
        "desks": payload.desks,
        "language": payload.language,
        "tone": payload.tone,
        "geo": geo,
        "category": category,
        "period_hours": 24 * 7,
        "selected_article_ids": [row.id for row in selected_articles],
    }
    project = await script_repository.create_project(
        db,
        project_type=ScriptProjectType.bulletin_weekly,
        title=f"Weekly Bulletin - W{datetime.utcnow():%V}-{datetime.utcnow():%Y}",
        params_json=params_json,
        created_by=current_user.username,
    )
    await audit_service.log_action(
        db,
        action="script_project_create",
        entity_type="script_project",
        entity_id=project.id,
        actor=current_user,
        details={"source": "bulletin_weekly", "selected_items": len(selected_articles)},
    )
    queue_meta = await _queue_script_generation(db=db, script_id=project.id, actor=current_user)
    reloaded = await script_repository.get_project_by_id(db, project.id)
    if not reloaded:
        raise HTTPException(status_code=500, detail="Failed to load script project")
    return success_envelope({"script": _serialize_project(reloaded), "job": queue_meta}, status_code=status.HTTP_202_ACCEPTED)


@router.get("/{script_id}")
async def get_script_project(
    script_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(*VIEW_ROLES)),
):
    project = await script_repository.get_project_by_id(db, script_id)
    if not project:
        raise HTTPException(status_code=404, detail="Script project not found")
    return success_envelope(_serialize_project(project))


@router.get("/{script_id}/outputs")
async def list_script_outputs(
    script_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(*VIEW_ROLES)),
):
    project = await script_repository.get_project_by_id(db, script_id)
    if not project:
        raise HTTPException(status_code=404, detail="Script project not found")
    outputs = await script_repository.list_outputs(db, script_id)
    return success_envelope([_serialize_output(output) for output in outputs])


@router.post("/{script_id}/approve")
async def approve_script_project(
    script_id: int,
    payload: ScriptDecisionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*CHIEF_ROLES)),
):
    _assert_chief_permission(current_user)
    project = await script_repository.get_project_by_id(db, script_id)
    if not project:
        raise HTTPException(status_code=404, detail="Script project not found")
    if project.status == ScriptProjectStatus.approved:
        return success_envelope(_serialize_project(project))
    if project.status != ScriptProjectStatus.ready_for_review:
        raise HTTPException(status_code=409, detail="Script must be ready_for_review before approval")

    project.status = ScriptProjectStatus.approved
    project.updated_by = current_user.username
    await audit_service.log_action(
        db,
        action="script_project_approve",
        entity_type="script_project",
        entity_id=project.id,
        actor=current_user,
        reason=(payload.reason or "").strip() or None,
        from_state=ScriptProjectStatus.ready_for_review.value,
        to_state=ScriptProjectStatus.approved.value,
    )
    await db.commit()
    reloaded = await script_repository.get_project_by_id(db, script_id)
    if not reloaded:
        raise HTTPException(status_code=500, detail="Failed to load script project")
    return success_envelope(_serialize_project(reloaded))


@router.post("/{script_id}/reject")
async def reject_script_project(
    script_id: int,
    payload: ScriptDecisionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*CHIEF_ROLES)),
):
    _assert_chief_permission(current_user)
    reason_value = (payload.reason or "").strip()
    if not reason_value:
        raise HTTPException(status_code=400, detail="Reject reason is required")

    project = await script_repository.get_project_by_id(db, script_id)
    if not project:
        raise HTTPException(status_code=404, detail="Script project not found")
    if project.status == ScriptProjectStatus.rejected:
        return success_envelope(_serialize_project(project))
    if project.status != ScriptProjectStatus.ready_for_review:
        raise HTTPException(status_code=409, detail="Script must be ready_for_review before rejection")

    project.status = ScriptProjectStatus.rejected
    project.updated_by = current_user.username
    await audit_service.log_action(
        db,
        action="script_project_reject",
        entity_type="script_project",
        entity_id=project.id,
        actor=current_user,
        reason=reason_value,
        from_state=ScriptProjectStatus.ready_for_review.value,
        to_state=ScriptProjectStatus.rejected.value,
    )
    await db.commit()
    reloaded = await script_repository.get_project_by_id(db, script_id)
    if not reloaded:
        raise HTTPException(status_code=500, detail="Failed to load script project")
    return success_envelope(_serialize_project(reloaded))


def _safe_article_title(article: Article) -> str:
    return (article.title_ar or article.original_title or "").strip() or f"Article #{article.id}"
