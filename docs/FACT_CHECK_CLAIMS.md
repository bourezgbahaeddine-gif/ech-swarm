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
- `risk_level` (`low|medium|high`)
- `confidence`
- `sensitive`
- `evidence_links`
- `unverifiable`
- `unverifiable_reason`
- `supported`
- `support_count`

Response also includes:

- `claim_coverage.high_risk_total`
- `claim_coverage.high_risk_supported`
- `claim_coverage.high_risk_documented_unverifiable`
- `claim_coverage.high_risk_unsupported`
- `claim_coverage.percent_high_risk_supported`
- `persisted.claims_upserted`
- `persisted.supports_upserted`

## Gate Behavior

Claim support gate runs under `FACT_CHECK` in `run_submission_quality_gates`:

- Sensitive claim without evidence and without valid unverifiable reason:
  - `code=claim_support_required`
  - `severity=blocker`
- Sensitive claim marked `unverifiable=true` with non-empty reason:
  - `code=claim_unverifiable_marked`
  - `severity=info`

FACT_CHECK output also adds a hard blocker reason when unsupported high-risk claims exist:

- `High-risk claims are missing support links or documented unverifiable reasons.`

Strict option:

- `ECHOROUK_OS_QUALITY_CLAIM_REQUIRE_NON_AGGREGATOR_SUPPORT=true`
  - aggregator-only links do not satisfy support requirement.

## UI Notes

Workspace editor shows:

- Per-claim evidence links input
- Per-claim `unverifiable` toggle + reason field
- On `verify`, current overrides are sent to backend and reflected in gate results.

Accepted evidence formats:

- URL (`https://...`)
- Document Intel refs (`docintel:...`, `document-intel:...`, `doc:...`, `di://...`)

## Persistence Model

Claims are persisted in dedicated tables:

- `article_claims`
- `article_claim_supports`

This keeps claim/support history queryable outside `article_quality_reports.report_json`.

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
- `claim_coverage` block in FACT_CHECK response
- `persisted` counters in FACT_CHECK response

SQL sanity:

```sql
SELECT article_id, claim_external_id, risk_level, supported, unverifiable
FROM article_claims
ORDER BY updated_at DESC
LIMIT 30;

SELECT claim_id, support_kind, support_ref
FROM article_claim_supports
ORDER BY id DESC
LIMIT 50;
```
