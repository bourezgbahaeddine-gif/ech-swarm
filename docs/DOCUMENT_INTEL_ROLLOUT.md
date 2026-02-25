# Document Intelligence (PDF) - Rollout Notes

## What was added
- Backend endpoint: `POST /api/v1/document-intel/extract`
- Frontend page: `/services/document-intel`
- Sidebar entry: `محلل الوثائق`
- Parsing strategy:
  - Primary: `Docling` (if installed in backend image)
  - Fallback: `pypdf` (always available via `backend/requirements.txt`)

## API contract
- Multipart fields:
  - `file` (PDF, required)
  - `language_hint` (`ar|fr|en|auto`, optional, default `ar`)
  - `max_news_items` (1..20, optional)
  - `max_data_points` (1..120, optional)
- Response includes:
  - parser used, language detection, basic stats
  - extracted headings
  - `news_candidates`
  - `data_points`
  - warnings (e.g. Docling unavailable)

## Optional Docling activation
- Base system works without Docling (uses pypdf fallback).
- To enable Docling in backend runtime:
  - Set env: `INSTALL_DOCLING=true`
  - rebuild backend/worker images
  - Docker build now supports `INSTALL_DOCLING` arg from `docker-compose.yml`
- Runtime controls:
  - `ECHOROUK_OS_DOCUMENT_INTEL_DOCLING_TIMEOUT_SECONDS` (default `45`)
  - `ECHOROUK_OS_DOCUMENT_INTEL_DOCLING_MAX_SIZE_MB` (default `8`)
  - `ECHOROUK_OS_DOCUMENT_INTEL_MAX_UPLOAD_MB` (default `80`)
  - For large files, system skips Docling and uses `pypdf` directly.
  - OCR controls:
    - `ECHOROUK_OS_DOCUMENT_INTEL_OCR_ENABLED` (default `true`)
    - `ECHOROUK_OS_DOCUMENT_INTEL_OCR_FORCE` (default `false`)
    - `ECHOROUK_OS_DOCUMENT_INTEL_OCR_TIMEOUT_SECONDS` (default `180`)
    - `ECHOROUK_OS_DOCUMENT_INTEL_OCR_PER_PAGE_TIMEOUT_SECONDS` (default `15`)
    - `ECHOROUK_OS_DOCUMENT_INTEL_OCR_MAX_PAGES` (default `24`)
    - `ECHOROUK_OS_DOCUMENT_INTEL_OCR_DPI` (default `220`)
    - `ECHOROUK_OS_DOCUMENT_INTEL_OCR_TRIGGER_MIN_CHARS` (default `1200`)

## OCR stage
- If extracted text is weak/short, backend runs OCR automatically using:
  - `pdftoppm` (Poppler) to render pages
  - `tesseract` (`ara`, `eng`, `fra`) for recognition
- OCR is bounded by timeout and max pages to protect API responsiveness.

## Multilingual extraction update
- News candidate scoring now supports:
  - Arabic keywords
  - English keywords (press release / announced / confirmed / official / etc.)
  - French keywords (communiqué / a annoncé / gouvernement / etc.)
- Language detection now returns `ar|en|fr|mixed|unknown`.

## Next integration step (recommended)
- Done: action button in Document Intelligence page:
  - `إنشاء Draft في المحرر الذكي`
  - Uses endpoint: `POST /api/v1/editorial/workspace/manual-drafts`
