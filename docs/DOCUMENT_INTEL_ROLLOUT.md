# Document Intelligence (PDF) - Rollout Notes

## What was added
- Backend sync endpoint: `POST /api/v1/document-intel/extract`
- Backend async flow:
  - `POST /api/v1/document-intel/extract/submit` (returns `job_id`)
  - `GET /api/v1/document-intel/extract/{job_id}` (poll status/result)
- Frontend page: `/services/document-intel`
- Sidebar entry: `Document Intel`
- Parsing strategy:
  - Primary: `Docling` (if installed)
  - Fallback: `pypdf`
  - OCR fallback for scanned PDFs (`pdftoppm` + `tesseract`)

## Why async flow
- Prevents `504` on large/scanned PDFs.
- Keeps upload request short and moves heavy parsing to worker queue.
- Frontend now shows queue/running/completed/failed job states.

## API contract
- Submit fields (multipart):
  - `file` (PDF, required)
  - `language_hint` (`ar|fr|en|auto`, optional, default `ar`)
  - `max_news_items` (1..20, optional)
  - `max_data_points` (1..120, optional)
- Job status response includes:
  - `status` (`queued|running|completed|failed|dead_lettered`)
  - `error` (when failed)
  - `result` (same payload as sync `/extract` response)

## Runtime controls
- `ECHOROUK_OS_DOCUMENT_INTEL_DOCLING_TIMEOUT_SECONDS` (default `45`)
- `ECHOROUK_OS_DOCUMENT_INTEL_DOCLING_MAX_SIZE_MB` (default `8`)
- `ECHOROUK_OS_DOCUMENT_INTEL_DOCLING_SKIP_FOR_AR` (default `true`)
- `ECHOROUK_OS_DOCUMENT_INTEL_MAX_UPLOAD_MB` (default `80`)
- `ECHOROUK_OS_DOCUMENT_INTEL_JOB_PAYLOAD_TTL_SECONDS` (default `3600`)
- OCR controls:
  - `ECHOROUK_OS_DOCUMENT_INTEL_OCR_ENABLED` (default `true`)
  - `ECHOROUK_OS_DOCUMENT_INTEL_OCR_FORCE` (default `false`)
  - `ECHOROUK_OS_DOCUMENT_INTEL_OCR_TIMEOUT_SECONDS` (default `180`)
  - `ECHOROUK_OS_DOCUMENT_INTEL_OCR_PER_PAGE_TIMEOUT_SECONDS` (default `15`)
  - `ECHOROUK_OS_DOCUMENT_INTEL_OCR_MAX_PAGES` (default `24`)
  - `ECHOROUK_OS_DOCUMENT_INTEL_OCR_DPI` (default `220`)
  - `ECHOROUK_OS_DOCUMENT_INTEL_OCR_TRIGGER_MIN_CHARS` (default `1200`)

## Decision strategy
- Skip Docling for oversized PDFs.
- Skip Docling for Arabic large/gazette-like files when `DOCUMENT_INTEL_DOCLING_SKIP_FOR_AR=true`.
- Use OCR fallback when extracted text quality is low.

## Current UX integration
- User uploads PDF from Document Intel page.
- Frontend submits async job and polls until completion.
- Extracted news candidates can be pushed to Smart Editor via manual draft action.
