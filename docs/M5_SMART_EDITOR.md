# M5 — Echorouk Smart News Editor Replacement

## Scope
This milestone replaces the old draft page with a newsroom-grade smart editor:
- Rich text editing (TipTap)
- AI suggestion workflow (diff-first, no silent overwrite)
- Evidence/claim verification panel
- Quality scoring panel
- SEO/social generation panels
- Version history + restore + diff
- Publish readiness gate (blocks unresolved claims)

## Why TipTap (vs Lexical)
TipTap was selected because:
- ProseMirror-based, stable extension system.
- Fast integration for newsroom formatting (H1/H2/H3, lists, links, quotes).
- Built-in `BubbleMenu` for contextual inline tools.
- Clean HTML output path that is easy to sanitize server-side.
- Better fit for side-panel editorial workflows than a raw editor core setup.

## Architecture
### Frontend
- Route: `frontend/src/app/workspace-drafts/page.tsx` (fully replaced)
- Layout:
  - Left panel: draft queue + source preview + metadata/rationale
  - Center: TipTap editor + suggestion diff block
  - Right panel tabs:
    - Evidence / Fact-check
    - Quality Score
    - SEO Tools
    - Social Versions
    - Story Context (versions, restore, diff)
  - Top bar:
    - Save state
    - Verify / Improve / Headlines / SEO / Social / Quality / Publish Gate / Apply

### Backend
- New service: `backend/app/services/smart_editor_service.py`
  - HTML sanitization (bleach)
  - Diff generation
  - AI rewrite/headline/SEO/social suggestion generation
  - Claim extraction + fact-check report
  - Quality scoring engine (0..100)
- Extended editorial routes in `backend/app/api/routes/editorial.py`:
  - `GET /editorial/workspace/drafts/{work_id}/context`
  - `GET /editorial/workspace/drafts/{work_id}/versions`
  - `GET /editorial/workspace/drafts/{work_id}/diff`
  - `POST /editorial/workspace/drafts/{work_id}/autosave`
  - `POST /editorial/workspace/drafts/{work_id}/restore/{version}`
  - `POST /editorial/workspace/drafts/{work_id}/ai/rewrite`
  - `POST /editorial/workspace/drafts/{work_id}/ai/headlines`
  - `POST /editorial/workspace/drafts/{work_id}/ai/seo`
  - `POST /editorial/workspace/drafts/{work_id}/ai/social`
  - `POST /editorial/workspace/drafts/{work_id}/ai/apply`
  - `POST /editorial/workspace/drafts/{work_id}/verify/claims`
  - `POST /editorial/workspace/drafts/{work_id}/quality/score`
  - `GET /editorial/workspace/drafts/{work_id}/publish-readiness`
- Publish rule tightened:
  - `publish_now` now blocks if latest `FACT_CHECK` stage is missing or failing.

### Database
- Model updated: `backend/app/models/news.py` (`EditorialDraft`)
  - `parent_draft_id`
  - `change_origin`
  - unique `(work_id, version)`
- Migration: `alembic/versions/20260217_m5_smart_editor.py`

## File Tree (M5 touchpoints)
- `frontend/src/app/workspace-drafts/page.tsx`
- `frontend/src/lib/api.ts`
- `frontend/src/components/layout/Sidebar.tsx`
- `frontend/src/app/globals.css`
- `frontend/package.json`
- `backend/app/api/routes/editorial.py`
- `backend/app/services/smart_editor_service.py`
- `backend/app/services/__init__.py`
- `backend/app/models/news.py`
- `backend/app/agents/scribe.py`
- `backend/requirements.txt`
- `alembic/versions/20260217_m5_smart_editor.py`
- `backend/tests/test_smart_editor_service.py`

## Security
- Server-side sanitization for draft HTML via `bleach`.
- Unsafe tags and `javascript:` links are stripped.
- Editor apply path keeps suggestion acceptance explicit.

## Local Run (Docker)
1. Build/update containers:
   - `docker compose up -d --build backend frontend`
2. Apply migrations:
   - `docker compose run --rm backend alembic upgrade head`
3. Restart backend:
   - `docker compose restart backend`
4. Open UI:
   - `http://localhost:3000/workspace-drafts`

## Tests
- Backend unit tests:
  - `pytest backend/tests/test_smart_editor_service.py -q`
