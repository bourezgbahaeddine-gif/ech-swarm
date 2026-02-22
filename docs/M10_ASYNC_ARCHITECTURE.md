# M10 Async Job Architecture (FastAPI + Celery)

## 1) Folder Structure (Proposed + Implemented)

```text
backend/
  app/
    api/
      routes/
        jobs.py                # job status, retry, queue depth, provider health, DLQ
        dashboard.py           # enqueue-only agent triggers
        editorial.py           # enqueue-only heavy AI ops
        msi.py                 # enqueue MSI runs
        simulator.py           # enqueue simulator runs
    core/
      correlation.py           # request_id / correlation_id context helpers
      config.py                # queue/backpressure/provider settings
    models/
      job_queue.py             # JobRun + DeadLetterJob tables
    queue/
      celery_app.py            # Celery app + routing
      tasks/
        ai_tasks.py            # editorial AI tasks in workers
        pipeline_tasks.py      # router/scribe/msi/simulator/trends/published-monitor tasks
    services/
      job_queue_service.py     # enqueue, backpressure, status, DLQ
      provider_manager.py      # health + weighted routing + circuit breaker
```

## 2) Modified Backend Structure

- HTTP handlers now enqueue jobs for AI-heavy operations and return immediately.
- Worker tasks read payload from `job_runs.payload_json`, execute logic, then update status/result.
- Backpressure is applied before enqueue using Redis queue depth thresholds.
- Retries use Celery `autoretry_for + retry_backoff + retry_jitter`.
- Final failures are written to `dead_letter_jobs`.
- Correlation IDs are propagated:
  - Request middleware writes `x-request-id`, `x-correlation-id`.
  - Job record persists both IDs.
  - Worker binds them into structured logging context.

## 3) Example Worker Implementation

Reference: `backend/app/queue/tasks/ai_tasks.py`

- Task: `run_editorial_ai_job`
- Steps:
  1. load `job_runs` row by `job_id`
  2. mark `running` + increment attempts
  3. execute operation (`rewrite`, `seo`, `quality`, `claims`, `links_suggest`, ...)
  4. write `result_json` and mark `completed`
  5. on error:
     - mark `failed` for retriable attempts
     - move to DLQ on final attempt

## 4) Example Refactored Endpoint (enqueue-only)

Reference: `backend/app/api/routes/editorial.py`

`POST /api/v1/editorial/workspace/drafts/{work_id}/ai/seo`

Behavior now:
- Validate auth + draft existence
- check backpressure for `ai_quality`
- create row in `job_runs`
- enqueue Celery task
- return:

```json
{
  "job_id": "uuid",
  "status": "queued",
  "work_id": "WRK-...",
  "operation": "seo"
}
```

## 5) Provider Manager Skeleton

Reference: `backend/app/services/provider_manager.py`

Implemented:
- provider health snapshot
- weighted selection (`provider_weight_gemini`, `provider_weight_groq`)
- circuit breaker (`provider_circuit_failures`, `provider_circuit_open_sec`)
- latency tracking (rolling p50 approximation)
- fallback call path

Current integration:
- `ai_service.rewrite_article` routes via provider manager.

## 6) Queue Monitoring Strategy

### API Monitoring

- `GET /api/v1/jobs`
- `GET /api/v1/jobs/{job_id}`
- `POST /api/v1/jobs/{job_id}/retry`
- `GET /api/v1/jobs/queues/depth`
- `GET /api/v1/jobs/providers/health`
- `GET /api/v1/jobs/dead-letter`

### Infrastructure Monitoring

- Celery Worker service in Docker: `worker`
- Flower UI service in Docker: `flower` at `:5555`
- Queue depth thresholds in settings:
  - `queue_depth_limit_router`
  - `queue_depth_limit_scribe`
  - `queue_depth_limit_quality`
  - `queue_depth_limit_simulator`
  - `queue_depth_limit_msi`
  - `queue_depth_limit_links`

### Operational Rules

- Reject enqueue with HTTP `429` when queue depth exceeds threshold.
- Keep editorial pages responsive by returning ticket immediately.
- Operators inspect failed jobs in `/jobs/dead-letter` then retry selected jobs.

