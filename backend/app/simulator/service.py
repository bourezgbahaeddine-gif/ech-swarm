"""Audience simulator orchestration service."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from hashlib import sha1

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session
from app.core.logging import get_logger
from app.models import SimJobEvent, SimResult, SimRun
from app.models.user import User
from app.simulator.graph import SimulationGraphRunner
from app.simulator.nodes import SimulationGraphNodes
from app.simulator.state import SimulationState

logger = get_logger("simulator.service")


class AudienceSimulationService:
    def __init__(self):
        self._running_tasks: dict[str, asyncio.Task] = {}

    @staticmethod
    def _normalize_excerpt(value: str | None) -> str:
        return (value or "").strip()[:3000]

    @staticmethod
    def _build_idempotency_key(headline: str, excerpt: str, platform: str, mode: str, actor_id: int | None) -> str:
        raw = f"{headline.strip().lower()}|{excerpt.strip().lower()}|{platform}|{mode}|{actor_id or 0}"
        return sha1(raw.encode("utf-8")).hexdigest()

    async def create_run(
        self,
        db: AsyncSession,
        *,
        headline: str,
        body_excerpt: str | None,
        platform: str,
        mode: str,
        actor: User | None,
        article_id: int | None = None,
        draft_id: int | None = None,
        idempotency_key: str | None = None,
    ) -> SimRun:
        excerpt = self._normalize_excerpt(body_excerpt)
        idem = idempotency_key or self._build_idempotency_key(headline, excerpt, platform, mode, actor.id if actor else None)
        existing_row = await db.execute(
            select(SimRun)
            .where(SimRun.idempotency_key == idem)
            .order_by(SimRun.created_at.desc())
            .limit(1)
        )
        existing = existing_row.scalar_one_or_none()
        if existing and existing.status in {"queued", "running", "completed"}:
            return existing

        run_id = f"SIM-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{abs(hash((headline, platform, mode, datetime.utcnow().isoformat()))) % 10_000_000:07d}"
        run = SimRun(
            run_id=run_id,
            article_id=article_id,
            draft_id=draft_id,
            headline=headline.strip(),
            body_excerpt=excerpt,
            platform=platform,
            mode=mode,
            status="queued",
            created_by_user_id=actor.id if actor else None,
            created_by_username=actor.username if actor else "system",
            idempotency_key=idem,
        )
        db.add(run)
        await db.commit()
        await db.refresh(run)
        return run

    async def start_run_task(self, run_id: str) -> None:
        if run_id in self._running_tasks and not self._running_tasks[run_id].done():
            return
        task = asyncio.create_task(self.execute_run(run_id))
        self._running_tasks[run_id] = task

    async def execute_run(self, run_id: str) -> None:
        async with async_session() as db:
            run_row = await db.execute(select(SimRun).where(SimRun.run_id == run_id))
            run = run_row.scalar_one_or_none()
            if not run:
                return

            run.status = "running"
            await db.commit()
            await self._emit_event(db, run_id, "runner", "started", {"status": "running"})

            async def emit(node: str, event_type: str, payload: dict):
                await self._emit_event(db, run_id, node, event_type, payload)

            nodes = SimulationGraphNodes(emit)
            graph = SimulationGraphRunner(nodes, emit)
            initial_state = SimulationState(
                run_id=run.run_id,
                article_id=run.article_id,
                draft_id=run.draft_id,
                headline=run.headline,
                body_excerpt=run.body_excerpt or "",
                platform=run.platform,  # type: ignore[arg-type]
                mode=run.mode,  # type: ignore[arg-type]
                created_by_username=run.created_by_username,
            )
            try:
                result = await graph.run(initial_state)
                await self._persist_result(db, run, result)
                run.status = "completed"
                run.finished_at = datetime.utcnow()
                run.error = None
                await db.commit()
                await self._emit_event(db, run_id, "runner", "finished", {"status": "completed"})
            except Exception as exc:  # noqa: BLE001
                logger.error("sim_run_failed", run_id=run_id, error=str(exc))
                await db.rollback()
                run_row = await db.execute(select(SimRun).where(SimRun.run_id == run_id))
                failed = run_row.scalar_one_or_none()
                if failed:
                    failed.status = "failed"
                    failed.finished_at = datetime.utcnow()
                    failed.error = str(exc)[:2000]
                    await db.commit()
                await self._emit_event(db, run_id, "runner", "failed", {"status": "failed", "error": str(exc)})

    async def _persist_result(self, db: AsyncSession, run: SimRun, result: SimulationState) -> None:
        existing_row = await db.execute(
            select(SimResult)
            .where(SimResult.run_id == run.run_id)
            .order_by(SimResult.created_at.desc())
            .limit(1)
        )
        existing = existing_row.scalar_one_or_none()
        payload = {
            "risk_score": result.result.risk_score,
            "virality_score": result.result.virality_score,
            "confidence_score": result.result.confidence_score,
            "breakdown_json": self._json_safe(result.result.breakdown.model_dump()),
            "reactions_json": self._json_safe([r.model_dump() for r in result.reactions]),
            "advice_json": self._json_safe(result.advice.model_dump()),
            "red_flags_json": self._json_safe(result.result.red_flags),
        }
        if existing:
            for key, value in payload.items():
                setattr(existing, key, value)
            existing.created_at = datetime.utcnow()
        else:
            db.add(SimResult(run_id=run.run_id, **payload))

    @staticmethod
    def _json_safe(value):
        return json.loads(json.dumps(value, ensure_ascii=False, default=str))

    async def _emit_event(self, db: AsyncSession, run_id: str, node: str, event_type: str, payload: dict) -> None:
        db.add(
            SimJobEvent(
                run_id=run_id,
                node=node,
                event_type=event_type,
                payload_json=self._json_safe(payload or {}),
            )
        )
        await db.commit()

    async def get_run_status(self, db: AsyncSession, run_id: str) -> SimRun | None:
        row = await db.execute(select(SimRun).where(SimRun.run_id == run_id))
        return row.scalar_one_or_none()

    async def get_result(self, db: AsyncSession, run_id: str) -> dict | None:
        row = await db.execute(
            select(SimResult)
            .where(SimResult.run_id == run_id)
            .order_by(desc(SimResult.created_at))
            .limit(1)
        )
        result = row.scalar_one_or_none()
        if not result:
            return None
        run = await self.get_run_status(db, run_id)
        return {
            "run_id": run_id,
            "status": run.status if run else "unknown",
            "headline": run.headline if run else "",
            "platform": run.platform if run else "",
            "mode": run.mode if run else "",
            "risk_score": result.risk_score,
            "virality_score": result.virality_score,
            "confidence_score": result.confidence_score,
            "breakdown": result.breakdown_json or {},
            "reactions": result.reactions_json or [],
            "advice": result.advice_json or {},
            "red_flags": result.red_flags_json or {},
            "policy_level": self._policy_level(result.risk_score, result.red_flags_json or {}),
            "created_at": result.created_at.isoformat(),
        }

    @staticmethod
    def _policy_level(risk_score: float, red_flags: dict) -> str:
        if risk_score >= 8.0 or float((red_flags or {}).get("legal", 0.0)) >= 0.7:
            return "HIGH_RISK"
        if risk_score >= 5.0:
            return "REVIEW_RECOMMENDED"
        return "LOW_RISK"

    async def get_history(
        self,
        db: AsyncSession,
        *,
        article_id: int | None = None,
        draft_id: int | None = None,
        limit: int = 20,
    ) -> list[dict]:
        query = select(SimRun).order_by(SimRun.created_at.desc()).limit(limit)
        if article_id is not None:
            query = query.where(SimRun.article_id == article_id)
        if draft_id is not None:
            query = query.where(SimRun.draft_id == draft_id)
        rows = await db.execute(query)
        runs = rows.scalars().all()
        out: list[dict] = []
        for run in runs:
            result = await self.get_result(db, run.run_id)
            out.append(
                {
                    "run_id": run.run_id,
                    "status": run.status,
                    "headline": run.headline,
                    "platform": run.platform,
                    "mode": run.mode,
                    "created_at": run.created_at.isoformat() if run.created_at else None,
                    "risk_score": result.get("risk_score") if result else None,
                    "virality_score": result.get("virality_score") if result else None,
                    "policy_level": result.get("policy_level") if result else None,
                }
            )
        return out

    async def get_events_since(self, db: AsyncSession, run_id: str, last_id: int = 0, limit: int = 100) -> list[SimJobEvent]:
        rows = await db.execute(
            select(SimJobEvent)
            .where(SimJobEvent.run_id == run_id, SimJobEvent.id > last_id)
            .order_by(SimJobEvent.id.asc())
            .limit(limit)
        )
        return rows.scalars().all()


audience_simulation_service = AudienceSimulationService()
