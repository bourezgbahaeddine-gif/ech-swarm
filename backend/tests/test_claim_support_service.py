from app.services.claim_support_service import claim_support_service


def test_normalize_support_refs_accepts_urls_and_docintel_refs():
    refs = claim_support_service.normalize_support_refs(
        [
            "https://example.com/a",
            "http://example.com/b",
            "docintel:chunk-22",
            "di://memo/123",
            "not-valid",
            "",
        ]
    )
    support_refs = {item["support_ref"] for item in refs}
    kinds = {item["support_kind"] for item in refs}

    assert "https://example.com/a" in support_refs
    assert "docintel:chunk-22" in support_refs
    assert "not-valid" not in support_refs
    assert "url" in kinds
    assert "doc_intel_ref" in kinds


def test_enrich_fact_check_report_blocks_unsupported_high_risk_claims():
    report = {
        "stage": "FACT_CHECK_PASSED",
        "passed": True,
        "score": 100,
        "claims": [
            {
                "id": "clm-1",
                "text": "GDP reached 5.1%",
                "claim_type": "number",
                "confidence": 0.91,
                "evidence_links": [],
                "unverifiable": False,
                "unverifiable_reason": "",
            },
            {
                "id": "clm-2",
                "text": "Official said project starts next month.",
                "claim_type": "statement",
                "confidence": 0.72,
                "evidence_links": ["https://example.com/proof"],
                "unverifiable": False,
                "unverifiable_reason": "",
            },
        ],
        "blocking_reasons": [],
        "actionable_fixes": [],
    }

    enriched = claim_support_service.enrich_fact_check_report(report)

    assert enriched["passed"] is False
    assert "High-risk claims are missing support links or documented unverifiable reasons." in enriched["blocking_reasons"]
    assert enriched["claim_coverage"]["high_risk_total"] == 1
    assert enriched["claim_coverage"]["high_risk_supported"] == 0
    assert enriched["claim_coverage"]["high_risk_unsupported"] == 1
    assert enriched["unsupported_high_risk_claim_ids"] == ["clm-1"]


def test_enrich_fact_check_report_counts_documented_unverifiable_as_covered():
    report = {
        "stage": "FACT_CHECK_PASSED",
        "passed": True,
        "score": 100,
        "claims": [
            {
                "id": "clm-9",
                "text": "Sensitive date claim.",
                "claim_type": "date",
                "confidence": 0.89,
                "evidence_links": [],
                "unverifiable": True,
                "unverifiable_reason": "No public source published yet.",
            }
        ],
        "blocking_reasons": [],
        "actionable_fixes": [],
    }

    enriched = claim_support_service.enrich_fact_check_report(report)

    assert enriched["passed"] is True
    assert enriched["claim_coverage"]["high_risk_total"] == 1
    assert enriched["claim_coverage"]["high_risk_supported"] == 0
    assert enriched["claim_coverage"]["high_risk_documented_unverifiable"] == 1
    assert enriched["claim_coverage"]["high_risk_unsupported"] == 0
    assert "unsupported_high_risk_claim_ids" not in enriched
