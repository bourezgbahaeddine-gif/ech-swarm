"""Provider manager with health tracking, weighted routing and circuit breaker."""

from __future__ import annotations

import random
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger("services.provider_manager")
settings = get_settings()


@dataclass
class ProviderState:
    healthy: bool = True
    latency_ms_p50: float = 0.0
    last_error: str | None = None
    consecutive_failures: int = 0
    open_until: datetime | None = None
    calls: int = 0


@dataclass
class RouteDecision:
    provider: str
    degraded: bool = False
    reason: str | None = None
    estimated_cost_usd: float = 0.0


class ProviderManager:
    """In-memory provider manager skeleton.

    Production note:
    - Persist these metrics to Redis/Postgres for multi-instance workers.
    """

    def __init__(self) -> None:
        self._state: dict[str, ProviderState] = {
            "gemini": ProviderState(),
            "groq": ProviderState(),
        }
        self._weights = {
            "gemini": max(0.01, settings.provider_weight_gemini),
            "groq": max(0.01, settings.provider_weight_groq),
        }
        self._estimated_cost_usd = {
            "gemini": max(0.0, settings.provider_cost_estimate_gemini_usd),
            "groq": max(0.0, settings.provider_cost_estimate_groq_usd),
        }
        self._daily_spend_usd_by_date: dict[str, float] = {}

    def health(self) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        now = datetime.utcnow()
        spend_today = self._current_daily_spend_usd()
        budget = max(0.01, float(settings.provider_daily_budget_usd))
        for name, st in self._state.items():
            circuit_open = bool(st.open_until and st.open_until > now)
            out[name] = {
                "healthy": st.healthy and not circuit_open,
                "latency_ms_p50": round(st.latency_ms_p50, 2),
                "last_error": st.last_error,
                "consecutive_failures": st.consecutive_failures,
                "circuit_open": circuit_open,
                "calls": st.calls,
                "estimated_cost_usd_per_call": round(self._estimate_call_cost_usd(name), 4),
            }
        out["_budget"] = {
            "daily_budget_usd": round(budget, 4),
            "daily_spend_usd": round(spend_today, 4),
            "daily_budget_ratio": round(min(1.0, spend_today / budget), 4),
        }
        return out

    @staticmethod
    def _today_key() -> str:
        return datetime.utcnow().date().isoformat()

    def _current_daily_spend_usd(self) -> float:
        return float(self._daily_spend_usd_by_date.get(self._today_key(), 0.0))

    def _add_daily_spend_usd(self, cost_usd: float) -> None:
        if cost_usd <= 0:
            return
        key = self._today_key()
        self._daily_spend_usd_by_date[key] = float(self._daily_spend_usd_by_date.get(key, 0.0)) + float(cost_usd)
        # keep only today's bucket in memory
        for bucket in list(self._daily_spend_usd_by_date.keys()):
            if bucket != key:
                self._daily_spend_usd_by_date.pop(bucket, None)

    def _eligible(self) -> list[str]:
        now = datetime.utcnow()
        providers = []
        for name, st in self._state.items():
            if st.open_until and st.open_until > now:
                continue
            if settings.provider_prefer_configured_only and not self._is_configured(name):
                continue
            providers.append(name)
        return providers or ["gemini"]

    @staticmethod
    def _is_configured(provider: str) -> bool:
        if provider == "groq":
            return bool((settings.groq_api_key or "").strip())
        if provider == "gemini":
            return bool((settings.gemini_api_key or "").strip())
        return True

    def _estimate_call_cost_usd(self, provider: str) -> float:
        return float(self._estimated_cost_usd.get(provider, 0.0))

    def _cheapest_provider(self, eligible: list[str]) -> str:
        if not eligible:
            return "gemini"
        return min(eligible, key=self._estimate_call_cost_usd)

    @staticmethod
    def _normalized_urgency(route_context: dict[str, Any] | None) -> str:
        if not route_context:
            return "normal"
        raw = str(route_context.get("urgency") or "normal").strip().lower()
        if raw in {"breaking", "high", "critical"}:
            return "high"
        if raw in {"low"}:
            return "low"
        return "normal"

    @staticmethod
    def _queue_tier(route_context: dict[str, Any] | None) -> str:
        if not route_context:
            return "balanced"
        queue = str(route_context.get("queue_name") or route_context.get("queue") or "").strip().lower()
        queue_tiers = {
            "ai_scribe": settings.provider_queue_tier_scribe,
            "ai_quality": settings.provider_queue_tier_quality,
            "ai_simulator": settings.provider_queue_tier_simulator,
            "ai_router": settings.provider_queue_tier_router,
        }
        tier = str(queue_tiers.get(queue, "balanced")).strip().lower()
        return tier if tier in {"low", "balanced", "high"} else "balanced"

    def pick_with_context(self, route_context: dict[str, Any] | None = None) -> RouteDecision:
        eligible = self._eligible()
        urgency = self._normalized_urgency(route_context)
        tier = self._queue_tier(route_context)

        if tier == "high" or urgency == "high":
            preferred = "gemini"
        elif tier == "low" or urgency == "low":
            preferred = "groq"
        else:
            preferred = random.choices(eligible, weights=[self._weights.get(p, 0.1) for p in eligible], k=1)[0]

        if preferred not in eligible:
            preferred = self._cheapest_provider(eligible)

        budget_limit = max(0.01, float(settings.provider_daily_budget_usd))
        per_job_cap = max(0.0, float(settings.provider_per_job_max_usd))
        spend_today = self._current_daily_spend_usd()
        preferred_cost = self._estimate_call_cost_usd(preferred)

        if spend_today >= budget_limit or (per_job_cap > 0 and preferred_cost > per_job_cap):
            degraded_provider = self._cheapest_provider(eligible)
            degraded = degraded_provider != preferred
            return RouteDecision(
                provider=degraded_provider,
                degraded=degraded,
                reason="budget_cap" if degraded else None,
                estimated_cost_usd=self._estimate_call_cost_usd(degraded_provider),
            )

        return RouteDecision(
            provider=preferred,
            degraded=False,
            reason=None,
            estimated_cost_usd=preferred_cost,
        )

    def pick(self) -> str:
        return self.pick_with_context().provider

    def record_success(self, provider: str, elapsed_ms: float, *, cost_estimate_usd: float | None = None) -> None:
        st = self._state.setdefault(provider, ProviderState())
        st.calls += 1
        st.consecutive_failures = 0
        st.last_error = None
        # Cheap rolling p50 approximation.
        st.latency_ms_p50 = elapsed_ms if st.latency_ms_p50 <= 0 else ((st.latency_ms_p50 * 0.7) + (elapsed_ms * 0.3))
        st.healthy = True
        st.open_until = None
        estimated_cost = self._estimate_call_cost_usd(provider) if cost_estimate_usd is None else max(0.0, float(cost_estimate_usd))
        self._add_daily_spend_usd(estimated_cost)

    def record_failure(self, provider: str, error: str) -> None:
        st = self._state.setdefault(provider, ProviderState())
        st.calls += 1
        st.consecutive_failures += 1
        st.last_error = error[:500]
        if st.consecutive_failures >= settings.provider_circuit_failures:
            st.open_until = datetime.utcnow() + timedelta(seconds=settings.provider_circuit_open_sec)
            st.healthy = False
            logger.warning("provider_circuit_open", provider=provider, open_seconds=settings.provider_circuit_open_sec)

    async def call(self, *, run_fn: Any, fallback_fn: Any | None = None, route_context: dict[str, Any] | None = None) -> Any:
        """Run provider call with automatic fallback.

        run_fn(provider_name) -> awaitable result
        fallback_fn(provider_name, exc) -> awaitable result | raises
        """
        decision = self.pick_with_context(route_context)
        provider = decision.provider
        if decision.degraded:
            logger.warning(
                "provider_routed_degraded",
                provider=provider,
                reason=decision.reason,
                route_context=route_context or {},
            )
        started = time.perf_counter()
        try:
            result = await run_fn(provider)
            self.record_success(
                provider,
                (time.perf_counter() - started) * 1000,
                cost_estimate_usd=decision.estimated_cost_usd,
            )
            return result
        except Exception as exc:  # noqa: BLE001
            self.record_failure(provider, str(exc))
            if fallback_fn:
                return await fallback_fn(provider, exc)
            raise


provider_manager = ProviderManager()
