"""MSI service: run orchestration, persistence, watchlist."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import async_session
from app.core.logging import get_logger
from app.models import MsiArtifact, MsiBaseline, MsiJobEvent, MsiReport, MsiRun, MsiTimeseries, MsiWatchlist
from app.models.user import User
from app.msi.graph import MsiGraphRunner
from app.msi.nodes import MsiGraphNodes
from app.msi.profiles import list_profiles
from app.msi.state import MSIState

logger = get_logger("msi.service")
settings = get_settings()


class MsiMonitorService:
    def __init__(self):
        self._running_tasks: dict[str, asyncio.Task] = {}

    @staticmethod
    def compute_window(mode: str, start: datetime | None = None, end: datetime | None = None) -> tuple[datetime, datetime]:
        tz = ZoneInfo(settings.msi_timezone)
        now = datetime.now(tz).replace(tzinfo=None)
        period_end = end or now
        if start:
            period_start = start
        else:
            period_start = period_end - timedelta(days=1 if mode == "daily" else 7)
        return period_start, period_end

    async def list_profiles(self) -> list[dict]:
        return list_profiles()

    async def create_run(
        self,
        db: AsyncSession,
        *,
        profile_id: str,
        entity: str,
        mode: str,
        actor: User | None,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> MsiRun:
        period_start, period_end = self.compute_window(mode, start=start, end=end)
        run_id = f"MSI-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{abs(hash((profile_id, entity, mode, period_end.isoformat()))) % 10_000_000:07d}"
        run = MsiRun(
            run_id=run_id,
            profile_id=profile_id,
            entity=entity.strip(),
            mode=mode,
            period_start=period_start,
            period_end=period_end,
            timezone=settings.msi_timezone,
            status="queued",
            created_by_user_id=actor.id if actor else None,
            created_by_username=actor.username if actor else "system",
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
            run_row = await db.execute(select(MsiRun).where(MsiRun.run_id == run_id))
            run = run_row.scalar_one_or_none()
            if not run:
                return

            run.status = "running"
            await db.commit()
            await self._emit_event(db, run_id, "runner", "started", {"status": "running"})

            async def emit(node: str, event_type: str, payload: dict):
                await self._emit_event(db, run_id, node, event_type, payload)

            nodes = MsiGraphNodes(db, emit)
            graph = MsiGraphRunner(nodes, emit)
            initial_state = MSIState(
                run_id=run.run_id,
                profile_id=run.profile_id,
                entity=run.entity,
                mode=run.mode,  # type: ignore[arg-type]
                period_start=run.period_start,
                period_end=run.period_end,
                timezone=run.timezone or settings.msi_timezone,
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
                logger.error("msi_run_failed", run_id=run_id, error=str(exc))
                try:
                    await db.rollback()
                except Exception:
                    pass

                try:
                    failed_row = await db.execute(select(MsiRun).where(MsiRun.run_id == run_id))
                    failed_run = failed_row.scalar_one_or_none()
                    if failed_run:
                        failed_run.status = "failed"
                        failed_run.finished_at = datetime.utcnow()
                        failed_run.error = str(exc)[:2000]
                        await db.commit()
                except Exception as mark_exc:  # noqa: BLE001
                    logger.error("msi_run_mark_failed_error", run_id=run_id, error=str(mark_exc))

                try:
                    async with async_session() as db2:
                        await self._emit_event(db2, run_id, "runner", "failed", {"status": "failed", "error": str(exc)})
                except Exception as emit_exc:  # noqa: BLE001
                    logger.error("msi_run_failed_event_error", run_id=run_id, error=str(emit_exc))

    async def _persist_result(self, db: AsyncSession, run: MsiRun, result: MSIState) -> None:
        report = MsiReport(run_id=run.run_id, report_json=self._json_safe(result.report))
        artifact = MsiArtifact(
            run_id=run.run_id,
            items_json=[item.model_dump(mode="json") for item in result.analyzed_items],
            aggregates_json=result.aggregates.model_dump(mode="json"),
        )
        db.add(report)
        db.add(artifact)

        # upsert timeseries point
        existing_point = await db.execute(
            select(MsiTimeseries).where(
                MsiTimeseries.profile_id == run.profile_id,
                MsiTimeseries.entity == run.entity,
                MsiTimeseries.mode == run.mode,
                MsiTimeseries.period_end == run.period_end,
            )
        )
        point = existing_point.scalar_one_or_none()
        if point:
            point.msi = result.computed.msi
            point.level = result.computed.level
            point.components_json = result.computed.components
        else:
            db.add(
                MsiTimeseries(
                    profile_id=run.profile_id,
                    entity=run.entity,
                    mode=run.mode,
                    period_end=run.period_end,
                    msi=result.computed.msi,
                    level=result.computed.level,
                    components_json=self._json_safe(result.computed.components),
                )
            )

        # upsert baseline
        baseline_row = await db.execute(
            select(MsiBaseline).where(
                MsiBaseline.profile_id == run.profile_id,
                MsiBaseline.entity == run.entity,
            )
        )
        baseline = baseline_row.scalar_one_or_none()
        baseline_data = result.baseline or {}
        if baseline:
            baseline.pressure_history = baseline_data.get("pressure_history", [])
            baseline.last_topic_dist = baseline_data.get("last_topic_dist", {})
            baseline.baseline_window_days = int(baseline_data.get("baseline_window_days", settings.msi_default_baseline_days))
            baseline.last_updated = datetime.utcnow()
        else:
            db.add(
                MsiBaseline(
                    profile_id=run.profile_id,
                    entity=run.entity,
                    pressure_history=self._json_safe(baseline_data.get("pressure_history", [])),
                    last_topic_dist=self._json_safe(baseline_data.get("last_topic_dist", {})),
                    baseline_window_days=int(baseline_data.get("baseline_window_days", settings.msi_default_baseline_days)),
                    last_updated=datetime.utcnow(),
                )
            )

    @staticmethod
    def _json_safe(value):
        """Ensure JSON payloads are serializable before writing to JSON columns."""
        return json.loads(json.dumps(value, ensure_ascii=False, default=str))

    async def _emit_event(self, db: AsyncSession, run_id: str, node: str, event_type: str, payload: dict) -> None:
        db.add(
            MsiJobEvent(
                run_id=run_id,
                node=node,
                event_type=event_type,
                payload_json=payload or {},
            )
        )
        await db.commit()

    async def get_run_status(self, db: AsyncSession, run_id: str) -> MsiRun | None:
        row = await db.execute(select(MsiRun).where(MsiRun.run_id == run_id))
        return row.scalar_one_or_none()

    async def get_report(self, db: AsyncSession, run_id: str) -> dict | None:
        row = await db.execute(
            select(MsiReport).where(MsiReport.run_id == run_id).order_by(desc(MsiReport.created_at)).limit(1)
        )
        report = row.scalar_one_or_none()
        return report.report_json if report else None

    async def get_timeseries(self, db: AsyncSession, profile_id: str, entity: str, mode: str, limit: int = 30) -> list[MsiTimeseries]:
        rows = await db.execute(
            select(MsiTimeseries)
            .where(
                MsiTimeseries.profile_id == profile_id,
                MsiTimeseries.entity == entity,
                MsiTimeseries.mode == mode,
            )
            .order_by(MsiTimeseries.period_end.desc())
            .limit(limit)
        )
        return list(reversed(rows.scalars().all()))

    async def get_top_entities(self, db: AsyncSession, mode: str, limit: int = 5) -> list[MsiTimeseries]:
        subquery = (
            select(
                MsiTimeseries.profile_id,
                MsiTimeseries.entity,
                MsiTimeseries.mode,
                func.max(MsiTimeseries.period_end).label("max_period_end"),
            )
            .where(MsiTimeseries.mode == mode)
            .group_by(MsiTimeseries.profile_id, MsiTimeseries.entity, MsiTimeseries.mode)
            .subquery()
        )
        rows = await db.execute(
            select(MsiTimeseries)
            .join(
                subquery,
                (MsiTimeseries.profile_id == subquery.c.profile_id)
                & (MsiTimeseries.entity == subquery.c.entity)
                & (MsiTimeseries.mode == subquery.c.mode)
                & (MsiTimeseries.period_end == subquery.c.max_period_end),
            )
            .order_by(MsiTimeseries.msi.asc())
            .limit(limit)
        )
        return rows.scalars().all()

    async def list_watchlist(self, db: AsyncSession, enabled_only: bool = False) -> list[MsiWatchlist]:
        query = select(MsiWatchlist).order_by(MsiWatchlist.updated_at.desc())
        if enabled_only:
            query = query.where(MsiWatchlist.enabled.is_(True))
        rows = await db.execute(query)
        return rows.scalars().all()

    async def create_watchlist_item(
        self,
        db: AsyncSession,
        *,
        profile_id: str,
        entity: str,
        run_daily: bool,
        run_weekly: bool,
        enabled: bool,
        actor: User | None,
    ) -> MsiWatchlist:
        existing = await db.execute(
            select(MsiWatchlist).where(
                MsiWatchlist.profile_id == profile_id,
                MsiWatchlist.entity == entity.strip(),
            )
        )
        row = existing.scalar_one_or_none()
        if row:
            row.run_daily = run_daily
            row.run_weekly = run_weekly
            row.enabled = enabled
            row.updated_at = datetime.utcnow()
            await db.commit()
            await db.refresh(row)
            return row

        row = MsiWatchlist(
            profile_id=profile_id,
            entity=entity.strip(),
            run_daily=run_daily,
            run_weekly=run_weekly,
            enabled=enabled,
            created_by_user_id=actor.id if actor else None,
            created_by_username=actor.username if actor else None,
        )
        db.add(row)
        await db.commit()
        await db.refresh(row)
        return row

    async def update_watchlist_item(self, db: AsyncSession, item_id: int, **changes) -> MsiWatchlist | None:
        row = await db.execute(select(MsiWatchlist).where(MsiWatchlist.id == item_id))
        item = row.scalar_one_or_none()
        if not item:
            return None
        for key, value in changes.items():
            if value is not None and hasattr(item, key):
                setattr(item, key, value)
        item.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(item)
        return item

    async def delete_watchlist_item(self, db: AsyncSession, item_id: int) -> bool:
        row = await db.execute(select(MsiWatchlist).where(MsiWatchlist.id == item_id))
        item = row.scalar_one_or_none()
        if not item:
            return False
        await db.delete(item)
        await db.commit()
        return True

    async def get_events_since(self, db: AsyncSession, run_id: str, last_id: int = 0, limit: int = 100) -> list[MsiJobEvent]:
        rows = await db.execute(
            select(MsiJobEvent)
            .where(MsiJobEvent.run_id == run_id, MsiJobEvent.id > last_id)
            .order_by(MsiJobEvent.id.asc())
            .limit(limit)
        )
        return rows.scalars().all()

    async def run_watchlist_mode(self, mode: str) -> dict:
        async with async_session() as db:
            items = await self.list_watchlist(db, enabled_only=True)
            triggered = 0
            for item in items:
                if mode == "daily" and not item.run_daily:
                    continue
                if mode == "weekly" and not item.run_weekly:
                    continue
                run = await self.create_run(
                    db,
                    profile_id=item.profile_id,
                    entity=item.entity,
                    mode=mode,
                    actor=None,
                )
                await self.start_run_task(run.run_id)
                triggered += 1
            return {"mode": mode, "triggered": triggered}


msi_monitor_service = MsiMonitorService()
