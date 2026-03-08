# Session Handoff - 2026-03-08 - Echorouk Archive Background Build

## Scope
This handoff captures the current state of the `Echorouk Online` archive backfill and background scheduling work so the next session can resume without redoing diagnosis.

## Code State
- Server updated to commit `9835f99`.
- Key archive scheduler fix was deployed:
  - Alembic merge revision shortened to fit `alembic_version.version_num`.
  - Background archive loop enabled through `backend/app/main.py`.
  - Archive refresh logic present in `backend/app/services/echorouk_archive_service.py`.

## Migration State
- `alembic upgrade head` now succeeds.
- Current Alembic head on server:
  - `20260308_merge_archive_heads`
- Archive tables now exist:
  - `archive_crawl_states`
  - `archive_crawl_urls`

Verification commands that succeeded:

```bash
docker compose exec backend alembic current
docker compose exec postgres psql -U echorouk -d echorouk_db -c "\dt archive_*"
```

## Runtime Config Applied on Server
Added to `.env`:

```bash
ECHOROUK_OS_ECHOROUK_ARCHIVE_ENABLED=true
ECHOROUK_OS_ECHOROUK_ARCHIVE_BACKFILL_INTERVAL_MINUTES=10
ECHOROUK_OS_ECHOROUK_ARCHIVE_MAX_LISTING_PAGES_PER_RUN=3
ECHOROUK_OS_ECHOROUK_ARCHIVE_MAX_ARTICLES_PER_RUN=12
ECHOROUK_OS_ECHOROUK_ARCHIVE_REFRESH_INTERVAL_MINUTES=1440
ECHOROUK_OS_ECHOROUK_ARCHIVE_REFRESH_LISTING_PAGES=2
ECHOROUK_OS_ECHOROUK_ARCHIVE_REFRESH_ARTICLE_PAGES=10
ECHOROUK_OS_ECHOROUK_ARCHIVE_RAG_ENABLED=false
```

Reason for `RAG=false`:
- keep archive ingestion isolated from editorial generation until the archive corpus has real indexed content.

## Observed Background Behavior
The scheduler started automatically after deploy.

Relevant logs:

- `periodic_loop_started` for loop `echorouk_archive`
- `echorouk_archive_enabled`
- `auto_echorouk_archive_tick_done`
- job enqueued on queue `ai_scripts`

Auto-created job:

- `job_id = c0ba5e0b-70d6-41a2-8067-69e8574880cb`
- `job_type = echorouk_archive_backfill`
- status seen in DB: `running`

Manual `POST /api/v1/archive/echorouk/run` returned `409`, which is expected while this active job exists.

## Current Server Status
Status endpoint at stop time:

```json
{
  "source_key": "echorouk_archive",
  "status": "running",
  "seeded_at": "2026-03-08T15:08:31.168790",
  "last_run_started_at": "2026-03-08T15:08:31.651210",
  "last_run_finished_at": null,
  "last_error": null,
  "stats": {
    "seeded_listing_urls": 6,
    "listing_pages_processed": 0,
    "article_pages_processed": 0,
    "article_pages_indexed": 0,
    "article_pages_failed": 0,
    "article_pages_skipped": 0,
    "urls_discovered": 0
  },
  "queue": {
    "listing": {
      "discovered": 3,
      "processing": 3
    }
  },
  "recent_failures": []
}
```

Queue rows at stop time:

```sql
select url_type, status, count(*)
from archive_crawl_urls
group by 1,2
order by 1,2;
```

Result:

- `listing / discovered = 3`
- `listing / processing = 3`

## Important Observation
The archive job appears stuck after claiming the first 3 listing URLs:

- no listing page was marked `fetched`
- no article URLs were discovered
- no article pages were indexed
- no archive-specific failure was written into `last_error`
- worker log shows `task_execution_started`, but not completion/failure for that job

At the same time, direct connectivity from the backend container to the source site is confirmed:

```bash
https://www.echoroukonline.com/ 200 357457
https://www.echoroukonline.com/economy 200 217863
https://www.echoroukonline.com/algeria 200 218501
```

This means:
- DNS/connectivity to the site is fine from the container.
- The current blocker is inside the running archive task path, not basic network reachability.

## Search State
Archive semantic search currently returns no items:

```json
{
  "items": [],
  "query": "سوناطراك",
  "limit": 5
}
```

This is expected at this point because:
- `article_pages_indexed = 0`
- no archive articles have been persisted/indexed yet.

## Previous Failure Already Resolved
Earlier failed job:

- `de4c0ffa-e023-4be0-aeab-27e9895bcce9`
- failure reason:
  - `relation "archive_crawl_states" does not exist`

This failure was caused by missing archive tables before the Alembic fix and can now be ignored as historical.

## Most Likely Investigation Starting Point for Next Session
The next session should focus on why the active archive task remains in `running` after claiming listing URLs.

Priority checks:

1. Inspect the active worker process and current stack/log behavior while the job is running.
2. Add archive-stage logs around:
   - listing fetch start
   - listing fetch end
   - listing parse counts
   - article claim phase
3. Verify whether the task is blocked in:
   - `_fetch_html(...)`
   - `response.text()`
   - HTML parsing/trafilatura path
   - DB commit after claim/fetch
4. If the active job is stale, mark it failed and reset `processing` listing URLs back to `discovered` before retrying.

## Recommended Resume Commands
Check current archive status:

```bash
curl -fsS "http://127.0.0.1:8000/api/v1/archive/echorouk/status" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

Check archive frontier:

```bash
docker compose exec postgres psql -U echorouk -d echorouk_db -c "
select url_type, status, count(*)
from archive_crawl_urls
group by 1,2
order by 1,2;
"
```

Check archive jobs:

```bash
docker compose exec postgres psql -U echorouk -d echorouk_db -c "
select id, job_type, status, started_at, finished_at, left(coalesce(error,''), 160) as error
from job_runs
where job_type = 'echorouk_archive_backfill'
order by created_at desc
limit 5;
"
```

Check logs:

```bash
docker compose logs --tail=300 backend worker | rg "auto_echorouk_archive|echorouk_archive|article_index_upserted|task_execution_started|job_completed|job_failed"
```

Connectivity sanity check:

```bash
docker compose exec backend sh -lc "python - <<'PY'
import requests
for url in [
    'https://www.echoroukonline.com/',
    'https://www.echoroukonline.com/economy',
    'https://www.echoroukonline.com/algeria',
]:
    try:
        r = requests.get(url, timeout=20, headers={'User-Agent':'Mozilla/5.0'})
        print(url, r.status_code, len(r.text))
    except Exception as e:
        print(url, 'ERROR', e)
PY"
```

## Next Session Goal
Get the first archive run to complete end-to-end:

1. listing pages move from `processing` to `fetched`
2. article URLs are discovered
3. first archive articles are inserted
4. vector indexing begins
5. archive search returns real results
