"""Time integrity metrics and stale-newsroom cleanup helpers."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import Article, NewsStatus
from app.services.cache_service import cache_service

settings = get_settings()


class TimeIntegrityService:
    """Build time-integrity telemetry and enforce stale cleanup policy."""

    _NON_PUBLISHED_STATUSES = [status for status in NewsStatus if status not in {NewsStatus.PUBLISHED, NewsStatus.ARCHIVED}]
    _CHIEF_STATUSES = [NewsStatus.READY_FOR_CHIEF_APPROVAL, NewsStatus.APPROVAL_REQUEST_WITH_RESERVATIONS]
    _EVENT_TIME = func.coalesce(Article.published_at, Article.crawled_at, Article.created_at)

    @staticmethod
    def _resolve_max_age_hours(max_age_hours: int | None = None) -> int:
        configured = max_age_hours if max_age_hours is not None else settings.scout_max_article_age_hours
        try:
            value = int(configured)
        except (TypeError, ValueError):
            value = 24
        return max(1, value)

    @staticmethod
    def _age_hours(now: datetime, event_time: datetime | None) -> float | None:
        if event_time is None:
            return None
        return round((now - event_time).total_seconds() / 3600.0, 2)

    async def build_overview(
        self,
        db: AsyncSession,
        *,
        max_age_hours: int | None = None,
        top_sources_limit: int = 10,
    ) -> dict:
        now = datetime.utcnow()
        effective_max_age_hours = self._resolve_max_age_hours(max_age_hours)
        cutoff = now - timedelta(hours=effective_max_age_hours)

        oldest_candidate_row = await db.execute(
            select(func.min(self._EVENT_TIME)).where(Article.status == NewsStatus.CANDIDATE)
        )
        oldest_candidate_at = oldest_candidate_row.scalar_one_or_none()

        oldest_chief_row = await db.execute(
            select(func.min(self._EVENT_TIME)).where(Article.status.in_(self._CHIEF_STATUSES))
        )
        oldest_chief_at = oldest_chief_row.scalar_one_or_none()

        stale_rows = await db.execute(
            select(Article.status, func.count(Article.id))
            .where(Article.status.in_(self._NON_PUBLISHED_STATUSES))
            .where(self._EVENT_TIME < cutoff)
            .group_by(Article.status)
        )
        stale_by_status = [
            {"status": status.value if status else "unknown", "count": int(count or 0)}
            for status, count in stale_rows.all()
        ]
        stale_total = sum(item["count"] for item in stale_by_status)

        skip_counters = await cache_service.list_counters("time_integrity:skip:", limit=200)
        skip_reasons = [
            {
                "reason": key.replace("time_integrity:skip:", "", 1),
                "count": int(value or 0),
            }
            for key, value in skip_counters.items()
        ]
        skip_reasons.sort(key=lambda item: item["count"], reverse=True)

        missing_source_counters = await cache_service.list_counters(
            "time_integrity:missing_timestamp_source:",
            limit=1000,
        )
        top_missing_timestamp_sources = [
            {
                "source": key.replace("time_integrity:missing_timestamp_source:", "", 1),
                "count": int(value or 0),
            }
            for key, value in missing_source_counters.items()
        ]
        top_missing_timestamp_sources.sort(key=lambda item: item["count"], reverse=True)
        top_missing_timestamp_sources = top_missing_timestamp_sources[: max(1, top_sources_limit)]

        stale_source_counters = await cache_service.list_counters(
            "time_integrity:source_reason:stale:",
            limit=1000,
        )
        top_stale_sources = [
            {
                "source": key.replace("time_integrity:source_reason:stale:", "", 1),
                "count": int(value or 0),
            }
            for key, value in stale_source_counters.items()
        ]
        top_stale_sources.sort(key=lambda item: item["count"], reverse=True)
        top_stale_sources = top_stale_sources[: max(1, top_sources_limit)]

        fallback_accepted = await cache_service.get_counter("time_integrity:url_date_fallback_accepted")
        ingested_total = await cache_service.get_counter("time_integrity:ingested_total")
        fallback_acceptance_ratio = round((fallback_accepted / ingested_total), 4) if ingested_total > 0 else 0.0

        return {
            "generated_at": now.isoformat(),
            "policy": {
                "max_article_age_hours": effective_max_age_hours,
                "cutoff_iso": cutoff.isoformat(),
                "require_timestamp_for_all_sources": bool(settings.scout_require_timestamp_for_all_sources),
                "require_timestamp_for_aggregator": bool(settings.scout_require_timestamp_for_aggregator),
                "allow_url_date_fallback": bool(settings.scout_allow_url_date_fallback),
            },
            "oldest_candidate_age_hours": self._age_hours(now, oldest_candidate_at),
            "oldest_ready_for_chief_age_hours": self._age_hours(now, oldest_chief_at),
            "stale_non_published_total": stale_total,
            "stale_non_published_by_status": stale_by_status,
            "skip_reasons": skip_reasons,
            "top_stale_sources": top_stale_sources,
            "top_missing_timestamp_sources": top_missing_timestamp_sources,
            "url_date_fallback": {
                "accepted_count": int(fallback_accepted),
                "ingested_total": int(ingested_total),
                "acceptance_ratio": fallback_acceptance_ratio,
            },
        }

    async def archive_stale_non_published(
        self,
        db: AsyncSession,
        *,
        max_age_hours: int | None = None,
        dry_run: bool = False,
        reason: str = "auto_archived:strict_time_guard",
    ) -> dict:
        now = datetime.utcnow()
        effective_max_age_hours = self._resolve_max_age_hours(max_age_hours)
        cutoff = now - timedelta(hours=effective_max_age_hours)

        count_row = await db.execute(
            select(func.count(Article.id))
            .where(Article.status.in_(self._NON_PUBLISHED_STATUSES))
            .where(self._EVENT_TIME < cutoff)
        )
        matched = int(count_row.scalar_one_or_none() or 0)

        archived_rows = 0
        if not dry_run and matched > 0:
            result = await db.execute(
                update(Article)
                .where(Article.status.in_(self._NON_PUBLISHED_STATUSES))
                .where(self._EVENT_TIME < cutoff)
                .values(
                    status=NewsStatus.ARCHIVED,
                    rejection_reason=f"{reason}:{effective_max_age_hours}h",
                    updated_at=now,
                )
            )
            archived_rows = int(result.rowcount or 0)
            await db.commit()

        return {
            "dry_run": dry_run,
            "matched_rows": matched,
            "archived_rows": archived_rows,
            "max_age_hours": effective_max_age_hours,
            "cutoff_iso": cutoff.isoformat(),
            "reason": f"{reason}:{effective_max_age_hours}h",
        }


time_integrity_service = TimeIntegrityService()
