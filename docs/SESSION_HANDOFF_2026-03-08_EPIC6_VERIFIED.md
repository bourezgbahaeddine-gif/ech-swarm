# Session Handoff - 2026-03-08 - Epic 6 Verified on Server

## Deployment State
- Server updated and running latest `main`.
- Services rebuilt and started successfully:
  - `backend`, `worker`, `frontend` images built.
  - core containers healthy/running.
- Health probe succeeded: `HEALTH_OK`.

## Verification Results

### 1) Queue SLA Endpoint
- Endpoint: `GET /api/v1/jobs/sla?lookback_hours=24`
- Result: **OK (200)** with expected JSON payload:
  - `generated_at`
  - `lookback_hours`
  - `failure_rate_threshold_percent`
  - `queues[]` with:
    - `queue_name`
    - `depth`, `depth_limit`
    - `oldest_task_age`
    - `mean_runtime`
    - `failure_rate_24h`
    - `SLA_target_minutes`
    - `SLA_breached`

### 2) Structured Backpressure (429)
- Scenario: worker stopped + synthetic queue pressure (`ai_router` depth 220).
- Endpoint: `POST /api/v1/dashboard/agents/router/run?limit=10`
- Result: **OK (429 behavior as expected)**:
  - `error.code = "http_error"`
  - `error.details` is an **object** (not string).
  - Required fields present:
    - `queue_name`
    - `current_depth`
    - `depth_limit`
    - `retry_after_seconds`
  - Sample returned:
    - `queue_name: "ai_router"`
    - `current_depth: 220`
    - `depth_limit: 200`
    - `retry_after_seconds: 20`

## Important Observation
- `jobs/sla` currently shows SLA breaches for `ai_router` and `ai_msi` due very high `oldest_task_age` while queue depth is `0`.
- Likely cause: stale `queued/running` DB job rows (historical), not active Redis backlog.

## Recommended Next Session
1. Validate and clean stale job rows (recover/reconcile stuck jobs).
2. Re-check `GET /api/v1/jobs/sla` after cleanup.
3. Optional hardening: consider ignoring `oldest_task_age` when queue depth is `0`, or enforce stricter stale-state reconciliation.

## Resume Commands
```bash
cd ~/ech-swarm
git fetch origin
git pull --ff-only origin main
docker compose up -d --build --force-recreate backend worker frontend
until curl -fsS http://127.0.0.1:8000/health >/dev/null; do sleep 2; done
echo "HEALTH_OK"
```
