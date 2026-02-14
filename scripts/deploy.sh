#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-$HOME/ech-swarm}"
BRANCH="${BRANCH:-main}"
DOMAIN="${DOMAIN:-echswarm.agentdz.com}"

echo "[1/7] Update code"
cd "$PROJECT_DIR"
git fetch origin
git reset --hard "origin/$BRANCH"

echo "[2/7] Build and start containers"
docker compose down
docker compose up -d --build

echo "[3/7] Wait for backend container"
for i in {1..30}; do
  if docker compose ps backend | grep -q "Up"; then
    break
  fi
  sleep 2
done

echo "[4/7] Run migrations"
docker compose exec -T backend sh -lc "PYTHONPATH=/app alembic -c /app/alembic.ini upgrade head"

echo "[5/7] Restart backend after migration"
docker compose restart backend
sleep 3

echo "[6/7] Local smoke checks"
curl -fsS http://127.0.0.1:8000/health >/dev/null
curl -fsS http://127.0.0.1:3000 >/dev/null

echo "[7/7] Public smoke checks"
curl -fsS "https://$DOMAIN/api/v1/health" >/dev/null
curl -fsS "https://$DOMAIN" >/dev/null

echo "Deploy completed successfully."
