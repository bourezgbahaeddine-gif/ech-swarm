from __future__ import annotations

from app.services.provider_manager import ProviderManager


def test_pick_with_context_prefers_high_tier(monkeypatch):
    manager = ProviderManager()
    monkeypatch.setattr(manager, "_is_configured", lambda _provider: True)

    decision = manager.pick_with_context({"queue_name": "ai_quality", "urgency": "normal"})

    assert decision.provider == "gemini"
    assert decision.degraded is False


def test_pick_with_context_degrades_when_budget_exceeded(monkeypatch):
    manager = ProviderManager()
    monkeypatch.setattr(manager, "_is_configured", lambda _provider: True)
    manager._daily_spend_usd_by_date[manager._today_key()] = 99999.0

    decision = manager.pick_with_context({"queue_name": "ai_quality", "urgency": "high"})

    assert decision.provider == "groq"
    assert decision.degraded is True
    assert decision.reason == "budget_cap"


def test_health_reports_budget_snapshot(monkeypatch):
    manager = ProviderManager()
    monkeypatch.setattr(manager, "_is_configured", lambda _provider: True)
    manager.record_success("groq", 12.0, cost_estimate_usd=0.015)

    health = manager.health()

    assert "_budget" in health
    assert health["_budget"]["daily_spend_usd"] >= 0.015
    assert "estimated_cost_usd_per_call" in health["groq"]
