# Echorouk Editorial OS — Architecture Documentation

Echorouk Editorial OS is an enterprise operating system for managing editorial content lifecycle from capture to manual-publish readiness, with strict governance and mandatory Human-in-the-Loop.


## System Architecture

### Data Flow Pipeline

```
                    ┌──────────────────────────────────────────────────────────────────┐
                    │                  ECHOROUK EDITORIAL OS                           │
                    │                                                                  │
  RSS Feeds ────►   │  ┌─────────┐    ┌──────────┐    ┌─────────┐    ┌─────────────┐  │
  (300+ sources)    │  │  Scout  │───►│  Router  │───►│ Scribe  │───►│  Editorial  │  │
                    │  │ Agent   │    │  Agent   │    │ Agent   │    │  Dashboard  │  │
                    │  └────┬────┘    └────┬─────┘    └────┬────┘    └──────┬──────┘  │
                    │       │              │               │                │          │
                    │       ▼              ▼               ▼                ▼          │
                    │  ┌──────────────────────────────────────────────────────────┐    │
                    │  │                    PostgreSQL + pgvector                 │    │
                    │  │                    Redis (Cache + Queue)                 │    │
                    │  │                    MinIO (Object Storage)                │    │
                    │  └──────────────────────────────────────────────────────────┘    │
                    │                                                                  │
                    │  ┌────────────┐    ┌───────────────┐                             │
                    │  │   Trend    │    │    Audio      │                             │
                    │  │   Radar    │    │    Agent      │                             │
                    │  └────────────┘    └───────────────┘                             │
                    └──────────────────────────────────────────────────────────────────┘
```

### Article Status Pipeline

```
NEW → CLEANED → DEDUPED → CLASSIFIED → CANDIDATE → APPROVED → PUBLISHED → ARCHIVED
                                            │                      │
                                            ├──► REJECTED          │
                                            │                      │
                                            └──► REWRITE ────►────┘
```

### Deduplication Strategy (Three-Layer)

1. **Layer 1: SHA1 Hash** — Exact URL + title match check against Redis (24h TTL)
2. **Layer 2: Database Check** — Fallback to PostgreSQL unique_hash index
3. **Layer 3: Levenshtein Fuzzy** — Token-sort ratio against recent 200 titles (threshold: 70%)

### Cost Optimization: Tiered AI Processing

```
Input Text
    │
    ▼
┌─────────────────┐
│  Python Rules   │──── If confident (2+ keyword matches) → FREE classification
│  (Keywords)     │
└────────┬────────┘
         │ uncertain
         ▼
┌─────────────────┐
│  Gemini Flash   │──── Fast, cheap classification + analysis
│  ($0.002/call)  │
└────────┬────────┘
         │ complex/investigative
         ▼
┌─────────────────┐
│  Gemini Pro     │──── Deep analysis, large docs (only when needed)
│  ($0.01/call)   │
└─────────────────┘
```

### Database Schema (ER Diagram)

```
┌──────────────┐     ┌──────────────┐     ┌───────────────────┐
│   sources    │     │   articles   │     │ editor_decisions  │
├──────────────┤     ├──────────────┤     ├───────────────────┤
│ id           │     │ id           │     │ id                │
│ name         │◄────│ source_id    │────►│ article_id        │
│ url          │     │ unique_hash  │     │ editor_name       │
│ category     │     │ status       │     │ decision          │
│ trust_score  │     │ category     │     │ reason            │
│ priority     │     │ importance   │     │ edited_title      │
│ enabled      │     │ urgency      │     │ edited_body       │
│ error_count  │     │ title_ar     │     │ decided_at        │
└──────────────┘     │ summary      │     └───────────────────┘
                     │ body_html    │
                     │ entities     │     ┌───────────────────┐
                     │ keywords     │     │  feedback_logs    │
                     │ truth_score  │     ├───────────────────┤
                     │ ai_model     │     │ id                │
                     │ trace_id     │     │ article_id        │
                     └──────────────┘     │ field_name        │
                                          │ original_value    │
                     ┌──────────────┐     │ corrected_value   │
                     │ failed_jobs  │     │ correction_type   │
                     ├──────────────┤     └───────────────────┘
                     │ id           │
                     │ job_type     │     ┌───────────────────┐
                     │ payload      │     │  pipeline_runs    │
                     │ error_msg    │     ├───────────────────┤
                     │ retry_count  │     │ id                │
                     │ resolved     │     │ run_type          │
                     └──────────────┘     │ total_items       │
                                          │ new_items         │
                                          │ duplicates        │
                                          │ errors            │
                                          │ status            │
                                          └───────────────────┘
```

## Security Model

### Input Validation Pipeline

```
Raw Input → Strip HTML → Remove Scripts → Decode Entities → Remove XSS Patterns → Clean Whitespace → Output
```

### Secret Management

- All secrets in `.env` (never committed)
- `.env.example` for documentation only
- Docker secrets for production deployment
- API keys validated on startup

## 2026-02-25 Hardening Update

### Layering and bounded contexts

The backend now follows explicit boundaries:

- `app/api/*`: HTTP transport only (request parsing, auth dependencies, response mapping).
- `app/services/*`: application orchestration and cross-module workflows.
- `app/domain/*`: pure domain logic (state machine and quality gate primitives).
- `app/repositories/*`: reusable persistence access patterns.
- `app/models/*`: SQLAlchemy persistence models.

New modules introduced:

- `app/domain/news/state_machine.py`
- `app/domain/quality/gates.py`
- `app/repositories/story_repository.py`
- `app/repositories/task_idempotency_repository.py`
- `app/services/task_execution_service.py`

### Correlation and request tracking propagation

Request middleware sets and logs:

- `request_id`
- `correlation_id`

These values are persisted in `job_runs` and rebound inside Celery workers through `_load_job()` / `_mark_running()` context binding so worker logs remain traceable back to the triggering API request.

### Task idempotency approach

Task-level idempotency is implemented via `task_idempotency_keys` and `task_execution_service`.

- Key format: `task_name:entity_id:payload_hash` (or explicit `idempotency_key` from payload).
- `acquire` states:
  - `acquired`: task can execute
  - `running`: another active owner exists -> skip duplicate side effects
  - `completed`: return cached result
- Completion/failure updates are stored for replay-safe retries.

This is applied to pipeline and editorial queue workers to avoid duplicate transitions/draft side effects under retry/requeue conditions.

### Story activation flow (MVP)

Stories are now operationally activated from the newsroom workflow:

- `POST /api/v1/stories/from-article/{article_id}`
  - one-click story creation from an article
  - creates `stories` + `story_items` in one transaction
  - optional `reuse=true` returns existing linked story when already linked

- `GET /api/v1/stories/suggest?article_id=...`
  - read-only linking suggestions (no side effects)
  - score combines:
    - title similarity (sequence + token overlap)
    - entity overlap (article entities vs story text)
    - relation boost (if related articles are linked to story)
    - category match boost

- `GET /api/v1/stories/{story_id}/dossier`
  - unified dossier output for editorial consumption:
    - linked timeline (`article` + `draft`)
    - stats (items/articles/drafts/last activity)
    - highlights (latest titles, top sources, notes count)

Data integrity is enforced at DB level for `story_items`:

- exactly one of `article_id` or `draft_id` must be set
- `link_type` must match the non-null reference (`article` or `draft`)
