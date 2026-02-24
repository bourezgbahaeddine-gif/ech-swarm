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
  - install optional deps from `backend/requirements-docling.txt`

## Next integration step (recommended)
- Add action button in Document Intelligence page:
  - `Create draft from candidate`
  - Call existing endpoint: `POST /api/v1/editorial/workspace/manual-drafts`
