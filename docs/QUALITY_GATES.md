# Quality Gates

## Purpose

Quality gates enforce newsroom safety before chief approval and manual publish readiness.

The system evaluates structured checks and classifies issues by severity:

- `info`: optional quality suggestions.
- `warn`: quality degradation that should be reviewed.
- `blocker`: must be fixed before progressing.

## Active checks

Current submission gate aggregation (see `backend/app/services/quality_gate_service.py`):

- `FACT_CHECK`
- `SEO_TECH`
- `READABILITY`
- `QUALITY_SCORE`
- `EDITORIAL_POLICY` (if policy report is available)

If any stage report is missing, it is treated as a `blocker`.

## Output contract

Domain output model (`app/domain/quality/gates.py`):

```json
{
  "passed": false,
  "issues": [
    {
      "code": "fact_check_failed",
      "message": "Claim verification threshold not met",
      "severity": "blocker",
      "details": {"stage": "FACT_CHECK"}
    }
  ]
}
```

## Workflow integration

### During draft submission to chief

`_submit_draft_for_chief_approval` computes a gate result:

- `passed=true` -> status can move to `ready_for_chief_approval`.
- `passed=false` -> status moves to `approval_request_with_reservations`.

### During chief decision

Chief can:

- `approve` (after publish gate checks)
- `approve_with_reservations` (reason required)
- `send_back`
- `reject` (reason required)

## Operational guidance

- Track blockers in `article_quality_reports` and policy report payloads.
- Use `dashboard/ops/overview` and job logs for failure distribution and latency.
- Never bypass gate blockers with direct DB state edits.
