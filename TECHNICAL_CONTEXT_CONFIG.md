# TECHNICAL CONTEXT - CONFIG FILES

## 1) Frontend Config
- Package and scripts:
  - `frontend/package.json`
- TypeScript:
  - `frontend/tsconfig.json`
- Next.js:
  - `frontend/next.config.ts`
- ESLint:
  - `frontend/eslint.config.mjs`
- PostCSS/Tailwind:
  - `frontend/postcss.config.mjs`
  - `frontend/src/app/globals.css`

## 2) Backend Config
- Dependencies:
  - `backend/requirements.txt`
- App settings:
  - `backend/app/core/config.py`
- App entry:
  - `backend/app/main.py`
- DB migrations:
  - `alembic.ini`
  - `alembic/`

## 3) Environment and Deployment
- Env templates:
  - `.env.example`
  - `.env` (runtime secrets, not committed)
- Containers:
  - `docker-compose.yml`
  - `backend/Dockerfile`
  - `frontend/Dockerfile`

## 4) Queue and Worker Runtime
- Queue service config and usage:
  - `backend/app/services/job_queue_service.py`
  - `backend/app/queue/` (if present in branch)
- Worker entrypoints and task definitions:
  - `backend/app/queue/tasks/`
  - `backend/app/agents/`

## 5) Agent Onboarding Checklist
When an agent starts work, load in this order:
1. `PROJECT_KNOWLEDGE_BASE.md`
2. `DEVELOPMENT_GUIDELINES.md`
3. `STATE_DATA_MANAGEMENT.md`
4. `STYLING_RULES.md`
5. `TECHNICAL_CONTEXT_TYPES.md`
6. `TECHNICAL_CONTEXT_CONFIG.md`

## 6) Change Control
Update this file whenever:
- scripts in `package.json` change
- required backend dependencies change
- env variable keys change
- docker service topology changes
