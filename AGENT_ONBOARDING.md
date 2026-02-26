# AGENT ONBOARDING

## Purpose
This file defines the minimum startup sequence for any coding agent working on this repository.

## Mandatory Read Order
1. `PROJECT_KNOWLEDGE_BASE.md`
2. `DEVELOPMENT_GUIDELINES.md`
3. `STATE_DATA_MANAGEMENT.md`
4. `STYLING_RULES.md`
5. `TECHNICAL_CONTEXT_TYPES.md`
6. `TECHNICAL_CONTEXT_CONFIG.md`
7. `IMPLEMENTATION_PLAN.md`

## First Actions Before Any Code Change
1. Confirm target scope (backend, frontend, infra, or docs).
2. Identify impacted models/status transitions if touching pipeline logic.
3. Identify impacted API contracts if touching routes/services.
4. For frontend changes, verify theme compatibility (light/dark) and RTL support.

## Change Safety Rules
- Do not bypass freshness/dedup/breaking constraints in pipeline code.
- Do not introduce hardcoded secrets or environment-specific constants.
- Keep enum-driven status/category usage consistent with backend models.
- Update documentation files when behavior or contracts change.

## Validation Checklist
- Backend syntax/tests pass for touched modules.
- Frontend lint/build passes for touched modules.
- API contracts updated in `frontend/src/lib/api.ts` when endpoints change.
- README section `Agent Documentation Bundle` remains current.
