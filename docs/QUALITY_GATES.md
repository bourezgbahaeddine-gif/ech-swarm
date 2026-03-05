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
- `approve_with_reservations` (reason required, with explicit blocker override trail)
- `send_back`
- `reject` (reason required)

When chief chooses `approve_with_reservations`, backend now returns:

- `overridden_blockers`: list of blocker messages that were explicitly overridden.

This list is also persisted in transition/audit details for traceability.

## RBAC and Transition Guarantees

- Chief override endpoint (`/editorial/{article_id}/chief/final-decision`) is restricted to:
  - `director`
  - `editor_chief`
- `approve_with_reservations` and `reject` require a mandatory reason.
- `approve` path still enforces publish gate checks and blocks on unresolved blockers.
- Journalists cannot execute chief override path.

## Claim Support Rule

`FACT_CHECK` includes a claim support sub-gate:

- Sensitive claim without support link => `blocker` (`claim_support_required`)
- Claim marked as unverifiable **with reason** => `info` (`claim_unverifiable_marked`)
- Optional strict mode can reject aggregator-only evidence links

Related config:

- `ECHOROUK_OS_QUALITY_CLAIM_SUPPORT_ENFORCEMENT_ENABLED=true|false`
- `ECHOROUK_OS_QUALITY_CLAIM_SENSITIVE_THRESHOLD=0.80`
- `ECHOROUK_OS_QUALITY_CLAIM_REQUIRE_NON_AGGREGATOR_SUPPORT=true|false`

## Operational Notes

Quick verification commands:

```bash
TOKEN=$(curl -fsS -X POST "http://127.0.0.1:8000/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"bourezgb","password":"password123"}' \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')

curl -fsS "http://127.0.0.1:8000/api/v1/editorial/workspace/drafts/<WORK_ID>/publish-readiness" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

Expected:

- `gates.counts` includes `blocker|warn|info`
- `gates.items[*].severity` uses `blocker|warn|info`
- chief `approve_with_reservations` response includes `overridden_blockers` when blockers exist

## Operational guidance

- Track blockers in `article_quality_reports` and policy report payloads.
- Use `dashboard/ops/overview` and job logs for failure distribution and latency.
- Never bypass gate blockers with direct DB state edits.

## Roadmap Status (`docs/news AGENTS.md`)

- Epic 3 (Quality Gates 2.0): in progress; severity and chief override trail implemented, tests extended for chief decision flow and RBAC checks.
