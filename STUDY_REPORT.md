# Echorouk AI Swarm — Project Study Report

**Date:** 2026-02-10
**Status:** Initial Study & Environment Setup Complete

---

## 1. Executive Summary

**Echorouk AI Swarm** is an advanced, AI-powered newsroom automation platform designed for Echorouk Online. It automates the lifecycle of news production—from ingestion and classification to drafting and trend analysis—while maintaining strict human-in-the-loop oversight.

The system is built on a modern microservices-like architecture using **FastAPI** for the backend and **Next.js 16** for the frontend, fully containerized with **Docker**.

---

## 2. Technical Architecture

### 2.1 Backend (`/backend`)

- **Framework:** FastAPI (Python 3.11).
- **Database:** PostgreSQL 16 with `pgvector` for future RAG capabilities and `pg_trgm` for fuzzy search.
- **Caching & Queue:** Redis (used for deduplication caching and background job management).
- **Storage:** MinIO (S3-compatible object storage) for media assets.
- **AI Integration:**
  - **Gemini Flash/Pro:** For classification, analysis, and drafting.
  - **Groq (Llama 3):** For high-speed, low-cost drafting.
  - **Edge-TTS:** For generating audio briefings.

### 2.2 Frontend (`/frontend`)

- **Framework:** Next.js 16 (App Router).
- **Language:** TypeScript.
- **UI Library:** Shadcn UI + TailwindCSS for a responsive, modern Arabic-first interface.
- **State Management:** React Query (`@tanstack/react-query`) for efficient server-state synchronization.
- **Authentication:** JWT-based auth handling via NextAuth (or custom implementation consuming the backend API).

### 2.3 DevOps

- **Containerization:** Docker & Docker Compose (`docker-compose.yml`).
- **Services:**
  - `backend`: API & Agents.
  - `frontend`: Next.js Dashboard.
  - `postgres`: Data interactions.
  - `redis`: Caching.

---

## 3. Core Components: The Agent Swarm

The system revolves around five specialized AI agents:

| Agent | Arabic Name | Role | Technology |
|-------|-------------|------|------------|
| **Scout** | الكشّاف | Ingests news from 300+ RSS feeds, handles deduplication (SHA1 + Fuzzy). | Python, Redis |
| **Router** | الموجّه | Classifies articles, assigns urgency/category, and routes to pipelines. | Gemini Flash |
| **Scribe** | الكاتب | Drafts full articles in Echorouk's style based on sources. | Groq / Gemini |
| **Trend Radar** | رادار التراند | Detects rising trends by cross-referencing multiple sources/platforms. | Python, Gemini |
| **Audio** | المذيع | Converts top news into audio briefings. | Edge-TTS |

---

## 4. database & User Management

### 4.1 User Roles

The system implements a strict role-based access control (RBAC) system:

- **Director:** Full system access.
- **Editor-in-Chief:** Editorial oversight, approval/rejection.
- **Journalist:** Content creation and viewing.
- **Social Media:** Specific access for social trends.
- **Print Editor:** Access to print-related workflows.

### 4.2 Status Verification

- **Database Seeding:** Successfully executed.
- **Initial Users:** 16 journalist accounts created (e.g., `bourezgb`, `s.hawas`, `m.abdelmoumin`).
- **Fix Applied:** Corrected `UserRole` enum mismatch between Python code (uppercase) and Database (lowercase) to ensure successful seeding.

---

## 5. Current System State

1. **Backend is Healthy:** `docker ps` confirms `ech-backend` is up.
2. **Database is Ready:** `seed_users.py` script ran successfully, populating the `users` table.
3. **Frontend is Running:** `npm run dev` is active.
4. **Integration:** The API is accessible at `http://localhost:8000` (docs at `/docs`), and Frontend assumes connection to it.

## 6. Recommendations & Next Steps

1. **Frontend Verification:** Log in via the frontend (`http://localhost:3000`) using one of the seeded accounts (e.g., `bourezgb` / `password123`) to verify the full end-to-end flow.
2. **Agent Testing:** Manually trigger the **Scout Agent** via the API (`POST /api/v1/dashboard/agents/scout/run`) to populate the database with initial news articles.
3. **Editorial Workflow:** Test the "Approval" loop by navigating to the "Pending" section in the dashboard and approving an article to trigger the **Scribe Agent**.

---
**Prepared by:** Antigravity (AI Assistant)
