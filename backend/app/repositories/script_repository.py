from __future__ import annotations

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import ScriptOutput, ScriptOutputFormat, ScriptProject, ScriptProjectStatus, ScriptProjectType


class ScriptRepository:
    async def create_project(
        self,
        db: AsyncSession,
        *,
        project_type: ScriptProjectType,
        title: str,
        params_json: dict,
        created_by: str | None,
        story_id: int | None = None,
        article_id: int | None = None,
    ) -> ScriptProject:
        project = ScriptProject(
            type=project_type,
            status=ScriptProjectStatus.new,
            story_id=story_id,
            article_id=article_id,
            title=title,
            params_json=params_json,
            created_by=created_by,
            updated_by=created_by,
        )
        db.add(project)
        await db.flush()
        await db.refresh(project)
        return project

    async def get_project_by_id(self, db: AsyncSession, project_id: int) -> ScriptProject | None:
        row = await db.execute(
            select(ScriptProject)
            .options(selectinload(ScriptProject.outputs))
            .where(ScriptProject.id == project_id)
            .execution_options(populate_existing=True)
        )
        return row.scalar_one_or_none()

    async def list_projects(
        self,
        db: AsyncSession,
        *,
        limit: int = 100,
        project_type: ScriptProjectType | None = None,
        status: ScriptProjectStatus | None = None,
    ) -> list[ScriptProject]:
        stmt = select(ScriptProject).options(selectinload(ScriptProject.outputs))
        if project_type:
            stmt = stmt.where(ScriptProject.type == project_type)
        if status:
            stmt = stmt.where(ScriptProject.status == status)
        stmt = stmt.order_by(desc(ScriptProject.updated_at), desc(ScriptProject.id)).limit(max(1, min(limit, 200)))
        rows = await db.execute(stmt)
        return list(rows.scalars().all())

    async def get_next_output_version(self, db: AsyncSession, script_id: int) -> int:
        row = await db.execute(select(func.coalesce(func.max(ScriptOutput.version), 0)).where(ScriptOutput.script_id == script_id))
        return int(row.scalar_one() or 0) + 1

    async def create_output(
        self,
        db: AsyncSession,
        *,
        script_id: int,
        version: int,
        content_json: dict | None,
        content_text: str | None,
        output_format: ScriptOutputFormat,
        quality_issues_json: list[dict],
    ) -> ScriptOutput:
        output = ScriptOutput(
            script_id=script_id,
            version=version,
            content_json=content_json,
            content_text=content_text,
            format=output_format,
            quality_issues_json=quality_issues_json,
        )
        db.add(output)
        await db.flush()
        await db.refresh(output)
        return output

    async def list_outputs(self, db: AsyncSession, script_id: int) -> list[ScriptOutput]:
        rows = await db.execute(
            select(ScriptOutput)
            .where(ScriptOutput.script_id == script_id)
            .order_by(desc(ScriptOutput.version), desc(ScriptOutput.id))
        )
        return list(rows.scalars().all())


script_repository = ScriptRepository()
