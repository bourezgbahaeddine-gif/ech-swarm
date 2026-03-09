# Echorouk Editorial OS — Architecture

Last updated: 2026-03-09

## 1) Overview
Enterprise newsroom operating system that manages editorial lifecycle from capture to manual‑publish readiness with strict governance and full traceability.

## 2) System Layers
- Presentation: Next.js + React.
- API: FastAPI + SQLAlchemy + Pydantic.
- Data: PostgreSQL + pgvector + Redis.
- Async: Celery Workers + Redis Broker/Result.
- Storage: MinIO.
- Feeds: FreshRSS + RSS‑Bridge.

## 3) Core Editorial Flow
```
RSS/FreshRSS -> Scout -> Router -> Scribe -> Smart Editor -> Chief Approval -> ready_for_manual_publish
```

## 4) Smart Editor Flow
```
Draft -> Proofread -> Quality -> Claims -> SEO/Links/Social -> Publish Readiness Gate -> Chief Approval
```

## 5) Archive Flow
```
Listing URLs -> Archive Crawler -> Article Fetch -> Article Index -> pgvector -> /archive + RAG
```

## 6) Post‑Publish Quality Monitor
```
RSS Feed -> Scoring -> Issues/Suggestions -> Telegram Alerts + UI Panel
```

## 7) RAG in Scribe
```
Article Content -> Embedding -> Archive Search -> Supporting Context -> Draft Generation
```

## 8) Deduplication (Scout)
- SHA1 hash + Redis cache.
- URL dedup via `original_url`.
- Fuzzy title dedup (Levenshtein).
- Cross‑source dedup by time window and similarity.

## 9) Time Integrity
- Rejects stale or future timestamps beyond policy.
- Per‑source timestamp policies and fallbacks.

## 10) Semantic Storage
- `article_profiles`, `article_chunks`, `article_vectors`.
- Archive corpus tagged as `corpus=echorouk_archive`.

## 11) Queues
- `ai_router`, `ai_scribe`, `ai_quality`, `ai_simulator`, `ai_msi`, `ai_links`, `ai_trends`, `ai_scripts`.
- Idempotency keys + retry/backoff + DLQ.

## 12) Observability
- Structured logging with `request_id` + `correlation_id`.
- Health endpoint: `/health`.

## 13) Ports
- Backend: `8000`
- Frontend: `3000`
- Postgres: `5433`
- Redis: `6380`
- MinIO: `9000/9001`

---
See also: `docs/PLATFORM_MASTER_DETAILS_AR.md`.
