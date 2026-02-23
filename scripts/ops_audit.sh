#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
USERNAME="${USERNAME:-bourezgb}"
PASSWORD="${PASSWORD:-password123}"
MONITOR_LIMIT="${MONITOR_LIMIT:-12}"
MONITOR_WAIT_SECONDS="${MONITOR_WAIT_SECONDS:-90}"

echo "[1/8] Health check"
curl -fsS "$BASE_URL/health" >/dev/null
echo "OK health"

echo "[2/8] Login"
TOKEN="$(
  curl -fsS -X POST "$BASE_URL/api/v1/auth/login" \
    -H "Content-Type: application/json" \
    -d "{\"username\":\"$USERNAME\",\"password\":\"$PASSWORD\"}" \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])'
)"
echo "OK token"

echo "[3/8] Agents status"
curl -fsS "$BASE_URL/api/v1/dashboard/agents/status" -H "Authorization: Bearer $TOKEN" >/dev/null
echo "OK agents status"

echo "[4/8] Trigger published monitor with wait=true"
RUN_RESP="$(
  curl -fsS -X POST "$BASE_URL/api/v1/dashboard/agents/published-monitor/run?wait=true&wait_timeout_seconds=$MONITOR_WAIT_SECONDS&limit=$MONITOR_LIMIT" \
    -H "Authorization: Bearer $TOKEN"
)"
echo "$RUN_RESP"

echo "[5/8] Latest published monitor"
LATEST_RESP="$(
  curl -fsS "$BASE_URL/api/v1/dashboard/agents/published-monitor/latest?refresh_if_empty=true&limit=$MONITOR_LIMIT" \
    -H "Authorization: Bearer $TOKEN"
)"
echo "$LATEST_RESP"

echo "[6/8] Dashboard notifications"
NOTIF_RESP="$(
  curl -fsS "$BASE_URL/api/v1/dashboard/notifications?limit=30" \
    -H "Authorization: Bearer $TOKEN"
)"
echo "$NOTIF_RESP" | python3 - <<'PY'
import json, sys
payload = json.load(sys.stdin)
items = payload.get("items", [])
has_quality = any(i.get("type") == "published_quality" for i in items)
print(f"notifications_total={len(items)} has_published_quality={has_quality}")
PY

echo "[7/8] Queues depth"
curl -fsS "$BASE_URL/api/v1/jobs/queues/depth" -H "Authorization: Bearer $TOKEN"
echo

echo "[8/8] Failed jobs snapshot"
curl -fsS "$BASE_URL/api/v1/jobs?limit=20&status_filter=failed" -H "Authorization: Bearer $TOKEN"
echo

echo "Audit completed."
