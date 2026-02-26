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

    def health(self) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        now = datetime.utcnow()
        for name, st in self._state.items():
            circuit_open = bool(st.open_until and st.open_until > now)
            out[name] = {
                "healthy": st.healthy and not circuit_open,
                "latency_ms_p50": round(st.latency_ms_p50, 2),
                "last_error": st.last_error,
                "consecutive_failures": st.consecutive_failures,
                "circuit_open": circuit_open,
                "calls": st.calls,
            }
        return out

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

    def pick(self) -> str:
        eligible = self._eligible()
        weights = [self._weights.get(p, 0.1) for p in eligible]
        return random.choices(eligible, weights=weights, k=1)[0]

    def record_success(self, provider: str, elapsed_ms: float) -> None:
        st = self._state.setdefault(provider, ProviderState())
        st.calls += 1
        st.consecutive_failures = 0
        st.last_error = None
        # Cheap rolling p50 approximation.
        st.latency_ms_p50 = elapsed_ms if st.latency_ms_p50 <= 0 else ((st.latency_ms_p50 * 0.7) + (elapsed_ms * 0.3))
        st.healthy = True
        st.open_until = None

    def record_failure(self, provider: str, error: str) -> None:
        st = self._state.setdefault(provider, ProviderState())
        st.calls += 1
        st.consecutive_failures += 1
        st.last_error = error[:500]
        if st.consecutive_failures >= settings.provider_circuit_failures:
            st.open_until = datetime.utcnow() + timedelta(seconds=settings.provider_circuit_open_sec)
            st.healthy = False
            logger.warning("provider_circuit_open", provider=provider, open_seconds=settings.provider_circuit_open_sec)

    async def call(self, *, run_fn: Any, fallback_fn: Any | None = None) -> Any:
        """Run provider call with automatic fallback.

        run_fn(provider_name) -> awaitable result
        fallback_fn(provider_name, exc) -> awaitable result | raises
        """
        provider = self.pick()
        started = time.perf_counter()
        try:
            result = await run_fn(provider)
            self.record_success(provider, (time.perf_counter() - started) * 1000)
            return result
        except Exception as exc:  # noqa: BLE001
            self.record_failure(provider, str(exc))
            if fallback_fn:
                return await fallback_fn(provider, exc)
            raise


provider_manager = ProviderManager()
