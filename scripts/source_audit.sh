#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
USERNAME="${USERNAME:-bourezgb}"
PASSWORD="${PASSWORD:-password123}"
HOURS="${HOURS:-48}"

echo "[1/4] health"
curl -fsS "$BASE_URL/health" >/dev/null
echo "ok"

echo "[2/4] login"
TOKEN="$(
  curl -fsS -X POST "$BASE_URL/api/v1/auth/login" \
    -H "Content-Type: application/json" \
    -d "{\"username\":\"$USERNAME\",\"password\":\"$PASSWORD\"}" \
  | python3 -c 'import sys, json; print(json.load(sys.stdin)["access_token"])'
)"
echo "ok"

echo "[3/4] source stats"
curl -fsS "$BASE_URL/api/v1/sources/stats" \
  -H "Authorization: Bearer $TOKEN"
echo

echo "[4/5] source health"
curl -fsS "$BASE_URL/api/v1/sources/health?hours=$HOURS&include_disabled=true" \
  -H "Authorization: Bearer $TOKEN"
echo

echo "[5/5] source health apply (dry run)"
curl -fsS -X POST "$BASE_URL/api/v1/sources/health/apply?hours=$HOURS&dry_run=true&include_disabled=true" \
  -H "Authorization: Bearer $TOKEN"
echo

echo "done"
