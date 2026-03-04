# Time Integrity

This module enforces strict freshness without weakening editorial controls.

## Non-Negotiables

- Human-in-the-loop remains mandatory.
- No automatic publishing is introduced.
- Freshness guard only archives stale non-published items.

## Endpoints

### `GET /api/v1/dashboard/time-integrity`

Returns freshness telemetry:

- `oldest_candidate_age_hours`
- `oldest_ready_for_chief_age_hours`
- `stale_non_published_total`
- `stale_non_published_by_status`
- `skip_reasons`
- `top_stale_sources`
- `top_missing_timestamp_sources`
- `source_health_watchlist`
- `url_date_fallback`

### `POST /api/v1/dashboard/time-integrity/cleanup`

Archives stale non-published items using `SCOUT_MAX_ARTICLE_AGE_HOURS`.

Query params:

- `dry_run` (default: `true`)
- `max_age_hours` (optional override)

Response includes:

- `matched_rows`, `archived_rows`
- `matched_by_status`
- `reason` (prefix: `auto_archived:strict_time_guard`)
- `audit_action` (`auto_archived_stale`)

### `POST /api/v1/dashboard/time-integrity/cleanup/restore` (Director only)

Rollback endpoint for recent auto-archived rows.

Query params:

- `dry_run` (default: `true`)
- `lookback_hours` (default: `24`, max: `168`)
- `max_rows` (default: `200`)

Behavior:

- Reads `action_audit_logs` where `action=auto_archived_stale`.
- Restores only rows still in `archived` and archived by strict time guard.
- Restores each row to its original status captured at archive time.

Audit trail on restore:

- `action=auto_archived_stale_restored`
- `reason=manual_restore_auto_archived_stale`

## Scheduled Auto-Cleanup

Config keys:

- `ECHOROUK_OS_TIME_INTEGRITY_CLEANUP_ENABLED`
- `ECHOROUK_OS_TIME_INTEGRITY_CLEANUP_INTERVAL_MINUTES`
- `ECHOROUK_OS_SCOUT_MAX_ARTICLE_AGE_HOURS`

When enabled, backend logs:

- `auto_time_integrity_cleanup_tick_done`

## Operational Commands

```bash
# 1) Observe
curl -fsS "http://127.0.0.1:8000/api/v1/dashboard/time-integrity" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

# 2) Cleanup dry run
curl -fsS -X POST "http://127.0.0.1:8000/api/v1/dashboard/time-integrity/cleanup?dry_run=true" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

# 3) Apply cleanup
curl -fsS -X POST "http://127.0.0.1:8000/api/v1/dashboard/time-integrity/cleanup?dry_run=false" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

# 4) Restore dry run (director)
curl -fsS -X POST "http://127.0.0.1:8000/api/v1/dashboard/time-integrity/cleanup/restore?dry_run=true&lookback_hours=24&max_rows=200" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

# 5) Apply restore (director)
curl -fsS -X POST "http://127.0.0.1:8000/api/v1/dashboard/time-integrity/cleanup/restore?dry_run=false&lookback_hours=24&max_rows=200" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

## Sanity SQL

```sql
-- stale candidates by status
SELECT status, COUNT(*)
FROM articles
WHERE status NOT IN ('published','archived')
  AND COALESCE(published_at, crawled_at, created_at) < NOW() - INTERVAL '24 hours'
GROUP BY status
ORDER BY COUNT(*) DESC;

-- recent auto archive audit events
SELECT created_at, entity_id, from_state, to_state, reason
FROM action_audit_logs
WHERE action = 'auto_archived_stale'
ORDER BY created_at DESC
LIMIT 50;

-- recent restore audit events
SELECT created_at, entity_id, from_state, to_state, reason
FROM action_audit_logs
WHERE action = 'auto_archived_stale_restored'
ORDER BY created_at DESC
LIMIT 50;
```
