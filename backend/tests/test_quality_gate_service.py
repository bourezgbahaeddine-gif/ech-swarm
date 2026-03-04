from types import SimpleNamespace

from app.domain.quality.gates import GateIssue, GateResult, GateSeverity
from app.services.quality_gate_service import quality_gate_service


class _DummySettings:
    quality_claim_support_enforcement_enabled = True
    quality_claim_sensitive_threshold = 0.80
    quality_claim_require_non_aggregator_support = False


def _mock_settings(monkeypatch, **overrides):
    data = _DummySettings()
    for key, value in overrides.items():
        setattr(data, key, value)
    monkeypatch.setattr("app.services.quality_gate_service.get_settings", lambda: data)


def test_claim_support_gate_adds_blocker_for_sensitive_claim_without_support(monkeypatch):
    _mock_settings(monkeypatch, quality_claim_require_non_aggregator_support=False)
    report = SimpleNamespace(
        report_json={
            "claims": [
                {
                    "id": "clm-1",
                    "text": "Budget reached 12 billion in 2026.",
                    "claim_type": "number",
                    "confidence": 0.91,
                    "evidence_links": [],
                    "unverifiable": False,
                    "unverifiable_reason": "",
                }
            ]
        }
    )

    issues = quality_gate_service._claim_support_gate_issues(report)
    assert len(issues) == 1
    assert issues[0].code == "claim_support_required"
    assert issues[0].severity == GateSeverity.BLOCKER


def test_claim_support_gate_allows_unverifiable_with_reason(monkeypatch):
    _mock_settings(monkeypatch)
    report = SimpleNamespace(
        report_json={
            "claims": [
                {
                    "id": "clm-2",
                    "text": "Unofficial witness claim.",
                    "claim_type": "statement",
                    "confidence": 0.86,
                    "sensitive": True,
                    "evidence_links": [],
                    "unverifiable": True,
                    "unverifiable_reason": "No public source can confirm this yet.",
                }
            ]
        }
    )

    issues = quality_gate_service._claim_support_gate_issues(report)
    assert len(issues) == 1
    assert issues[0].code == "claim_unverifiable_marked"
    assert issues[0].severity == GateSeverity.INFO


def test_claim_support_gate_rejects_aggregator_only_links_when_strict(monkeypatch):
    _mock_settings(monkeypatch, quality_claim_require_non_aggregator_support=True)
    report = SimpleNamespace(
        report_json={
            "claims": [
                {
                    "id": "clm-3",
                    "text": "Economic growth was 4.2%.",
                    "claim_type": "number",
                    "confidence": 0.9,
                    "evidence_links": ["https://news.google.com/articles/demo"],
                    "unverifiable": False,
                    "unverifiable_reason": "",
                }
            ]
        }
    )

    issues = quality_gate_service._claim_support_gate_issues(report)
    assert len(issues) == 1
    assert issues[0].code == "claim_support_required"
    assert issues[0].severity == GateSeverity.BLOCKER


def test_summarize_gate_result_uses_warn_bucket():
    gate_result = GateResult(
        passed=False,
        issues=[
            GateIssue(code="a", message="warn issue", severity=GateSeverity.WARN, details={}),
            GateIssue(code="b", message="blocker issue", severity=GateSeverity.BLOCKER, details={}),
            GateIssue(code="c", message="info issue", severity=GateSeverity.INFO, details={}),
        ],
    )
    summary = quality_gate_service.summarize_gate_result(gate_result)

    assert summary["counts"]["blocker"] == 1
    assert summary["counts"]["warn"] == 1
    assert summary["counts"]["info"] == 1
    assert "warning" not in summary["counts"]
