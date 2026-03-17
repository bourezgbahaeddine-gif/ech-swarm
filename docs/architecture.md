# Echorouk Editorial OS — Architecture

Last updated: 2026-03-17

## 1) System Overview
Echorouk Editorial OS is a newsroom operating system that manages the editorial lifecycle from signal capture to manual-publish readiness.

It combines:
- ingestion and deduplication
- AI-assisted classification and drafting
- human editing and quality review
- chief approval and governance
- archive, knowledge, and digital execution layers

## 2) Product Architecture
The platform is organized around five product layers:

1. Daily orchestration
   - `/today`
   - role-aware queues and next actions

2. Editorial execution
   - `/news`
   - `/workspace-drafts`
   - `/editorial`
   - `/stories`
   - `/events`

3. Support and knowledge
   - `/archive`
   - `/memory`
   - `/services/document-intel`
   - `/services/media-logger`

4. Advanced tools
   - `/digital`
   - `/trends`
   - `/simulator`
   - `/competitor-xray`
   - `/scripts`

5. Operational visibility
   - `/ux-insights`
   - `/agents`
   - `/sources`
   - `/settings`
   - `/team`

## 3) Core Editorial Flow

```text
RSS/FreshRSS/RSS-Bridge
        -> Scout
        -> Router
        -> Scribe
        -> Smart Editor
        -> Quality Gates
        -> Chief Approval
        -> Ready for Manual Publish
```

## 4) News Status Lifecycle
Primary lifecycle states:

```text
new
-> cleaned
-> deduped
-> classified
-> candidate
-> approved / approved_handoff
-> draft_generated
-> ready_for_chief_approval / approval_request_with_reservations
-> ready_for_manual_publish
-> published / archived
```

Canonical status logic is defined in:
- `backend/app/models/news.py`
- `backend/app/domain/news/state_machine.py`

## 5) Smart Editor Flow

```text
Writing Stage
-> Save
-> Review Stage
-> Proofread / Claims / Quality / Readiness
-> Send for Chief Approval
```

The editor was recently simplified so the default journalist experience starts in a quiet writing-first surface, with review tooling shown later.

## 6) Digital Desk Flow

```text
Trigger Sources
(programs / events / breaking / manual)
-> social_tasks
-> compose
-> social_post_versions
-> approval / scheduling / dispatch
```

Digital Desk currently supports:
- Execute / Compose / Planning modes
- Now / Next / At Risk sections
- Next Best Action
- explainability
- post versioning
- bundles
- delivery layer
- scope performance

## 7) Archive + RAG Flow

```text
Archive Crawl / Feed Inputs
-> article fetch
-> chunking
-> embeddings
-> pgvector index
-> retrieval for archive search and drafting context
```

## 8) Post-Publish Quality Monitor

```text
Published feed
-> scoring
-> weak-item detection
-> UI panel + alerts
```

## 9) UX Telemetry Flow

```text
Frontend surface_view / next_action_click events
-> telemetry API
-> action_audit_logs
-> /ux-insights summaries and funnel views
```

## 10) Technical Stack

### Presentation
- Next.js 16
- React
- TypeScript
- Tailwind CSS

### API
- FastAPI
- Pydantic
- SQLAlchemy

### Data
- PostgreSQL
- pgvector
- Redis

### Async / Jobs
- Celery workers
- Redis broker/result

### Storage / Feeds
- MinIO
- FreshRSS
- RSS-Bridge

## 11) Main Backend Domains
- `backend/app/agents/` editorial and AI pipeline agents
- `backend/app/api/routes/` REST entrypoints
- `backend/app/services/` domain services
- `backend/app/models/` ORM models
- `backend/app/domain/news/` workflow/state logic
- `backend/app/queue/` async execution

## 12) Main Frontend Domains
- `frontend/src/app/` route surfaces
- `frontend/src/components/layout/` shell and navigation
- `frontend/src/components/workflow/` queue/help/onboarding UI
- `frontend/src/components/editorial-os/` explanatory docs UI
- `frontend/src/lib/api.ts` API contracts
- `frontend/src/lib/workflow-language.ts` shared workflow labels

## 13) Ports
- Backend: `8000`
- Frontend: `3000`
- PostgreSQL: `5433`
- Redis: `6380`
- MinIO: `9000/9001`

## 14) Operational Constraints
- No automatic final publish to CMS
- Chief approval remains authoritative
- Status transitions must respect the state machine
- UX changes must preserve RTL and Arabic correctness
- New tools should prefer contextual exposure over top-level clutter

## 15) Documentation References
- `docs/PRODUCT_ROADMAP_AR.md`
- `docs/PLATFORM_MASTER_DETAILS_AR.md`
- `docs/PROJECT_PROFILE_AR.md`
- `docs/USER_GUIDE_AR.md`
- `AGENT_ONBOARDING.md`
- `README.md`
