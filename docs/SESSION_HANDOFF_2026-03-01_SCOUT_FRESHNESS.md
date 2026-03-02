# Session Handoff - Scout Freshness Hardening (2026-03-01)

## Problem
- `scout` was ingesting stale content (older than 1 month / years), which is unsafe for newsroom workflow.
- This happened when runtime settings were relaxed (very high age limit, disabled ingest filters, missing timestamps).

## Fix Implemented
- File changed: `backend/app/agents/scout.py`

### 1) Global safety cap for article age
- Added hard cap: `SCOUT_HARD_MAX_ARTICLE_AGE_HOURS = 24 * 31` (31 days).
- Effective max age now uses:
  - configured `scout_max_article_age_hours`
  - clamped by hard cap
- Added warning log when clamping happens:
  - `scout_max_age_clamped_for_safety`

### 2) Freshness gate is now always enforced
- Stale/future timestamp checks are no longer behind `scout_ingest_filters_enabled`.
- New stale skip log:
  - `entry_skipped_stale`

### 3) URL date fallback
- When feed entry does not include a timestamp, scout now tries extracting date from URL patterns:
  - `YYYY/MM/DD`
  - `YYYY-MM-DD`
  - `YYYYMMDD`

### 4) Scraper safety guard
- For `source.method == scraper`, entries without timestamp are skipped.
- New log:
  - `entry_skipped_missing_timestamp_scraper`

## Why This Is Safe
- Prevents accidental backlog floods even if ops sets loose values.
- Preserves configurability (age can be lower than 31 days, never higher).
- Keeps aggregator + scraper feeds from replaying old archive links into newsroom queues.

## Deploy Commands (Server)
```bash
cd ~/ech-swarm
git pull origin $(git branch --show-current)

set_kv ECHOROUK_OS_SCOUT_MAX_ARTICLE_AGE_HOURS 72
set_kv ECHOROUK_OS_SCOUT_INGEST_FILTERS_ENABLED true
set_kv ECHOROUK_OS_SCOUT_REQUIRE_TIMESTAMP_FOR_AGGREGATOR true

docker compose build backend worker
docker compose up -d --force-recreate backend worker
```

## Validation Commands
```bash
docker logs ech-worker --since 20m | grep -E "entry_skipped_stale|entry_skipped_missing_timestamp_scraper|entry_skipped_missing_timestamp_aggregator|scout_run_complete" | tail -n 120
```

## Expected Validation Signal
- You should see one or more of:
  - `entry_skipped_stale`
  - `entry_skipped_missing_timestamp_scraper`
  - `entry_skipped_missing_timestamp_aggregator`
- `scout_run_complete` should continue normally with no worker crash.

## Git Commands (PowerShell-safe)
```powershell
git add backend/app/agents/scout.py docs/SESSION_HANDOFF_2026-03-01_SCOUT_FRESHNESS.md
git commit -m "fix(scout): harden freshness gate against stale backlog ingestion"
git push origin "$(git branch --show-current)"
```

