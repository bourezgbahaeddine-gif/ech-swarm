# Session Handoff - 2026-03-05 - Queue SLA & Backpressure

## Status Summary
- Deployment/build succeeded and services are healthy (`HEALTH_OK`).
- Auth login works and token generation is OK.
- `GET /api/v1/jobs/sla` returned `404` (endpoint not available on deployed backend).
- Backpressure test returned `429`, but payload is **old format**:
  - `error.details` is a plain string.
  - Missing structured fields: `queue_name`, `current_depth`, `depth_limit`, `retry_after_seconds`.

## Conclusion
- Epic 6 is **not deployed** on server yet.
- Current runtime code is still pre-Epic6 behavior.

## Evidence (from server run)
- `curl ... /api/v1/jobs/sla?lookback_hours=24` -> `404`.
- `POST /api/v1/dashboard/agents/router/run` during queue pressure -> `429` with:
  - `"details": "Queue busy for pipeline_router (220/200). Retry in a moment."`
  - `HAS_REQUIRED_FIELDS = False`

## Required Before Next Verification
1. Push backend/frontend changes containing:
   - `/api/v1/jobs/sla` route
   - standardized 429 backpressure payload
   - agents page Jobs Health section
2. On server, redeploy from commit containing these changes.
3. Re-run verification commands for:
   - `/api/v1/jobs/sla` (should return JSON with `queues[]`)
   - 429 payload shape + `Retry-After` header.

## Resume Commands (Server)
```bash
cd ~/ech-swarm
git fetch origin
git switch -C deploy-origin-main origin/main
git rev-parse --short HEAD
docker compose up -d --build --force-recreate backend worker frontend
until curl -fsS http://127.0.0.1:8000/health >/dev/null; do sleep 2; done
echo "HEALTH_OK"
```

