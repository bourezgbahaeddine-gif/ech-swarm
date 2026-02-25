# Session Handoff - 2026-02-25

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
