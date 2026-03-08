# Provider Routing Cost (Epic 7 - Phase 1)

This document describes the current cost-aware provider routing behavior for AI calls.

## Goals
- Keep provider fallback and health/circuit-breaker behavior.
- Add budget-aware routing without blocking newsroom workflows.
- Degrade gracefully to a cheaper provider when budget caps are hit.

## Config

```env
PROVIDER_DAILY_BUDGET_USD=12.0
PROVIDER_PER_JOB_MAX_USD=0.20
PROVIDER_COST_ESTIMATE_GEMINI_USD=0.03
PROVIDER_COST_ESTIMATE_GROQ_USD=0.015
PROVIDER_QUEUE_TIER_SCRIBE=balanced
PROVIDER_QUEUE_TIER_QUALITY=high
PROVIDER_QUEUE_TIER_SIMULATOR=balanced
PROVIDER_QUEUE_TIER_ROUTER=low
```

Equivalent `ECHOROUK_OS_...` prefixed variables are supported as well.

## Routing Rules

1. Provider health is checked first (circuit-open providers are excluded).
2. Queue tier + urgency pick a preferred provider:
   - `high` -> prefer `gemini`
   - `low` -> prefer `groq`
   - `balanced` -> weighted selection (`provider_weight_*`)
3. Budget check:
   - If daily budget is exhausted OR preferred call cost exceeds per-job cap,
     route to the cheapest eligible provider.
4. If degraded by budget, system logs `provider_routed_degraded`.

## Health Endpoint

`GET /api/v1/jobs/providers/health`

Now includes:
- per-provider `estimated_cost_usd_per_call`
- `_budget` block:
  - `daily_budget_usd`
  - `daily_spend_usd`
  - `daily_budget_ratio`

## Notes
- Spend tracking is currently in-memory (per-process).
- This phase is intentionally non-blocking: if budget is tight, calls still run on the cheaper provider.
