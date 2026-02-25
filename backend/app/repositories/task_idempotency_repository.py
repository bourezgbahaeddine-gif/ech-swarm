from __future__ import annotations

from datetime import datetime
from typing import Literal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import TaskIdempotencyKey


AcquireState = Literal["acquired", "running", "completed"]


class TaskIdempotencyRepository:
    async def get(self, db: AsyncSession, idempotency_key: str) -> TaskIdempotencyKey | None:
        row = await db.execute(
            select(TaskIdempotencyKey).where(TaskIdempotencyKey.idempotency_key == idempotency_key)
        )
        return row.scalar_one_or_none()

    async def start(
        self,
        db: AsyncSession,
        *,
        idempotency_key: str,
        task_name: str,
        job_id: str | None,
    ) -> TaskIdempotencyKey:
        row = TaskIdempotencyKey(
            idempotency_key=idempotency_key,
            task_name=task_name,
            status="running",
            first_job_id=job_id,
            last_job_id=job_id,
        )
        db.add(row)
        await db.flush()
        return row

    async def acquire(
        self,
        db: AsyncSession,
        *,
        idempotency_key: str,
        task_name: str,
        job_id: str | None,
    ) -> tuple[AcquireState, TaskIdempotencyKey]:
        existing = await self.get(db, idempotency_key)
        if existing is None:
            try:
                created = await self.start(
                    db,
                    idempotency_key=idempotency_key,
                    task_name=task_name,
                    job_id=job_id,
                )
                return "acquired", created
            except IntegrityError:
                await db.rollback()
                existing = await self.get(db, idempotency_key)
                if existing is None:
                    raise

        existing.last_job_id = job_id
        existing.updated_at = datetime.utcnow()

        if existing.status == "completed":
            await db.flush()
            return "completed", existing

        if existing.status == "running":
            # Allow retries for the same job to continue execution.
            if (existing.first_job_id and existing.first_job_id == job_id) or (
                existing.last_job_id and existing.last_job_id == job_id
            ):
                await db.flush()
                return "acquired", existing
            await db.flush()
            return "running", existing

        # failed -> reacquire and retry
        existing.status = "running"
        existing.error = None
        if not existing.first_job_id:
            existing.first_job_id = job_id
        await db.flush()
        return "acquired", existing

    async def mark_completed(
        self,
        db: AsyncSession,
        *,
        idempotency_key: str,
        result_json: dict,
        job_id: str | None,
    ) -> None:
        row = await self.get(db, idempotency_key)
        if not row:
            return
        row.status = "completed"
        row.result_json = result_json
        row.error = None
        row.last_job_id = job_id
        row.updated_at = datetime.utcnow()
        await db.flush()

    async def mark_failed(
        self,
        db: AsyncSession,
        *,
        idempotency_key: str,
        error: str,
        job_id: str | None,
    ) -> None:
        row = await self.get(db, idempotency_key)
        if not row:
            return
        row.status = "failed"
        row.error = (error or "")[:4000]
        row.last_job_id = job_id
        row.updated_at = datetime.utcnow()
        await db.flush()


task_idempotency_repository = TaskIdempotencyRepository()
