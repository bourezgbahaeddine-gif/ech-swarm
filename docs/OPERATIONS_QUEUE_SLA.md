# Operations: Queue SLA & Backpressure

This document explains queue SLA observability and standardized backpressure behavior.

## Endpoint: `GET /api/v1/jobs/sla`

Returns per-queue health for the last `lookback_hours` window (default: `24`).

Query params:
- `lookback_hours` (optional, `1..168`)

Example:

```bash
curl -sS "http://127.0.0.1:8000/api/v1/jobs/sla?lookback_hours=24" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

Response shape:

```json
{
  "generated_at": "2026-03-05T12:00:00.000000",
  "lookback_hours": 24,
  "failure_rate_threshold_percent": 25.0,
  "queues": [
    {
      "queue_name": "ai_router",
      "depth": 12,
      "depth_limit": 200,
      "oldest_task_age": 6.4,
      "mean_runtime": 2.1,
      "failure_rate_24h": 4.2,
      "SLA_target_minutes": 10,
      "SLA_breached": false,
      "active_running_jobs": 1,
      "active_queued_jobs": 11,
      "state_drift_suspected": false
    }
  ]
}
```

Metric semantics:
- `depth`: current Redis queue length.
- `oldest_task_age`: minutes for actionable backlog age.
  - When `depth > 0`: based on oldest queued/running active task.
  - When `depth == 0`: only running-age is considered; queued-age is ignored to avoid stale DB false positives.
- `mean_runtime`: average task runtime in minutes over lookback window.
- `failure_rate_24h`: percentage of failed/dead-lettered tasks over finished tasks in lookback window.
- `SLA_target_minutes`: configured target per queue.
- `SLA_breached`: true when any breach rule triggers (depth pressure, age/runtime over target, or high failure rate).
- `active_running_jobs`: count of `running` jobs in DB.
- `active_queued_jobs`: count of `queued` jobs in DB.
- `state_drift_suspected`: `true` when DB shows queued jobs while Redis depth is zero (candidate stale state).

## Standardized 429 Backpressure Payload

All queue-backed endpoints return a structured payload when backpressure blocks enqueueing:

```json
{
  "queue_name": "ai_quality",
  "current_depth": 345,
  "depth_limit": 300,
  "retry_after_seconds": 20,
  "message": "Queue busy for editorial_rewrite. Retry shortly."
}
```

Also, `Retry-After` response header is set.

## Flower

Default URL in Docker Compose:
- `http://127.0.0.1:5555`

Use Flower to inspect:
- active/queued tasks
- failed tasks and traceback
- worker heartbeat and queue pressure

## Runbook

1. `depth >= depth_limit`
- Reduce manual trigger bursts.
- Scale worker concurrency or add workers.

2. `failure_rate_24h` high
- Inspect failed tasks in Flower.
- Fix repeated upstream/provider/parser errors.

3. `oldest_task_age` high
- Recover stale jobs:

```bash
curl -sS -X POST "http://127.0.0.1:8000/api/v1/jobs/recover/stale?stale_running_minutes=15&stale_queued_minutes=30" \
  -H "Authorization: Bearer $TOKEN"
```
