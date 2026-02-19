# Session Checkpoint - 2026-02-19

## Current Status
- Platform is running after backend/frontend rebuild.
- MSI is working (profiles + run + report + timeseries).
- M7 `محاكي الجمهور` is implemented (Graph + API + UI page + Smart Editor button/tab).

## Incidents Resolved Today
1. Constitution gate blocking all navigation:
- Root cause: no active constitution record in DB.
- Fix:
  - `GET /constitution/latest` and `GET /constitution/ack` now return safe fallback when metadata is missing.
  - `POST /constitution/ack` auto-seeds minimal `ConstitutionMeta` if requested version does not exist.

2. Simulator endpoint 500 on `/api/v1/sim/run`:
- Root cause: simulator tables not migrated or missing.
- Fix:
  - Clear server message when `sim_runs` table is missing.
  - Runbook updated to enforce `alembic upgrade head` after pull.

3. Editor warnings/errors:
- Tiptap duplicate extension `link` fixed in Smart Editor.
- News article HTML render hardened to normalize unsafe full-document HTML wrappers.

## M7 Scope Delivered
- DB: `sim_runs`, `sim_results`, `sim_feedback`, `sim_calibration`, `sim_job_events`
- API:
  - `POST /api/v1/sim/run`
  - `GET /api/v1/sim/runs/{run_id}`
  - `GET /api/v1/sim/result`
  - `GET /api/v1/sim/history`
  - `GET /api/v1/sim/live` (SSE)
- Frontend:
  - `/simulator`
  - Sidebar item: `محاكي الجمهور`
  - Smart Editor integration: action button + result panel

## Mandatory Post-Deploy Checks
```bash
curl -sS http://127.0.0.1:8000/health
docker compose run --rm backend alembic upgrade head
docker exec -i ech-postgres psql -U echorouk -d echorouk_db -c "\dt sim_*"
docker exec -i ech-postgres psql -U echorouk -d echorouk_db -c "SELECT version,is_active FROM constitution_meta ORDER BY updated_at DESC LIMIT 5;"
```

## Quick Functional Smoke Test
```bash
TOKEN=$(curl -sS -X POST http://127.0.0.1:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"bourezgb","password":"password123"}' \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')

RUN=$(curl -sS -X POST http://127.0.0.1:8000/api/v1/sim/run \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"headline":"عنوان تجريبي","excerpt":"نص مختصر للتجربة","platform":"facebook","mode":"fast"}')

echo "$RUN"
RUN_ID=$(echo "$RUN" | python3 -c 'import sys,json; print(json.load(sys.stdin)["run_id"])')
curl -sS "http://127.0.0.1:8000/api/v1/sim/runs/$RUN_ID" -H "Authorization: Bearer $TOKEN"
curl -sS "http://127.0.0.1:8000/api/v1/sim/result?run_id=$RUN_ID" -H "Authorization: Bearer $TOKEN"
```

## Open Risks
- Existing unrelated dirty files remain in working tree and should not be committed with this release:
  - `backend/app/models/knowledge.py`
  - `backend/app/services/news_knowledge_service.py`
  - `frontend/src/app/memory/page.tsx`
