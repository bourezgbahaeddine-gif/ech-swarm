# YouTube Trends Integration - Rollout

## Added
- Trend Radar now supports a new source signal: `youtube_trending` (YouTube Data API v3).
- Settings page (director only) now includes:
  - `YOUTUBE_DATA_API_KEY`
  - `YOUTUBE_TRENDS_ENABLED` (`true/false`)
- Settings test endpoint supports:
  - `GET /api/v1/settings/test/YOUTUBE_DATA_API_KEY`
  - `GET /api/v1/settings/test/YOUTUBE_TRENDS_ENABLED`

## Behavior
- If `YOUTUBE_TRENDS_ENABLED=true` and key exists, trend scan pulls popular videos by region.
- Extracted terms from YouTube titles/entities are merged with Google Trends terms.
- Cross-validation now accepts YouTube as a first-class source signal.
- Confidence scoring includes a YouTube contribution.

## Env keys
- `ECHOROUK_OS_YOUTUBE_DATA_API_KEY=`
- `ECHOROUK_OS_YOUTUBE_TRENDS_ENABLED=false`

## Deploy
1. `git pull origin main`
2. `docker compose build backend worker frontend`
3. `docker compose up -d --force-recreate backend worker frontend`

## Enable from platform (Director)
1. Go to `Settings > APIs`.
2. Set `YOUTUBE_DATA_API_KEY`.
3. Set `YOUTUBE_TRENDS_ENABLED` to `true`.
4. Click `Save` for both.
5. Click `Test` on `YOUTUBE_DATA_API_KEY`.
6. Run Trends scan from `/trends`.
