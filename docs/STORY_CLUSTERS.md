# Story Clusters

## Goal

Expose operational visibility for event clustering so editors can quickly inspect duplicate pressure, top entities/topics, and cluster freshness.

## API

### `GET /api/v1/stories/clusters`

Query params:

- `hours` (default `24`, range `1..168`)
- `category` (optional)
- `min_size` (default `2`, range `2..100`)
- `limit` (default `20`, range `1..100`)

Response shape:

- `generated_at`
- `window_hours`
- `filters`
- `metrics`
- `items`

Metrics:

- `clusters_created`: number of clusters created during the selected window
- `average_cluster_size`: average `cluster_size` of returned clusters
- `time_to_cluster_minutes`: average elapsed time between article ingest timestamp and cluster membership timestamp

Each cluster item includes:

- `cluster_id`, `cluster_key`, `label`, `category`, `geography`
- `cluster_size`
- `top_entities` (max 5)
- `top_topics` (max 5)
- `members` (max 30)

## Frontend

Route: `frontend/src/app/stories/page.tsx`

Added a `Story Clusters` section with:

- window/min-size filters
- KPI strip (`clusters_created`, `average_cluster_size`, `time_to_cluster_minutes`)
- cluster cards with top entities/topics and member headlines

## Validation

```bash
# API smoke
curl -fsS "http://127.0.0.1:8000/api/v1/stories/clusters?hours=24&min_size=2&limit=10" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

# Expected keys
# - metrics.clusters_created
# - metrics.average_cluster_size
# - metrics.time_to_cluster_minutes
# - items[].top_entities
# - items[].top_topics
```

## Tests

- `backend/tests/test_stories_activation.py::test_list_story_clusters_returns_metrics_and_members`

## Rollback

No schema change in this slice.

Rollback is code-only:

1. Revert commit containing `/stories/clusters` endpoint and frontend section.
2. Rebuild and restart `backend` and `frontend` containers.
