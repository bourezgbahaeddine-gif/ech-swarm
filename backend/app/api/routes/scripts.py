from __future__ import annotations

import difflib
import json
from datetime import datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.rbac import require_roles
from app.api.envelope import success_envelope
from app.core.database import get_db
from app.models.job_queue import JobRun
from app.models.news import Article
from app.models.script import ScriptOutput, ScriptProjectStatus, ScriptProjectType
from app.models.story import Story
from app.models.user import User, UserRole
from app.repositories.script_repository import script_repository
from app.services.audit_service import audit_service
from app.services.job_queue_service import job_queue_service
from app.services.script_studio_service import script_studio_service
from app.services.script_video_workspace_service import script_video_workspace_service

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
    video_profile: str | None = Field(default=None, max_length=64)
    target_platform: str | None = Field(default=None, max_length=64)
    editorial_objective: str | None = Field(default=None, max_length=64)


class ScriptFromStoryRequest(BaseModel):
    type: Literal["story_script", "video_script"]
    tone: str = Field(default="neutral", max_length=50)
    length_seconds: int = Field(default=90, ge=20, le=1200)
    language: str = Field(default="ar", max_length=8)
    style_constraints: list[str] = Field(default_factory=list)
    video_profile: str | None = Field(default=None, max_length=64)
    target_platform: str | None = Field(default=None, max_length=64)
    editorial_objective: str | None = Field(default=None, max_length=64)


class BulletinRequest(BaseModel):
    max_items: int = Field(default=8, ge=1, le=20)
    duration_minutes: int = Field(default=5, ge=1, le=30)
    desks: list[str] = Field(default_factory=list)
    language: str = Field(default="ar", max_length=8)
    tone: str = Field(default="neutral", max_length=50)


class ScriptDecisionRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=2000)


class ScriptRegenerateRequest(BaseModel):
    tone: str | None = Field(default=None, max_length=50)
    length_seconds: int | None = Field(default=None, ge=20, le=1200)
    language: str | None = Field(default=None, max_length=8)
    style_constraints: list[str] | None = None
    max_items: int | None = Field(default=None, ge=1, le=30)
    duration_minutes: int | None = Field(default=None, ge=1, le=60)
    desks: list[str] | None = None
    video_profile: str | None = Field(default=None, max_length=64)
    target_platform: str | None = Field(default=None, max_length=64)
    editorial_objective: str | None = Field(default=None, max_length=64)


class ScriptDuplicateVersionRequest(BaseModel):
    source_version: int | None = Field(default=None, ge=1)


class VideoWorkspaceUpdateRequest(BaseModel):
    video_profile: str | None = Field(default=None, max_length=64)
    target_platform: str | None = Field(default=None, max_length=64)
    editorial_objective: str | None = Field(default=None, max_length=64)
    pace_notes: str | None = Field(default=None, max_length=4000)
    hook: str | None = Field(default=None, max_length=4000)
    closing: str | None = Field(default=None, max_length=4000)
    vo_script: str | None = Field(default=None, max_length=40000)
    hook_strength: float | None = Field(default=None, ge=0, le=1)


class VideoScenePatchRequest(BaseModel):
    duration_s: int | None = Field(default=None, ge=1, le=600)
    scene_type: str | None = Field(default=None, max_length=64)
    priority: str | None = Field(default=None, max_length=32)
    visual: str | None = Field(default=None, max_length=4000)
    on_screen_text: str | None = Field(default=None, max_length=2000)
    vo_line: str | None = Field(default=None, max_length=4000)
    asset_status: str | None = Field(default=None, max_length=32)
    source_reference: str | None = Field(default=None, max_length=1024)
    locked: bool | None = None


class VideoSceneAddRequest(BaseModel):
    insert_after: int | None = Field(default=None, ge=1)
    duration_s: int = Field(default=5, ge=1, le=600)
    scene_type: str = Field(default="body", max_length=64)
    priority: str = Field(default="medium", max_length=32)
    visual: str = Field(default="", max_length=4000)
    on_screen_text: str = Field(default="", max_length=2000)
    vo_line: str = Field(default="", max_length=4000)
    asset_status: str = Field(default="missing", max_length=32)
    source_reference: str | None = Field(default=None, max_length=1024)


class VideoSceneSplitRequest(BaseModel):
    split_duration_s: int = Field(..., ge=1, le=600)


class VideoSceneMergeRequest(BaseModel):
    source_idx: int = Field(..., ge=1)
    target_idx: int = Field(..., ge=1)


class VideoSceneReorderRequest(BaseModel):
    ordered_scene_indices: list[int] = Field(default_factory=list, min_length=1)


class VideoCaptionsUpdateRequest(BaseModel):
    captions_lines: list[dict] = Field(default_factory=list)


class VideoDeliveryUpdateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=1024)
    thumbnail_line: str | None = Field(default=None, max_length=2000)
    social_copy: str | None = Field(default=None, max_length=8000)
    shot_list: list[str] | None = None
    source_references: list[str] | None = None
    status: str | None = Field(default=None, max_length=64)


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
    latest_output = outputs[0] if outputs else None
    latest_quality_issues = (
        latest_output.quality_issues_json
        if latest_output and isinstance(latest_output.quality_issues_json, list)
        else []
    )
    latest_blockers = sum(
        1
        for issue in latest_quality_issues
        if isinstance(issue, dict) and str(issue.get("severity", "")).lower() == "blocker"
    )
    latest_warnings = sum(
        1
        for issue in latest_quality_issues
        if isinstance(issue, dict) and str(issue.get("severity", "")).lower() in {"warn", "warning"}
    )
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
        "output_count": len(outputs),
        "latest_version": latest_output.version if latest_output else None,
        "latest_output_at": latest_output.created_at.isoformat() if latest_output and latest_output.created_at else None,
        "latest_quality_blockers": latest_blockers,
        "latest_quality_warnings": latest_warnings,
        "video_workspace": script_video_workspace_service.workspace_summary(project),
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


def _to_diff_text(output: ScriptOutput) -> str:
    if output.content_text:
        return output.content_text
    if isinstance(output.content_json, dict):
        return json.dumps(output.content_json, ensure_ascii=False, sort_keys=True, indent=2)
    return ""


def _require_video_project(project) -> None:
    if project.type != ScriptProjectType.video_script:
        raise HTTPException(status_code=409, detail="Video workspace actions are only available for video scripts")


def _build_recovery_hints(error_text: str) -> list[dict]:
    raw = (error_text or "").strip()
    lowered = raw.lower()
    hints: list[dict] = []

    if not raw:
        return [
            {
                "code": "generic_retry",
                "severity": "warn",
                "title": "تعذر تشخيص سبب الفشل",
                "action": "أعد التوليد الآن. إذا تكرر الفشل، غيّر النبرة إلى `neutral` وقلّل المدة.",
            }
        ]

    if any(token in lowered for token in ("429", "rate", "quota", "resource_exhausted")):
        hints.append(
            {
                "code": "provider_rate_limit",
                "severity": "warn",
                "title": "تم بلوغ حد مزود الذكاء الاصطناعي",
                "action": "أعد المحاولة بعد دقائق، أو خفّض طول السكربت قبل إعادة التوليد.",
            }
        )
    if any(token in lowered for token in ("timeout", "timed out", "deadline")):
        hints.append(
            {
                "code": "timeout",
                "severity": "warn",
                "title": "انتهت مهلة التنفيذ",
                "action": "أعد التوليد. إذا استمر، قلّل `max_items` أو `length_seconds`.",
            }
        )
    if any(token in lowered for token in ("json", "parse", "validation", "schema")):
        hints.append(
            {
                "code": "output_schema",
                "severity": "info",
                "title": "مخرجات غير مطابقة للبنية المتوقعة",
                "action": "أعد التوليد بنبرة `neutral` وقيود أسلوب أقل.",
            }
        )
    if any(token in lowered for token in ("not_found", "source", "article", "story")):
        hints.append(
            {
                "code": "missing_source",
                "severity": "blocker",
                "title": "مصدر السكربت غير متاح",
                "action": "تحقق أن الخبر/القصة ما زالت موجودة ثم أعد المحاولة.",
            }
        )

    if not hints:
        hints.append(
            {
                "code": "generic_retry",
                "severity": "warn",
                "title": "فشل غير مصنف",
                "action": "أعد التوليد مباشرة. إذا تكرر، أنشئ نسخة جديدة ثم قارن النتائج.",
            }
        )

    return hints


async def _queue_script_generation(
    *,
    db: AsyncSession,
    script_id: int,
    actor: User,
) -> dict:
    allowed, depth, limit_depth = await job_queue_service.check_backpressure(SCRIPT_QUEUE_NAME)
    if not allowed:
        raise job_queue_service.backpressure_exception(
            queue_name=SCRIPT_QUEUE_NAME,
            current_depth=depth,
            depth_limit=limit_depth,
            message="Script generation queue overloaded. Retry shortly.",
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
        "video_profile": payload.video_profile,
        "target_platform": payload.target_platform,
        "editorial_objective": payload.editorial_objective,
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
        "video_profile": payload.video_profile,
        "target_platform": payload.target_platform,
        "editorial_objective": payload.editorial_objective,
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


@router.post("/{script_id}/regenerate", status_code=status.HTTP_202_ACCEPTED)
async def regenerate_script_project(
    script_id: int,
    payload: ScriptRegenerateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*VIEW_ROLES)),
):
    project = await script_repository.get_project_by_id(db, script_id)
    if not project:
        raise HTTPException(status_code=404, detail="Script project not found")

    incoming = payload.model_dump(exclude_none=True)
    params_json = dict(project.params_json or {})
    params_json.update(incoming)
    project.params_json = params_json
    project.updated_by = current_user.username
    await audit_service.log_action(
        db,
        action="script_project_regenerate_requested",
        entity_type="script_project",
        entity_id=project.id,
        actor=current_user,
        details={"params_override": incoming},
    )
    await db.commit()

    queue_meta = await _queue_script_generation(db=db, script_id=script_id, actor=current_user)
    reloaded = await script_repository.get_project_by_id(db, script_id)
    if not reloaded:
        raise HTTPException(status_code=500, detail="Failed to load script project")
    return success_envelope(
        {"script": _serialize_project(reloaded), "job": queue_meta},
        status_code=status.HTTP_202_ACCEPTED,
    )


@router.post("/{script_id}/duplicate-version")
async def duplicate_script_output_version(
    script_id: int,
    payload: ScriptDuplicateVersionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*VIEW_ROLES)),
):
    project = await script_repository.get_project_by_id(db, script_id)
    if not project:
        raise HTTPException(status_code=404, detail="Script project not found")

    outputs = await script_repository.list_outputs(db, script_id)
    if not outputs:
        raise HTTPException(status_code=409, detail="No output available to duplicate")

    by_version = {row.version: row for row in outputs}
    source_output = outputs[0]
    if payload.source_version:
        selected_output = by_version.get(payload.source_version)
        if not selected_output:
            raise HTTPException(status_code=404, detail="Source version not found")
        source_output = selected_output

    target_version = await script_repository.get_next_output_version(db, script_id)
    created = await script_repository.create_output(
        db,
        script_id=script_id,
        version=target_version,
        content_json=source_output.content_json if isinstance(source_output.content_json, dict) else source_output.content_json,
        content_text=source_output.content_text,
        output_format=source_output.format,
        quality_issues_json=source_output.quality_issues_json if isinstance(source_output.quality_issues_json, list) else [],
    )
    project.status = ScriptProjectStatus.ready_for_review
    project.updated_by = current_user.username
    await audit_service.log_action(
        db,
        action="script_output_duplicate_version",
        entity_type="script_project",
        entity_id=project.id,
        actor=current_user,
        details={
            "source_version": source_output.version,
            "target_version": target_version,
        },
    )
    await db.commit()

    reloaded = await script_repository.get_project_by_id(db, script_id)
    return success_envelope(
        {
            "script": _serialize_project(reloaded) if reloaded else None,
            "output": _serialize_output(created),
        }
    )


@router.get("/{script_id}/versions/diff")
async def script_versions_diff(
    script_id: int,
    from_version: int = Query(..., ge=1),
    to_version: int = Query(..., ge=1),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(*VIEW_ROLES)),
):
    project = await script_repository.get_project_by_id(db, script_id)
    if not project:
        raise HTTPException(status_code=404, detail="Script project not found")

    outputs = await script_repository.list_outputs(db, script_id)
    by_version = {row.version: row for row in outputs}
    base = by_version.get(from_version)
    target = by_version.get(to_version)
    if not base or not target:
        raise HTTPException(status_code=404, detail="Requested versions not found")

    base_text = _to_diff_text(base)
    target_text = _to_diff_text(target)
    diff_lines = list(
        difflib.unified_diff(
            base_text.splitlines(),
            target_text.splitlines(),
            fromfile=f"v{from_version}",
            tofile=f"v{to_version}",
            lineterm="",
        )
    )
    added = sum(1 for line in diff_lines if line.startswith("+") and not line.startswith("+++"))
    removed = sum(1 for line in diff_lines if line.startswith("-") and not line.startswith("---"))

    return success_envelope(
        {
            "script_id": script_id,
            "from_version": from_version,
            "to_version": to_version,
            "from_chars": len(base_text),
            "to_chars": len(target_text),
            "added_lines": added,
            "removed_lines": removed,
            "diff_lines": diff_lines,
        }
    )


@router.get("/{script_id}/recovery-hints")
async def script_recovery_hints(
    script_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(*VIEW_ROLES)),
):
    project = await script_repository.get_project_by_id(db, script_id)
    if not project:
        raise HTTPException(status_code=404, detail="Script project not found")

    latest_job_row = await db.execute(
        select(JobRun)
        .where(
            JobRun.job_type == SCRIPT_JOB_TYPE,
            JobRun.entity_id == str(script_id),
        )
        .order_by(desc(JobRun.updated_at), desc(JobRun.created_at))
        .limit(1)
    )
    latest_job = latest_job_row.scalar_one_or_none()

    latest_failed_row = await db.execute(
        select(JobRun)
        .where(
            JobRun.job_type == SCRIPT_JOB_TYPE,
            JobRun.entity_id == str(script_id),
            JobRun.status.in_(("failed", "dead_lettered")),
        )
        .order_by(desc(JobRun.updated_at), desc(JobRun.created_at))
        .limit(1)
    )
    latest_failed = latest_failed_row.scalar_one_or_none()
    error_text = (latest_failed.error if latest_failed else "") or ""

    return success_envelope(
        {
            "script_id": script_id,
            "project_status": project.status.value if project.status else None,
            "can_retry_now": True,
            "latest_job": (
                {
                    "id": str(latest_job.id),
                    "status": latest_job.status,
                    "error": latest_job.error,
                    "updated_at": latest_job.updated_at.isoformat() if latest_job.updated_at else None,
                }
                if latest_job
                else None
            ),
            "latest_failed_job": (
                {
                    "id": str(latest_failed.id),
                    "status": latest_failed.status,
                    "error": latest_failed.error,
                    "updated_at": latest_failed.updated_at.isoformat() if latest_failed.updated_at else None,
                }
                if latest_failed
                else None
            ),
            "hints": _build_recovery_hints(error_text),
        }
    )


@router.patch("/{script_id}/video")
async def update_video_workspace(
    script_id: int,
    payload: VideoWorkspaceUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*VIEW_ROLES)),
):
    project = await script_repository.get_project_by_id(db, script_id)
    if not project:
        raise HTTPException(status_code=404, detail="Script project not found")
    _require_video_project(project)

    content = script_video_workspace_service.payload_from_project(project)
    updates = payload.model_dump(exclude_none=True)
    content.update(updates)
    updated = await script_video_workspace_service.save_manual_video_version(
        db,
        project=project,
        content_json=content,
        actor_username=current_user.username,
        action="script_video_workspace_update",
        details={"fields": sorted(updates.keys())},
    )
    return success_envelope(_serialize_project(updated))


@router.patch("/{script_id}/scenes/{scene_idx}")
async def patch_video_scene(
    script_id: int,
    scene_idx: int,
    payload: VideoScenePatchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*VIEW_ROLES)),
):
    project = await script_repository.get_project_by_id(db, script_id)
    if not project:
        raise HTTPException(status_code=404, detail="Script project not found")
    _require_video_project(project)

    content = script_video_workspace_service.payload_from_project(project)
    scenes = content.get("scenes") or []
    if scene_idx < 1 or scene_idx > len(scenes):
        raise HTTPException(status_code=404, detail="Scene not found")
    scene = dict(scenes[scene_idx - 1])
    updates = payload.model_dump(exclude_none=True)
    scene.update(updates)
    scenes[scene_idx - 1] = scene
    content["scenes"] = scenes
    updated = await script_video_workspace_service.save_manual_video_version(
        db,
        project=project,
        content_json=content,
        actor_username=current_user.username,
        action="script_video_scene_update",
        details={"scene_idx": scene_idx, "fields": sorted(updates.keys())},
    )
    return success_envelope(_serialize_project(updated))


@router.post("/{script_id}/scenes")
async def add_video_scene(
    script_id: int,
    payload: VideoSceneAddRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*VIEW_ROLES)),
):
    project = await script_repository.get_project_by_id(db, script_id)
    if not project:
        raise HTTPException(status_code=404, detail="Script project not found")
    _require_video_project(project)

    content = script_video_workspace_service.payload_from_project(project)
    scenes = list(content.get("scenes") or [])
    new_scene = {
        "idx": 0,
        "duration_s": payload.duration_s,
        "scene_type": payload.scene_type,
        "priority": payload.priority,
        "visual": payload.visual,
        "on_screen_text": payload.on_screen_text,
        "vo_line": payload.vo_line,
        "asset_status": payload.asset_status,
        "source_reference": payload.source_reference,
        "locked": False,
    }
    insert_at = len(scenes)
    if payload.insert_after and payload.insert_after <= len(scenes):
        insert_at = payload.insert_after
    scenes.insert(insert_at, new_scene)
    content["scenes"] = scenes
    updated = await script_video_workspace_service.save_manual_video_version(
        db,
        project=project,
        content_json=content,
        actor_username=current_user.username,
        action="script_video_scene_add",
        details={"insert_after": payload.insert_after},
    )
    return success_envelope(_serialize_project(updated))


@router.delete("/{script_id}/scenes/{scene_idx}")
async def delete_video_scene(
    script_id: int,
    scene_idx: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*VIEW_ROLES)),
):
    project = await script_repository.get_project_by_id(db, script_id)
    if not project:
        raise HTTPException(status_code=404, detail="Script project not found")
    _require_video_project(project)
    content = script_video_workspace_service.payload_from_project(project)
    scenes = list(content.get("scenes") or [])
    if scene_idx < 1 or scene_idx > len(scenes):
        raise HTTPException(status_code=404, detail="Scene not found")
    scenes.pop(scene_idx - 1)
    content["scenes"] = scenes
    updated = await script_video_workspace_service.save_manual_video_version(
        db,
        project=project,
        content_json=content,
        actor_username=current_user.username,
        action="script_video_scene_delete",
        details={"scene_idx": scene_idx},
    )
    return success_envelope(_serialize_project(updated))


@router.post("/{script_id}/scenes/reorder")
async def reorder_video_scenes(
    script_id: int,
    payload: VideoSceneReorderRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*VIEW_ROLES)),
):
    project = await script_repository.get_project_by_id(db, script_id)
    if not project:
        raise HTTPException(status_code=404, detail="Script project not found")
    _require_video_project(project)
    content = script_video_workspace_service.payload_from_project(project)
    scenes = list(content.get("scenes") or [])
    current_ids = [int(scene.get("idx") or index + 1) for index, scene in enumerate(scenes)]
    if sorted(current_ids) != sorted(payload.ordered_scene_indices):
        raise HTTPException(status_code=400, detail="ordered_scene_indices must include all current scene indices exactly once")
    by_idx = {int(scene.get("idx") or index + 1): scene for index, scene in enumerate(scenes)}
    content["scenes"] = [by_idx[idx] for idx in payload.ordered_scene_indices]
    updated = await script_video_workspace_service.save_manual_video_version(
        db,
        project=project,
        content_json=content,
        actor_username=current_user.username,
        action="script_video_scene_reorder",
        details={"ordered_scene_indices": payload.ordered_scene_indices},
    )
    return success_envelope(_serialize_project(updated))


@router.post("/{script_id}/scenes/{scene_idx}/split")
async def split_video_scene(
    script_id: int,
    scene_idx: int,
    payload: VideoSceneSplitRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*VIEW_ROLES)),
):
    project = await script_repository.get_project_by_id(db, script_id)
    if not project:
        raise HTTPException(status_code=404, detail="Script project not found")
    _require_video_project(project)
    content = script_video_workspace_service.payload_from_project(project)
    scenes = list(content.get("scenes") or [])
    if scene_idx < 1 or scene_idx > len(scenes):
        raise HTTPException(status_code=404, detail="Scene not found")
    scene = dict(scenes[scene_idx - 1])
    duration = int(scene.get("duration_s") or 0)
    if payload.split_duration_s >= duration:
        raise HTTPException(status_code=400, detail="split_duration_s must be smaller than scene duration")
    scene["duration_s"] = payload.split_duration_s
    second = dict(scene)
    second["duration_s"] = duration - payload.split_duration_s
    second["scene_type"] = "body"
    scenes[scene_idx - 1] = scene
    scenes.insert(scene_idx, second)
    content["scenes"] = scenes
    updated = await script_video_workspace_service.save_manual_video_version(
        db,
        project=project,
        content_json=content,
        actor_username=current_user.username,
        action="script_video_scene_split",
        details={"scene_idx": scene_idx, "split_duration_s": payload.split_duration_s},
    )
    return success_envelope(_serialize_project(updated))


@router.post("/{script_id}/scenes/merge")
async def merge_video_scenes(
    script_id: int,
    payload: VideoSceneMergeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*VIEW_ROLES)),
):
    project = await script_repository.get_project_by_id(db, script_id)
    if not project:
        raise HTTPException(status_code=404, detail="Script project not found")
    _require_video_project(project)
    content = script_video_workspace_service.payload_from_project(project)
    scenes = list(content.get("scenes") or [])
    if payload.source_idx == payload.target_idx:
        raise HTTPException(status_code=400, detail="source_idx and target_idx must differ")
    if min(payload.source_idx, payload.target_idx) < 1 or max(payload.source_idx, payload.target_idx) > len(scenes):
        raise HTTPException(status_code=404, detail="Scene not found")
    source = dict(scenes[payload.source_idx - 1])
    target = dict(scenes[payload.target_idx - 1])
    target["duration_s"] = int(target.get("duration_s") or 0) + int(source.get("duration_s") or 0)
    target["vo_line"] = " ".join(filter(None, [str(target.get("vo_line") or "").strip(), str(source.get("vo_line") or "").strip()])).strip()
    target["on_screen_text"] = " | ".join(
        filter(None, [str(target.get("on_screen_text") or "").strip(), str(source.get("on_screen_text") or "").strip()])
    ).strip()
    target["visual"] = " + ".join(filter(None, [str(target.get("visual") or "").strip(), str(source.get("visual") or "").strip()])).strip()
    scenes[payload.target_idx - 1] = target
    scenes.pop(payload.source_idx - 1)
    content["scenes"] = scenes
    updated = await script_video_workspace_service.save_manual_video_version(
        db,
        project=project,
        content_json=content,
        actor_username=current_user.username,
        action="script_video_scene_merge",
        details={"source_idx": payload.source_idx, "target_idx": payload.target_idx},
    )
    return success_envelope(_serialize_project(updated))


@router.post("/{script_id}/scenes/{scene_idx}/lock")
async def lock_video_scene(
    script_id: int,
    scene_idx: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*VIEW_ROLES)),
):
    return await patch_video_scene(
        script_id=script_id,
        scene_idx=scene_idx,
        payload=VideoScenePatchRequest(locked=True),
        db=db,
        current_user=current_user,
    )


@router.post("/{script_id}/scenes/{scene_idx}/unlock")
async def unlock_video_scene(
    script_id: int,
    scene_idx: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*VIEW_ROLES)),
):
    return await patch_video_scene(
        script_id=script_id,
        scene_idx=scene_idx,
        payload=VideoScenePatchRequest(locked=False),
        db=db,
        current_user=current_user,
    )


@router.post("/{script_id}/scenes/{scene_idx}/regenerate", status_code=status.HTTP_202_ACCEPTED)
async def regenerate_video_scene(
    script_id: int,
    scene_idx: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*VIEW_ROLES)),
):
    project = await script_repository.get_project_by_id(db, script_id)
    if not project:
        raise HTTPException(status_code=404, detail="Script project not found")
    _require_video_project(project)
    try:
        updated = await script_video_workspace_service.regenerate_single_scene(
            db,
            project=project,
            scene_idx=scene_idx,
            actor_username=current_user.username,
        )
    except ValueError as exc:
        message = "Scene could not be regenerated"
        if str(exc) == "scene_not_found":
            raise HTTPException(status_code=404, detail="Scene not found") from exc
        if str(exc) == "scene_locked":
            raise HTTPException(status_code=409, detail="Scene is locked") from exc
        raise HTTPException(status_code=400, detail=message) from exc
    return success_envelope(_serialize_project(updated), status_code=status.HTTP_202_ACCEPTED)


@router.patch("/{script_id}/captions")
async def update_video_captions(
    script_id: int,
    payload: VideoCaptionsUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*VIEW_ROLES)),
):
    project = await script_repository.get_project_by_id(db, script_id)
    if not project:
        raise HTTPException(status_code=404, detail="Script project not found")
    _require_video_project(project)
    content = script_video_workspace_service.payload_from_project(project)
    content["captions_lines"] = payload.captions_lines
    updated = await script_video_workspace_service.save_manual_video_version(
        db,
        project=project,
        content_json=content,
        actor_username=current_user.username,
        action="script_video_captions_update",
        details={"lines": len(payload.captions_lines)},
    )
    return success_envelope(_serialize_project(updated))


@router.patch("/{script_id}/delivery")
async def update_video_delivery(
    script_id: int,
    payload: VideoDeliveryUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*VIEW_ROLES)),
):
    project = await script_repository.get_project_by_id(db, script_id)
    if not project:
        raise HTTPException(status_code=404, detail="Script project not found")
    _require_video_project(project)
    content = script_video_workspace_service.payload_from_project(project)
    delivery = dict(content.get("delivery") or {})
    for key, value in payload.model_dump(exclude_none=True).items():
        delivery[key] = value
    content["delivery"] = delivery
    updated = await script_video_workspace_service.save_manual_video_version(
        db,
        project=project,
        content_json=content,
        actor_username=current_user.username,
        action="script_video_delivery_update",
        details={"fields": sorted(payload.model_dump(exclude_none=True).keys())},
    )
    return success_envelope(_serialize_project(updated))


@router.post("/{script_id}/delivery/export")
async def export_video_delivery_bundle(
    script_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*VIEW_ROLES)),
):
    project = await script_repository.get_project_by_id(db, script_id)
    if not project:
        raise HTTPException(status_code=404, detail="Script project not found")
    _require_video_project(project)
    bundle = script_video_workspace_service.export_bundle(project)
    await audit_service.log_action(
        db,
        action="script_video_delivery_export",
        entity_type="script_project",
        entity_id=project.id,
        actor=current_user,
        details={"delivery_status": bundle.get("delivery_status")},
    )
    await db.commit()
    return success_envelope(bundle)


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
