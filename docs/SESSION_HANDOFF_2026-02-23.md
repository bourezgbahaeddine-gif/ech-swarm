# Session Handoff — 2026-02-23

## 1) Current Production Status (Server)

From your last server output:

- `GET /api/v1/sources/policy` => `405`
- `GET /api/v1/sources/health` => `500`
- `POST /api/v1/sources/health/apply` => `404`

Backend log confirms old `sources.py` query is still running (old GROUP BY form), so the server is **not on latest commits**.

Also server `git log --oneline -n 8` shows:

- `839d558` on top
- missing newer commits (`77f90dc`, `ab61980`, `e55b0ea`, `324b5ab`)

## 2) What Was Implemented Locally

### Phase 1
- `839d558` Sources phase-1: blocked self-domain ingestion + health endpoint baseline

### Phase 2
- `77f90dc` Diversity guard + auto-tuning apply endpoint

### Phase 3
- `ab61980` Source policy UI + runtime policy endpoints
- `e55b0ea` Route collision fix (`/{source_id:int}`) to unblock `/sources/policy`
- `324b5ab` PostgreSQL GROUP BY fix for `/sources/health`

## 3) Root Cause

Deployment mismatch:

- Server `main` stayed on `839d558`
- New commits were not present on server branch used by backend container

So containers rebuild correctly, but from old code.

## 4) Exact Recovery Procedure (Tomorrow)

### A) On local machine (PowerShell)
```powershell
cd "d:\AI Agent GOOGLE\echorouk-swarm"
git log --oneline -n 10
git push origin main
```

### B) On server (SSH)
```bash
cd ~/ech-swarm
git fetch --all --prune
git checkout main
git log --oneline -n 10
git pull --ff-only origin main
git log --oneline -n 10
```

Expected top commits after pull:

1. `324b5ab`
2. `e55b0ea`
3. `ab61980`
4. `77f90dc`
5. `839d558`

If `ff-only` fails بسبب اختلافات محلية:
```bash
git status
git stash push -u -m "pre-sync-2026-02-24"
git pull --ff-only origin main
```

### C) Rebuild + recreate
```bash
docker compose build --no-cache backend worker frontend
docker compose up -d --force-recreate backend worker frontend
sleep 8
curl -sS http://127.0.0.1:8000/health
```

### D) Verify loaded code inside backend container
```bash
docker compose exec -T backend sh -lc "grep -n '@router.get(\"/policy\")' /app/app/api/routes/sources.py"
docker compose exec -T backend sh -lc "grep -n '@router.post(\"/health/apply\")' /app/app/api/routes/sources.py"
docker compose exec -T backend sh -lc "grep -n 'source_name_expr = func.lower(func.coalesce(Article.source_name, \"\"))' /app/app/api/routes/sources.py"
docker compose exec -T backend sh -lc "grep -n '@router.put(\"/{source_id:int}\")' /app/app/api/routes/sources.py"
```

### E) API verification
```bash
TOKEN=$(curl -sS -X POST http://127.0.0.1:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"bourezgb","password":"password123"}' \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')

curl -sS "http://127.0.0.1:8000/api/v1/sources/policy" \
  -H "Authorization: Bearer $TOKEN"

curl -sS "http://127.0.0.1:8000/api/v1/sources/health?hours=48&include_disabled=true" \
  -H "Authorization: Bearer $TOKEN"

curl -sS -X POST "http://127.0.0.1:8000/api/v1/sources/health/apply?hours=48&dry_run=true&include_disabled=true" \
  -H "Authorization: Bearer $TOKEN"
```

## 5) Tomorrow Start Point

After recovery is confirmed:

1. Validate Source Policy UI behavior in `/sources`
2. Test real apply (`dry_run=false`) with small window
3. Move to Phase 4: source-category balancing + smarter candidate quality weighting

