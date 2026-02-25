from __future__ import annotations

import hashlib
import json
from collections.abc import Awaitable, Callable
from typing import Any

from app.core.database import async_session
from app.core.logging import get_logger
from app.models import JobRun
from app.repositories.task_idempotency_repository import task_idempotency_repository

logger = get_logger("services.task_execution")


def _stable_payload(payload: dict[str, Any]) -> dict[str, Any]:
    volatile_keys = {"requested_at", "enqueued_at", "request_id", "correlation_id"}
    return {key: value for key, value in payload.items() if key not in volatile_keys}


def build_task_idempotency_key(
    *,
    task_name: str,
    entity_id: str | None,
    payload: dict[str, Any],
    explicit: str | None = None,
) -> str:
    if explicit:
        return explicit[:190]
    stable_payload = _stable_payload(payload)
    digest = hashlib.sha1(
        json.dumps(stable_payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()[:24]
    base = f"{task_name}:{entity_id or '-'}:{digest}"
    return base[:190]


async def execute_with_task_idempotency(
    *,
    job: JobRun,
    task_name: str,
    runner: Callable[[], Awaitable[dict[str, Any]]],
) -> dict[str, Any]:
    payload = (job.payload_json or {}) if isinstance(job.payload_json, dict) else {}
    idempotency_key = build_task_idempotency_key(
        task_name=task_name,
        entity_id=job.entity_id,
        payload=payload,
        explicit=str(payload.get("idempotency_key") or "").strip() or None,
    )

    async with async_session() as db:
        state, row = await task_idempotency_repository.acquire(
            db,
            idempotency_key=idempotency_key,
            task_name=task_name,
            job_id=str(job.id),
        )
        await db.commit()

    if state == "completed":
        logger.info(
            "task_idempotency_reused_result",
            task_name=task_name,
            job_id=str(job.id),
            idempotency_key=idempotency_key,
        )
        result = row.result_json or {}
        return {
            **result,
            "idempotency": {"status": "completed_reused", "key": idempotency_key},
        }

    if state == "running":
        logger.info(
            "task_idempotency_skip_running",
            task_name=task_name,
            job_id=str(job.id),
            idempotency_key=idempotency_key,
            owner_job_id=row.first_job_id,
        )
        return {
            "idempotency": {
                "status": "running_skip",
                "key": idempotency_key,
                "owner_job_id": row.first_job_id,
            }
        }

    try:
        result = await runner()
    except Exception as exc:  # noqa: BLE001
        async with async_session() as db:
            await task_idempotency_repository.mark_failed(
                db,
                idempotency_key=idempotency_key,
                error=str(exc),
                job_id=str(job.id),
            )
            await db.commit()
        raise

    async with async_session() as db:
        await task_idempotency_repository.mark_completed(
            db,
            idempotency_key=idempotency_key,
            result_json=result,
            job_id=str(job.id),
        )
        await db.commit()

    return {
        **result,
        "idempotency": {"status": "completed", "key": idempotency_key},
    }
