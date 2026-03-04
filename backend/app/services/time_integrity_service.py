"""Time integrity metrics and stale-newsroom cleanup helpers."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import ActionAuditLog, Article, NewsStatus, Source
from app.models.user import User
from app.services.audit_service import audit_service
from app.services.cache_service import cache_service

settings = get_settings()


class TimeIntegrityService:
    """Build time-integrity telemetry and enforce stale cleanup policy."""

    _AUTO_ARCHIVE_ACTION = "auto_archived_stale"
    _AUTO_ARCHIVE_REASON_PREFIX = "auto_archived:strict_time_guard"
    _AUTO_ARCHIVE_RESTORE_ACTION = "auto_archived_stale_restored"
    _AUTO_ARCHIVE_RESTORE_REASON = "manual_restore_auto_archived_stale"
    _NON_PUBLISHED_STATUSES = [status for status in NewsStatus if status not in {NewsStatus.PUBLISHED, NewsStatus.ARCHIVED}]
    _CHIEF_STATUSES = [NewsStatus.READY_FOR_CHIEF_APPROVAL, NewsStatus.APPROVAL_REQUEST_WITH_RESERVATIONS]
    _EVENT_TIME = func.coalesce(Article.published_at, Article.crawled_at, Article.created_at)
    _WATCHLIST_DEFAULT_MIN_EVENTS = 10

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

    @staticmethod
    def _normalize_source_key(source_name: str | None) -> str:
        source = (source_name or "").strip().lower()
        source = "_".join(source.split())
        source = "".join(ch for ch in source if ch.isalnum() or ch in "._-")
        return source[:120] or "unknown"

    @staticmethod
    def _normalized_host(url: str | None) -> str:
        raw = (url or "").strip()
        if not raw:
            return ""
        if "://" not in raw:
            raw = f"https://{raw}"
        try:
            host = (urlparse(raw).netloc or "").lower()
        except Exception:
            return ""
        if host.startswith("www."):
            host = host[4:]
        return host

    @staticmethod
    def _coerce_status(value: Any) -> NewsStatus | None:
        if isinstance(value, NewsStatus):
            return value
        if value is None:
            return None
        raw = str(value).strip()
        if not raw:
            return None
        try:
            return NewsStatus(raw)
        except ValueError:
            return None

    @staticmethod
    def _coerce_int(value: Any) -> int | None:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _source_aliases(self, source: Source) -> set[str]:
        aliases = {
            self._normalize_source_key(source.name),
            self._normalize_source_key(source.slug),
            self._normalize_source_key(self._normalized_host(source.url)),
            self._normalize_source_key(self._normalized_host(source.rss_url)),
        }
        return {alias for alias in aliases if alias and alias != "unknown"}

    @staticmethod
    def _safe_rate(numerator: int, denominator: int) -> float:
        if denominator <= 0:
            return 0.0
        return round(float(numerator) / float(denominator), 4)

    @staticmethod
    def _watchlist_band(score: float) -> str:
        if score >= 80:
            return "excellent"
        if score >= 65:
            return "good"
        if score >= 45:
            return "review"
        return "weak"

    @classmethod
    def _watchlist_score(
        cls,
        *,
        stale_rate: float,
        missing_timestamp_rate: float,
        duplicate_rate: float,
        future_timestamp_rate: float,
        blocked_rate: float,
        fetch_error_rate: float,
    ) -> float:
        score = (
            100.0
            - stale_rate * 35.0
            - missing_timestamp_rate * 30.0
            - duplicate_rate * 20.0
            - future_timestamp_rate * 10.0
            - blocked_rate * 5.0
            - fetch_error_rate * 20.0
        )
        return round(max(0.0, min(100.0, score)), 1)

    @classmethod
    def _watchlist_actions(
        cls,
        *,
        enabled: bool,
        priority: int,
        total_events: int,
        stale_rate: float,
        missing_timestamp_rate: float,
        duplicate_rate: float,
        fetch_error_rate: float,
        health_score: float,
        min_events: int,
        source_known: bool,
    ) -> list[str]:
        actions: list[str] = []
        has_signal = total_events >= min_events

        if has_signal and missing_timestamp_rate >= 0.20:
            actions.append("require_manual_review")

        if source_known and has_signal and priority > 2:
            if stale_rate >= 0.35 or missing_timestamp_rate >= 0.20 or (duplicate_rate >= 0.65 and health_score < 65.0):
                actions.append("decrease_priority")
            elif duplicate_rate >= 0.80 and health_score >= 65.0:
                actions.append("monitor_duplicate_pressure")

        if source_known and enabled and (
            fetch_error_rate >= 0.80 or (has_signal and stale_rate >= 0.75 and health_score <= 35.0)
        ):
            actions.append("disable_temporarily")

        if source_known and (not enabled) and has_signal and health_score >= 80.0 and fetch_error_rate <= 0.20:
            actions.append("re_enable")

        return actions

    async def build_source_watchlist(
        self,
        db: AsyncSession,
        *,
        top_sources_limit: int = 10,
        min_events: int = _WATCHLIST_DEFAULT_MIN_EVENTS,
        include_disabled: bool = True,
        use_cache: bool = True,
    ) -> dict:
        limit = max(1, min(top_sources_limit, 100))
        min_events = max(1, min(min_events, 1000))
        cache_key = f"time_integrity:watchlist:v1:{limit}:{min_events}:{1 if include_disabled else 0}"
        if use_cache:
            cached = await cache_service.get_json(cache_key)
            if cached:
                return cached

        reason_counters = await cache_service.list_counters("time_integrity:source_reason:", limit=5000)
        ingested_counters = await cache_service.list_counters("time_integrity:source_ingested:", limit=5000)

        source_reason_map: dict[str, dict[str, int]] = {}
        for key, value in reason_counters.items():
            suffix = key.replace("time_integrity:source_reason:", "", 1)
            if ":" not in suffix:
                continue
            reason, source_key = suffix.split(":", 1)
            normalized_source = self._normalize_source_key(source_key)
            bucket = source_reason_map.setdefault(normalized_source, {})
            bucket[reason] = int(bucket.get(reason, 0) + int(value or 0))

        source_ingested_map: dict[str, int] = {}
        for key, value in ingested_counters.items():
            source_key = key.replace("time_integrity:source_ingested:", "", 1)
            normalized_source = self._normalize_source_key(source_key)
            source_ingested_map[normalized_source] = int(source_ingested_map.get(normalized_source, 0) + int(value or 0))

        source_query = select(Source).order_by(Source.priority.desc(), Source.id.asc())
        if not include_disabled:
            source_query = source_query.where(Source.enabled == True)  # noqa: E712
        source_rows = await db.execute(source_query)
        sources = source_rows.scalars().all()

        observed_keys = set(source_reason_map.keys()) | set(source_ingested_map.keys())
        consumed_keys: set[str] = set()
        watchlist_items: list[dict] = []

        def build_item(
            *,
            source_id: int | None,
            name: str,
            source_key: str,
            enabled: bool,
            priority: int,
            error_count: int,
            source_known: bool,
            aliases: set[str] | None = None,
        ) -> dict:
            alias_set = aliases or {source_key}
            reasons = {
                "duplicate": 0,
                "stale": 0,
                "future_timestamp": 0,
                "missing_timestamp": 0,
                "missing_timestamp_aggregator": 0,
                "missing_timestamp_scraper": 0,
                "blocked_source": 0,
            }
            ingested_count = 0
            for alias in alias_set:
                reason_bucket = source_reason_map.get(alias, {})
                for reason, count in reason_bucket.items():
                    reasons[reason] = int(reasons.get(reason, 0) + int(count or 0))
                ingested_count += int(source_ingested_map.get(alias, 0) or 0)

            missing_timestamp_count = (
                reasons.get("missing_timestamp", 0)
                + reasons.get("missing_timestamp_aggregator", 0)
                + reasons.get("missing_timestamp_scraper", 0)
            )
            duplicate_count = int(reasons.get("duplicate", 0))
            stale_count = int(reasons.get("stale", 0))
            future_timestamp_count = int(reasons.get("future_timestamp", 0))
            blocked_count = int(reasons.get("blocked_source", 0))
            total_events = ingested_count + duplicate_count + stale_count + missing_timestamp_count + future_timestamp_count + blocked_count

            stale_rate = self._safe_rate(stale_count, total_events)
            missing_timestamp_rate = self._safe_rate(missing_timestamp_count, total_events)
            duplicate_rate = self._safe_rate(duplicate_count, total_events)
            future_timestamp_rate = self._safe_rate(future_timestamp_count, total_events)
            blocked_rate = self._safe_rate(blocked_count, total_events)
            fetch_error_rate = round(min(max(error_count, 0) / 5.0, 1.0), 4)

            health_score = self._watchlist_score(
                stale_rate=stale_rate,
                missing_timestamp_rate=missing_timestamp_rate,
                duplicate_rate=duplicate_rate,
                future_timestamp_rate=future_timestamp_rate,
                blocked_rate=blocked_rate,
                fetch_error_rate=fetch_error_rate,
            )
            actions = self._watchlist_actions(
                enabled=enabled,
                priority=priority,
                total_events=total_events,
                stale_rate=stale_rate,
                missing_timestamp_rate=missing_timestamp_rate,
                duplicate_rate=duplicate_rate,
                fetch_error_rate=fetch_error_rate,
                health_score=health_score,
                min_events=min_events,
                source_known=source_known,
            )
            return {
                "source_id": source_id,
                "source_key": source_key,
                "name": name,
                "enabled": enabled,
                "priority": priority,
                "error_count": error_count,
                "source_known": source_known,
                "health_score": health_score,
                "health_band": self._watchlist_band(health_score),
                "total_events": total_events,
                "ingested_count": ingested_count,
                "duplicate_count": duplicate_count,
                "stale_count": stale_count,
                "missing_timestamp_count": missing_timestamp_count,
                "future_timestamp_count": future_timestamp_count,
                "blocked_count": blocked_count,
                "stale_rate": stale_rate,
                "missing_timestamp_rate": missing_timestamp_rate,
                "duplicate_rate": duplicate_rate,
                "fetch_error_rate": fetch_error_rate,
                "actions": actions,
            }

        for source in sources:
            aliases = self._source_aliases(source)
            matched_aliases = {alias for alias in aliases if alias in observed_keys}
            if not matched_aliases and int(source.error_count or 0) <= 0:
                continue
            consumed_keys.update(matched_aliases)
            display_name = source.name or source.slug or next(iter(matched_aliases), str(source.id))
            watchlist_items.append(
                build_item(
                    source_id=source.id,
                    name=display_name,
                    source_key=self._normalize_source_key(display_name),
                    enabled=bool(source.enabled),
                    priority=int(source.priority or 0),
                    error_count=int(source.error_count or 0),
                    source_known=True,
                    aliases=matched_aliases if matched_aliases else aliases,
                )
            )

        for source_key in sorted(observed_keys - consumed_keys):
            watchlist_items.append(
                build_item(
                    source_id=None,
                    name=source_key,
                    source_key=source_key,
                    enabled=False,
                    priority=0,
                    error_count=0,
                    source_known=False,
                    aliases={source_key},
                )
            )

        flagged_items = [
            item
            for item in watchlist_items
            if item["total_events"] >= min_events and (item["actions"] or item["health_band"] in {"review", "weak"})
        ]
        flagged_items.sort(
            key=lambda item: (
                item["health_score"],
                -item["total_events"],
                item["name"],
            )
        )

        payload = {
            "window_hours": 24,
            "min_events": min_events,
            "total_sources_observed": len(watchlist_items),
            "watchlist_total": len(flagged_items),
            "items": flagged_items[:limit],
        }
        if use_cache:
            await cache_service.set_json(cache_key, payload, ttl=timedelta(seconds=30))
        return payload

    async def apply_source_watchlist_actions(
        self,
        db: AsyncSession,
        *,
        dry_run: bool = True,
        top_sources_limit: int = 30,
        min_events: int = _WATCHLIST_DEFAULT_MIN_EVENTS,
        max_changes: int = 100,
        include_disabled: bool = True,
    ) -> dict:
        watchlist = await self.build_source_watchlist(
            db,
            top_sources_limit=max(top_sources_limit, max_changes),
            min_events=min_events,
            include_disabled=include_disabled,
            use_cache=False,
        )
        max_changes = max(1, min(max_changes, 500))

        source_rows = await db.execute(select(Source))
        source_map = {source.id: source for source in source_rows.scalars().all()}

        changed_items = []
        advisory_items = []
        for item in watchlist["items"]:
            actions = list(item.get("actions") or [])
            source_id = item.get("source_id")
            source = source_map.get(source_id) if source_id else None
            if source is None:
                if actions:
                    advisory_items.append(
                        {
                            "source_id": source_id,
                            "name": item.get("name"),
                            "actions": actions,
                            "note": "source_not_registered",
                        }
                    )
                continue

            before_enabled = bool(source.enabled)
            before_priority = int(source.priority or 0)
            after_enabled = before_enabled
            after_priority = before_priority
            manual_review = False

            for action in actions:
                if action == "disable_temporarily":
                    after_enabled = False
                elif action == "re_enable":
                    after_enabled = True
                elif action == "decrease_priority":
                    after_priority = max(1, after_priority - 1)
                elif action == "increase_priority":
                    after_priority = min(10, after_priority + 1)
                elif action == "require_manual_review":
                    manual_review = True

            if after_enabled == before_enabled and after_priority == before_priority:
                if manual_review:
                    advisory_items.append(
                        {
                            "source_id": source.id,
                            "name": source.name,
                            "actions": ["require_manual_review"],
                            "note": "manual_review_advisory_only",
                        }
                    )
                continue

            if len(changed_items) >= max_changes:
                break

            changed_items.append(
                {
                    "source_id": source.id,
                    "name": source.name,
                    "actions": actions,
                    "before": {"enabled": before_enabled, "priority": before_priority},
                    "after": {"enabled": after_enabled, "priority": after_priority},
                    "health_score": item.get("health_score"),
                    "health_band": item.get("health_band"),
                }
            )
            if not dry_run:
                source.enabled = after_enabled
                source.priority = after_priority

        if not dry_run and changed_items:
            await db.commit()

        return {
            "dry_run": dry_run,
            "max_changes": max_changes,
            "candidate_changes": len(changed_items),
            "applied_changes": 0 if dry_run else len(changed_items),
            "items": changed_items,
            "advisories": advisory_items,
        }

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
        source_watchlist = await self.build_source_watchlist(
            db,
            top_sources_limit=top_sources_limit,
            min_events=self._WATCHLIST_DEFAULT_MIN_EVENTS,
            include_disabled=True,
        )

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
            "source_health_watchlist": source_watchlist,
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
        reason: str = _AUTO_ARCHIVE_REASON_PREFIX,
    ) -> dict:
        now = datetime.utcnow()
        effective_max_age_hours = self._resolve_max_age_hours(max_age_hours)
        cutoff = now - timedelta(hours=effective_max_age_hours)

        stale_rows_result = await db.execute(
            select(Article.id, Article.status, self._EVENT_TIME.label("event_time"))
            .where(Article.status.in_(self._NON_PUBLISHED_STATUSES))
            .where(self._EVENT_TIME < cutoff)
        )
        stale_rows = stale_rows_result.all()
        matched = len(stale_rows)

        status_counts: dict[str, int] = {}
        for _, status, _ in stale_rows:
            status_value = status.value if isinstance(status, NewsStatus) else str(status or "unknown")
            status_counts[status_value] = int(status_counts.get(status_value, 0) + 1)

        archived_rows = 0
        if not dry_run and matched > 0:
            stale_article_ids = [int(article_id) for article_id, _, _ in stale_rows]
            result = await db.execute(
                update(Article)
                .where(Article.id.in_(stale_article_ids))
                .where(Article.status.in_(self._NON_PUBLISHED_STATUSES))
                .values(
                    status=NewsStatus.ARCHIVED,
                    rejection_reason=f"{reason}:{effective_max_age_hours}h",
                    updated_at=now,
                )
            )
            archived_rows = int(result.rowcount or 0)

            for article_id, status, event_time in stale_rows:
                original_status = self._coerce_status(status)
                age_hours = self._age_hours(now, event_time)
                await audit_service.log_action(
                    db,
                    action=self._AUTO_ARCHIVE_ACTION,
                    entity_type="article",
                    entity_id=int(article_id),
                    from_state=original_status.value if original_status else None,
                    to_state=NewsStatus.ARCHIVED.value,
                    reason=self._AUTO_ARCHIVE_ACTION,
                    details={
                        "original_status": original_status.value if original_status else None,
                        "age_hours": age_hours,
                        "max_age_hours": effective_max_age_hours,
                        "event_time": event_time.isoformat() if isinstance(event_time, datetime) else None,
                        "archived_at": now.isoformat(),
                    },
                )
            await db.commit()

        return {
            "dry_run": dry_run,
            "matched_rows": matched,
            "archived_rows": archived_rows,
            "max_age_hours": effective_max_age_hours,
            "cutoff_iso": cutoff.isoformat(),
            "reason": f"{reason}:{effective_max_age_hours}h",
            "audit_action": self._AUTO_ARCHIVE_ACTION,
            "matched_by_status": [{"status": k, "count": v} for k, v in sorted(status_counts.items())],
        }

    async def restore_recent_auto_archived(
        self,
        db: AsyncSession,
        *,
        lookback_hours: int = 24,
        max_rows: int = 200,
        dry_run: bool = True,
        actor: User | None = None,
    ) -> dict:
        now = datetime.utcnow()
        lookback_hours = max(1, min(int(lookback_hours), 168))
        max_rows = max(1, min(int(max_rows), 1000))
        cutoff = now - timedelta(hours=lookback_hours)

        log_rows = await db.execute(
            select(ActionAuditLog)
            .where(ActionAuditLog.action == self._AUTO_ARCHIVE_ACTION)
            .where(ActionAuditLog.entity_type == "article")
            .where(ActionAuditLog.created_at >= cutoff)
            .order_by(desc(ActionAuditLog.created_at))
            .limit(max_rows * 10)
        )
        logs = log_rows.scalars().all()

        recovery_plan: dict[int, dict[str, Any]] = {}
        for log in logs:
            article_id = self._coerce_int(log.entity_id)
            if article_id is None or article_id in recovery_plan:
                continue

            details = log.details_json if isinstance(log.details_json, dict) else {}
            original_status = self._coerce_status(details.get("original_status"))
            if original_status is None:
                original_status = self._coerce_status(log.from_state)
            if original_status is None or original_status in {NewsStatus.ARCHIVED, NewsStatus.PUBLISHED}:
                continue

            recovery_plan[article_id] = {
                "article_id": article_id,
                "target_status": original_status,
                "archived_at": log.created_at,
                "source_audit_id": log.id,
                "archive_reason": details.get("archive_reason") or log.reason,
                "age_hours_at_archive": details.get("age_hours"),
            }
            if len(recovery_plan) >= max_rows:
                break

        if not recovery_plan:
            return {
                "dry_run": dry_run,
                "lookback_hours": lookback_hours,
                "max_rows": max_rows,
                "candidate_logs": len(logs),
                "restorable_candidates": 0,
                "restored_rows": 0,
                "items": [],
                "advisories": [],
            }

        article_rows = await db.execute(
            select(Article.id, Article.status, Article.rejection_reason).where(Article.id.in_(list(recovery_plan.keys())))
        )
        article_map = {int(article_id): (status, rejection_reason) for article_id, status, rejection_reason in article_rows.all()}

        restorable_items: list[dict[str, Any]] = []
        advisories: list[dict[str, Any]] = []
        for article_id, plan in recovery_plan.items():
            article_state = article_map.get(article_id)
            if article_state is None:
                advisories.append(
                    {
                        "article_id": article_id,
                        "note": "article_not_found",
                    }
                )
                continue

            current_status, rejection_reason = article_state
            current_status_enum = self._coerce_status(current_status)
            if current_status_enum != NewsStatus.ARCHIVED:
                advisories.append(
                    {
                        "article_id": article_id,
                        "note": "article_not_archived",
                        "current_status": current_status_enum.value if current_status_enum else str(current_status),
                    }
                )
                continue

            reason_text = str(rejection_reason or "")
            if not reason_text.startswith(self._AUTO_ARCHIVE_REASON_PREFIX):
                advisories.append(
                    {
                        "article_id": article_id,
                        "note": "archive_reason_mismatch",
                        "current_rejection_reason": reason_text,
                    }
                )
                continue

            target_status = plan["target_status"]
            restorable_items.append(
                {
                    "article_id": article_id,
                    "before_status": NewsStatus.ARCHIVED.value,
                    "after_status": target_status.value,
                    "source_audit_id": plan["source_audit_id"],
                    "archived_at": plan["archived_at"].isoformat() if isinstance(plan["archived_at"], datetime) else None,
                    "age_hours_at_archive": plan["age_hours_at_archive"],
                }
            )

        restored_rows = 0
        if not dry_run and restorable_items:
            for item in restorable_items:
                article_id = int(item["article_id"])
                target_status = self._coerce_status(item["after_status"])
                if target_status is None:
                    continue
                update_result = await db.execute(
                    update(Article)
                    .where(Article.id == article_id)
                    .where(Article.status == NewsStatus.ARCHIVED)
                    .values(
                        status=target_status,
                        rejection_reason=None,
                        updated_at=now,
                    )
                )
                if int(update_result.rowcount or 0) <= 0:
                    continue

                restored_rows += 1
                await audit_service.log_action(
                    db,
                    action=self._AUTO_ARCHIVE_RESTORE_ACTION,
                    entity_type="article",
                    entity_id=article_id,
                    actor=actor,
                    from_state=NewsStatus.ARCHIVED.value,
                    to_state=target_status.value,
                    reason=self._AUTO_ARCHIVE_RESTORE_REASON,
                    details={
                        "source_audit_id": item["source_audit_id"],
                        "lookback_hours": lookback_hours,
                        "restored_at": now.isoformat(),
                    },
                )

            if restored_rows > 0:
                await db.commit()

        return {
            "dry_run": dry_run,
            "lookback_hours": lookback_hours,
            "max_rows": max_rows,
            "candidate_logs": len(logs),
            "restorable_candidates": len(restorable_items),
            "restored_rows": restored_rows,
            "items": restorable_items,
            "advisories": advisories,
        }


time_integrity_service = TimeIntegrityService()
