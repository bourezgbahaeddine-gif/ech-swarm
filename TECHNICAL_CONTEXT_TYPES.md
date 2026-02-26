# TECHNICAL CONTEXT - TYPES AND INTERFACES

## 1) Canonical Frontend Type Sources
Primary file:
- `frontend/src/lib/api.ts`

Contains shared interfaces used across pages/components, including:
- `ApiEnvelope<T>`, `ApiEnvelopeError`
- `Article`, `ArticleBrief`, `PaginatedResponse<T>`
- `Source`, `PipelineRun`, `DashboardStats`
- `OpsOverviewResponse`, `TrendAlert`
- published-monitor related response types

## 2) Canonical Backend Type Sources
- ORM enums and models:
  - `backend/app/models/news.py`
  - `backend/app/models/knowledge.py`
- Request/response schemas:
  - `backend/app/schemas/`

Key enums:
- `NewsStatus`
- `NewsCategory`
- `UrgencyLevel`

## 3) Interface Usage Rules
- Do not duplicate API response shapes in random component files.
- Import and reuse shared interfaces from `frontend/src/lib/api.ts`.
- If a new endpoint is added:
  1. Define/extend response interface in `frontend/src/lib/api.ts`.
  2. Add service function in same file or adjacent API module.
  3. Consume via typed hook/component.

## 4) Type Evolution Policy
- Backward-compatible change:
  - add optional field first.
- Breaking change:
  - update backend schema and frontend interface in the same release.
  - verify pages using that contract.

## 5) Quick Reference (Important Models)
- Article pipeline:
  - `backend/app/models/news.py` (`Article`)
- Story and relation structures:
  - `backend/app/models/knowledge.py` (`StoryCluster`, `StoryClusterMember`, `ArticleRelation`)
