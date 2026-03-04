# Fact Check Claims Workflow

## Goal

Support Human-in-the-Loop fact checking by attaching evidence links (or documented unverifiable reasons) to sensitive claims before chief approval.

## Data Shape

`POST /api/v1/editorial/workspace/drafts/{work_id}/verify/claims`

Request body:

```json
{
  "threshold": 0.7,
  "claim_overrides": [
    {
      "claim_id": "clm-3",
      "evidence_links": ["https://example.org/source-a"],
      "unverifiable": false,
      "unverifiable_reason": ""
    }
  ]
}
```

Response includes extracted claims:

- `id`
- `text`
- `claim_type`
- `confidence`
- `sensitive`
- `evidence_links`
- `unverifiable`
- `unverifiable_reason`

## Gate Behavior

Claim support gate runs under `FACT_CHECK` in `run_submission_quality_gates`:

- Sensitive claim without evidence and without valid unverifiable reason:
  - `code=claim_support_required`
  - `severity=blocker`
- Sensitive claim marked `unverifiable=true` with non-empty reason:
  - `code=claim_unverifiable_marked`
  - `severity=info`

Strict option:

- `ECHOROUK_OS_QUALITY_CLAIM_REQUIRE_NON_AGGREGATOR_SUPPORT=true`
  - aggregator-only links do not satisfy support requirement.

## UI Notes

Workspace editor shows:

- Per-claim evidence links input
- Per-claim `unverifiable` toggle + reason field
- On `verify`, current overrides are sent to backend and reflected in gate results.

## Operational Checks

```bash
TOKEN=$(curl -fsS -X POST "http://127.0.0.1:8000/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"bourezgb","password":"password123"}' \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')

curl -fsS -X POST "http://127.0.0.1:8000/api/v1/editorial/workspace/drafts/<WORK_ID>/verify/claims" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"threshold":0.7,"claim_overrides":[{"claim_id":"clm-1","evidence_links":["https://example.org/doc"]}]}' \
  | python3 -m json.tool

curl -fsS "http://127.0.0.1:8000/api/v1/editorial/workspace/drafts/<WORK_ID>/publish-readiness" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

Look for:

- `gates.items` containing `claim_support_required` when support is missing
- `gates.items` containing `claim_unverifiable_marked` when manually documented
