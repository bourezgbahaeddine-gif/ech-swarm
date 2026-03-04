from app.queue.tasks.ai_tasks import _apply_claim_overrides


def test_apply_claim_overrides_merges_links_and_unverifiable_fields():
    report = {
        "claims": [
            {
                "id": "clm-1",
                "text": "Claim text",
                "evidence_links": ["https://source-a.example/x"],
                "unverifiable": False,
                "unverifiable_reason": "",
            }
        ]
    }
    overrides = [
        {
            "claim_id": "clm-1",
            "evidence_links": ["https://source-b.example/y", "javascript:alert(1)"],
            "unverifiable": True,
            "unverifiable_reason": "No official source available yet.",
        }
    ]

    _apply_claim_overrides(report, overrides)

    claim = report["claims"][0]
    assert claim["evidence_links"] == [
        "https://source-a.example/x",
        "https://source-b.example/y",
    ]
    assert claim["unverifiable"] is True
    assert claim["unverifiable_reason"] == "No official source available yet."


def test_apply_claim_overrides_ignores_unknown_claim_ids():
    report = {"claims": [{"id": "known", "evidence_links": []}]}
    overrides = [{"claim_id": "unknown", "evidence_links": ["https://source.example/a"]}]

    _apply_claim_overrides(report, overrides)

    assert report["claims"][0]["evidence_links"] == []
