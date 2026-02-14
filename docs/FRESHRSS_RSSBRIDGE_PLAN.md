# FreshRSS + RSS-Bridge Integration

## Goal
Use FreshRSS as the single ingestion gateway, and use RSS-Bridge for sources that do not expose native RSS.

## Services
- `freshrss-db` (MariaDB)
- `freshrss`
- `rssbridge`
- Existing `backend`, `frontend`, `postgres`, `redis`, `minio`

## Backend behavior
- `SCOUT_USE_FRESHRSS=true`: Scout reads only `FRESHRSS_FEED_URL`.
- `SCOUT_USE_FRESHRSS=false`: Scout reads sources table directly.
- `RSSBRIDGE_ENABLED=true` and source has `method=scraper` + `rss_url`: Scout tries `rss_url` first (bridge feed), then falls back to direct scrape.

## Required .env keys
- `SCOUT_USE_FRESHRSS`
- `FRESHRSS_FEED_URL`
- `RSSBRIDGE_ENABLED`
- `RSSBRIDGE_BASE_URL`
- `FRESHRSS_BASE_URL`
- `FRESHRSS_DB_*`
- `FRESHRSS_ADMIN_*`

## Nginx (optional public routing)
Example:
```nginx
location /freshrss/ {
    proxy_pass http://127.0.0.1:8082/;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
}

location /rssbridge/ {
    proxy_pass http://127.0.0.1:8083/;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

## Operational flow
1. Add/update feeds in FreshRSS.
2. For non-RSS source, create RSS-Bridge feed URL and subscribe to it in FreshRSS.
3. Trigger Scout.
4. Router and Scribe continue unchanged.

## Notes
- RSS providers may still return 403/404; this is source-level behavior and should be monitored per source.
- Keep Telegram, Gemini, and Groq settings valid to avoid downstream processing failures.
