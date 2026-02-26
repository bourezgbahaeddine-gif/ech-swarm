# PROJECT KNOWLEDGE BASE

## 1) Project Summary
Echorouk Swarm is an editorial operations platform that ingests news from feeds, routes and classifies content, prepares drafts, and exposes dashboard workflows for newsroom users.

Core objective:
- Keep a continuous, reliable, and auditable news pipeline.
- Prioritize freshness, local relevance, and editorial control.
- Enforce human-in-the-loop for publication decisions.

## 2) Core Domains
- Ingestion: Scout agent collects items from RSS/FreshRSS and applies dedup + freshness gates.
- Classification: Router agent categorizes, scores, and marks urgency/breaking.
- Drafting: Scribe agent prepares candidate draft output.
- Monitoring: Published quality monitor, trends scan, and ops metrics.
- Editorial: Manual review and decision workflow.

## 3) Technical Stack
- Backend:
  - Python 3.11+
  - FastAPI
  - SQLAlchemy (async), Alembic
  - Celery + Redis (queues and async workers)
  - PostgreSQL (with pgvector)
- Frontend:
  - Next.js 16 (App Router)
  - React 19
  - TypeScript
  - React Query + Axios
  - Tailwind CSS v4
- Infra:
  - Docker Compose
  - Optional FreshRSS + RSSBridge
  - MinIO for object storage

## 4) Repository Layout
- `backend/`
  - `app/core/`: settings, db, logging
  - `app/models/`: ORM models and enums
  - `app/api/routes/`: REST endpoints
  - `app/agents/`: scout/router/scribe/trends/published monitor
  - `app/services/`: AI, cache, notifications, job orchestration
  - `app/utils/`: hashing, text utilities
  - `tests/`: backend tests
- `frontend/`
  - `src/app/`: page routes
  - `src/components/`: reusable UI
  - `src/lib/`: API client, auth, providers, helpers
- `docs/`: design and architecture docs
- `scripts/`: operational SQL/shell/python scripts
- `docker-compose.yml`: full local/production-like stack

## 5) Pipeline State Model (Article)
Primary status progression:
- `new -> classified -> candidate -> approved/rejected -> draft_generated -> archived/published`

Operational notes:
- Freshness filters must prevent stale entries from staying in `new/classified/candidate`.
- `breaking` must expire by TTL.
- Dedup is both exact and near-duplicate aware.

## 6) Runtime Components
- API container (`backend`) for REST endpoints and scheduler hooks.
- Worker container (`worker`) for Celery tasks.
- Redis for queue/cache/idempotency helpers.
- PostgreSQL as source of truth.

## 7) Configuration Principles
- All runtime behavior via env vars (`ECHOROUK_OS_*`).
- No hardcoded secrets.
- Feature switches for FreshRSS mode, auto pipeline, trends, and monitor jobs.

## 8) Observability
- Structured logs for task lifecycle and pipeline ticks.
- Ops endpoints expose throughput, latency, queue depth, and state age.
- Key logs:
  - `scout_run_complete`
  - `router_batch_complete`
  - `auto_pipeline_tick_done`
  - `published_monitor_scan_complete`
