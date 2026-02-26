# DEVELOPMENT GUIDELINES

## 1) Naming Conventions
- Python files/modules: `snake_case.py`
- Python classes/enums: `PascalCase`
- Python functions/variables: `snake_case`
- React components: `PascalCase.tsx`
- React hooks/helpers: `camelCase`
- Route folders in Next app router: lower-case, URL-friendly (for example `news`, `stories`, `services`)
- Constants: `UPPER_SNAKE_CASE`

## 2) Backend Code Style
- Prefer explicit typing for public functions and service boundaries.
- Keep async flow non-blocking in API and worker paths.
- Use services for business logic, routes for request/response wiring only.
- Validate input at API boundary (Pydantic schemas).
- Use enum values from model definitions, do not hardcode status/category strings in multiple places.
- Keep logs structured and event-driven (`event_name`, key fields).

## 3) Frontend Code Style
- Keep page files focused on composition and data orchestration.
- Move reusable logic to `src/lib` or dedicated hooks/helpers.
- Keep components presentational where possible.
- Use interfaces from shared API typing (`frontend/src/lib/api.ts`) instead of redefining shapes.
- Handle API errors through a consistent user-safe fallback message.

## 4) Formatting and Quality
- Backend:
  - Keep functions small and cohesive.
  - Add tests for behavior changes in routing/ingestion/state transitions.
- Frontend:
  - Keep props typed.
  - Avoid implicit `any`.
  - Keep class names readable; extract repeated UI patterns.
- Lint/test before shipping:
  - `frontend`: `npm run lint`
  - `backend`: `pytest`

## 5) Component Structure Pattern
- UI component file:
  - props/type definition
  - derived state/selectors
  - event handlers
  - rendering
- Avoid mixing API calls deep inside low-level UI components.

## 6) API Integration Rules
- Use centralized Axios client (`frontend/src/lib/api.ts`).
- Keep auth token injection in one place.
- Use React Query for caching/refetch rules and background refresh.
- Prefer idempotent backend task triggers with explicit job metadata.

## 7) Git and Change Scope
- One concern per commit where possible.
- Do not combine infra/config, data model, and UI redesign in one change unless required.
- Update docs when behavior changes (especially pipeline rules and status semantics).
