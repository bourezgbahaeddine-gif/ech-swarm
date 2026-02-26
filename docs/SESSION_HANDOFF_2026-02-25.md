# Session Handoff - 2026-02-25

## Update (Script Studio hardening)

### Scope completed
- Script Studio refactor/hardening completed without breaking route paths or envelope contract.
- Added reuse flow for script creation from article/story.
- Added explicit failed status for script generation lifecycle.
- Added race-safe output version handling under concurrent workers.
- Fixed `/scripts` frontend build issue caused by `useSearchParams` without `Suspense`.

### Commits shipped
- `500e8e2` Fix scripts reuse param default for direct-call tests (FastAPI Query + Annotated)
- `0c153f8` Harden Script Studio: reuse mode, failed status, and version-race safety
- `f4a34ed` Fix /scripts build: wrap useSearchParams with Suspense boundary
- `de77871` Fix Script Studio wiring: API export, model imports, routes, queue, UI
- `1773ec2` Add Script Studio MVP: models, API, queue, UI, tests, docs

### Backend changes
- `POST /api/v1/scripts/from-article/{article_id}`:
  - new query param `reuse` (default `false`)
  - when `reuse=true`, returns latest matching project and skips create/enqueue
- `POST /api/v1/scripts/from-story/{story_id}`:
  - same `reuse` behavior
- Repository helper added:
  - `ScriptRepository.get_latest_project_by_source(...)`
- Script status enum extended:
  - `failed`
- Generation failure behavior:
  - project status moves to `failed`
  - structured logging
  - audit event `script_generation_failed`
- Version race handling:
  - re-check `(script_id, version)` before insert
  - catch `IntegrityError` on unique conflict and return `reused=true` instead of failing

### Migration
- New migration:
  - `alembic/versions/20260226_script_status_failed.py`
- Behavior:
  - idempotent enum alter to add `failed` into `script_project_status`

### Frontend change
- `frontend/src/app/scripts/page.tsx`
  - wrapped page client using `useSearchParams()` inside `Suspense`
  - fixed Next.js build/prerender error on `/scripts`

### Validation on server
- Deployment succeeded (`git pull`, rebuild backend/worker, alembic upgrade, recreate services).
- Health check:
  - `GET /health` returned `ok`.
- Tests:
  - `pytest tests/test_scripts_studio.py` => **7 passed**
- API smoke (validated):
  - `from-article?reuse=false` creates new script + enqueues job
  - `from-article?reuse=true` returns same script with `meta.reused=true` and `job=null`

### Known non-blocking warnings
- `pytest_asyncio` loop-scope deprecation warning.
- Pydantic v2 deprecation warnings for class-based config (existing technical debt).

### Resume checklist for next session
1. Verify end-to-end review flow in UI:
   - generate -> ready_for_review -> approve/reject
2. Add one integration test for `reuse=true` against HTTP client layer (not route direct-call).
3. Decide whether to tighten bulletin statuses to:
   - `READY_FOR_MANUAL_PUBLISH`, `PUBLISHED`, `APPROVED`, `APPROVED_HANDOFF`
4. If needed, expose failure reason in script details panel for quicker newsroom triage.

## Scope completed
- Added async Document Intel flow to avoid blocking HTTP requests on large/scanned PDFs.
- Added Redis temporary payload storage for upload bytes (`job_id`-driven processing).
- Added worker task for document extraction jobs.
- Updated frontend Document Intel page to submit + poll job status.
- Added extraction strategy update to skip Docling in Arabic large/gazette-like documents.

## Backend changes
- New routes:
  - `POST /api/v1/document-intel/extract/submit`
  - `GET /api/v1/document-intel/extract/{job_id}`
- Existing sync route kept:
  - `POST /api/v1/document-intel/extract`
- New service:
  - `backend/app/services/document_intel_job_storage.py`
- Job queue integration:
  - job type: `document_intel_extract`
  - queue: `ai_quality`
  - task: `app.queue.tasks.pipeline_tasks.run_document_intel_extract_job`

## New env keys
- `ECHOROUK_OS_DOCUMENT_INTEL_DOCLING_SKIP_FOR_AR=true`
- `ECHOROUK_OS_DOCUMENT_INTEL_JOB_PAYLOAD_TTL_SECONDS=3600`

## Frontend changes
- `frontend/src/app/services/document-intel/page.tsx` now:
  - submits extraction as background job
  - polls status until completion/failure
  - shows current job status and `job_id`

## Validation done
- Python syntax check (`py_compile`) passed for modified backend modules.
- Frontend lint passed with one existing warning in `Sidebar.tsx` (`<img>` optimization warning).

## Deploy checklist (server)
1. `git pull`
2. `docker compose build backend worker frontend`
3. `docker compose up -d --force-recreate backend worker frontend`
4. Test async endpoints:
   - submit: `POST /api/v1/document-intel/extract/submit`
   - poll: `GET /api/v1/document-intel/extract/{job_id}`
