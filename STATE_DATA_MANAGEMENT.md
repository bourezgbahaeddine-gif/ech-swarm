# STATE AND DATA MANAGEMENT

## 1) End-to-End Data Flow
1. Scout ingests feed entries and writes `articles` as `status=new`.
2. Router classifies/scoring and transitions to `classified` or `candidate`.
3. Scribe generates draft content for approved editorial flow.
4. Dashboard reads paginated/queryable article state via `/api/v1/news/*`.
5. Editors review and move items to downstream publish-ready states.

## 2) Authoritative Data Sources
- Primary persistence: PostgreSQL.
- Cache/idempotency and queue transport: Redis.
- Worker execution: Celery jobs from API/scheduler triggers.

## 3) Article Lifecycle Rules
- Freshness gate:
  - Old entries should be archived, not kept in `new/classified/candidate`.
- Breaking gate:
  - `is_breaking=true` must remain within TTL window.
- Dedup gate:
  - Exact hash and URL dedup.
  - Fuzzy title and cross-source duplicate suppression.

## 4) Backend State Management
- Status fields are enum-backed (`NewsStatus`, `UrgencyLevel`, `NewsCategory`).
- Transition logic belongs to agents/services, not to UI.
- Batch jobs must be idempotent and safe under retries.
- Use `coalesce(published_at, crawled_at)` when freshness is evaluated.

## 5) Frontend State Management
- Server state: React Query (`frontend/src/lib/providers.tsx`).
  - `staleTime`: 30s
  - `refetchInterval`: 60s
  - `retry`: 2
- API layer: Axios singleton (`frontend/src/lib/api.ts`).
- UI local state: component-level `useState` for filters/forms/temporary state.

## 6) API Contract and Errors
- Prefer typed request/response models in frontend (interfaces in `frontend/src/lib/api.ts`).
- For endpoints using envelope responses, validate envelope shape before usage.
- For task-trigger endpoints, surface returned `job_id` and `job_type` in UI/ops.

## 7) Operational Data Safety
- Never mutate large sets without explicit scope filters.
- For cleanup jobs:
  - Archive stale items in target statuses only.
  - Demote stale breaking flags.
  - Keep audit reason in `rejection_reason`.

## 8) Recommended Query Patterns
- Newsroom active lists:
  - Exclude archived by default.
  - Filter stale records at query layer.
- Breaking lists:
  - Enforce freshness cutoff in query.

## 9) Performance and Scale Notes
- Prefer bounded batch limits and source quotas.
- Avoid N+1 source lookups during router batch processing.
- Commit in chunks for long-running batches to release locks progressively.
