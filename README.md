<div align="center">

# 🚀 Echorouk AI Swarm — غرفة الشروق الذكية

### AI-Powered Newsroom Automation Platform

**Automate news ingestion, analysis, writing, and trend detection — powered by Gemini, Groq, and a swarm of specialized AI agents.**

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791?logo=postgresql&logoColor=white)](https://postgresql.org)
[![Next.js](https://img.shields.io/badge/Next.js-16-000000?logo=next.js&logoColor=white)](https://nextjs.org)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)](https://docker.com)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

</div>

---

## 📖 Overview

**Echorouk AI Swarm** is a production-grade AI newsroom system designed for [Echorouk Online](https://www.echoroukonline.com), one of Algeria's leading digital news platforms. It automates the entire news lifecycle — from RSS ingestion through AI analysis to editorial-ready articles — while maintaining human editorial oversight at every critical decision point.

### 🎯 Key Principles

| Principle | Implementation |
|-----------|---------------|
| **Cost-Efficiency** | Gemini Flash for bulk tasks, Groq for speed, Pro only when needed |
| **Zero Trust** | All inputs sanitized, no hardcoded secrets, environment-based config |
| **Idempotency** | Triple deduplication: SHA1 hash → Redis cache → Levenshtein fuzzy |
| **Human-in-the-Loop** | Editorial review for every candidate before generation |
| **Graceful Degradation** | Retry with exponential backoff, DLQ for failures, no silent crashes |
| **RLHF Feedback** | Tracks diffs between AI output and editor corrections |

---

## 🤖 The Agent Swarm

```
RSS Sources (300+)
       │
       ▼
  ┌─────────┐    ┌─────────┐    ┌──────────┐    ┌─────────┐
  │  Scout   │───►│ Router  │───►│  Scribe  │───►│ Editor  │
  │ الكشّاف  │    │ الموجّه  │    │ الكاتب   │    │ التحرير │
  └─────────┘    └─────────┘    └──────────┘    └─────────┘
       │              │               │
       │         ┌────┴────┐    ┌─────┴─────┐
       │         │  Trend  │    │   Audio   │
       │         │  Radar  │    │ المذيع    │
       │         └─────────┘    └───────────┘
       │
  [ PostgreSQL + Redis + MinIO ]
```

| Agent | Role | AI Model | Cost |
|-------|------|----------|------|
| 🔍 **Scout** (الكشّاف) | RSS ingestion, deduplication | None (pure Python) | $0 |
| 🧭 **Router** (الموجّه) | Classification, urgency, routing | Gemini Flash (when needed) | ~$0.002/article |
| ✍️ **Scribe** (الكاتب) | Article generation, SEO | Groq → Gemini Flash | ~$0.01/article |
| 📡 **Trend Radar** (رادار التراند) | Cross-platform trend detection | Gemini Flash | ~$0.005/scan |
| 🎙️ **Audio** (المذيع الآلي) | TTS audio news briefings | Edge-TTS (free) + Gemini | ~$0.001/briefing |

---

## 🏗️ Architecture

```
echorouk-swarm/
├── backend/
│   ├── app/
│   │   ├── core/          # Config, Database, Logging
│   │   ├── models/        # SQLAlchemy ORM Models
│   │   ├── schemas/       # Pydantic Request/Response
│   │   ├── agents/        # AI Agent implementations (5 agents)
│   │   ├── services/      # Shared services (AI, Cache, Notifications)
│   │   ├── api/routes/    # FastAPI endpoints
│   │   ├── utils/         # Hashing, Text processing
│   │   └── main.py        # Application entry point
│   ├── tests/             # Unit & integration tests
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/              # Next.js 16 Dashboard
│   ├── src/
│   │   ├── app/           # 6 pages (Dashboard, News, Editorial, Sources, Agents, Trends)
│   │   ├── components/    # Reusable UI components (Layout, Dashboard widgets)
│   │   └── lib/           # API client, utilities, providers
│   ├── Dockerfile
│   └── package.json
├── scripts/
│   └── init_db.sql        # DB initialization + 25 RSS sources
├── docs/                  # Architecture & agent documentation
├── docker-compose.yml     # Full development stack
├── .env.example           # Environment variables template
└── README.md
```

---

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- A **Gemini API Key** ([Get one free](https://makersuite.google.com/app/apikey))
- (Optional) A **Groq API Key** ([Get one free](https://console.groq.com/keys))

### 1. Clone & Configure

```bash
git clone https://github.com/your-username/echorouk-swarm.git
cd echorouk-swarm

# Copy environment template
cp .env.example .env

# Edit .env with your API keys
nano .env  # or use any editor
```

### 2. Start with Docker

```bash
# Start all services (PostgreSQL, Redis, MinIO, Backend)
docker-compose up -d

# View logs
docker-compose logs -f backend
```

### 3. Verify Installation

```bash
# Health check
curl http://localhost:8000/health

# Open API docs
open http://localhost:8000/docs
```

### FreshRSS + RSS-Bridge Mode (Recommended for stable ingestion)

Use this mode to centralize all feeds in FreshRSS and bridge non-RSS sources through RSS-Bridge.

1. In `.env`:
```bash
SCOUT_USE_FRESHRSS=true
FRESHRSS_FEED_URL=http://freshrss:80/p/i/?a=rss&state=all
RSSBRIDGE_ENABLED=true
RSSBRIDGE_BASE_URL=http://rssbridge:80
```

2. Start stack:
```bash
docker compose up -d --build
```

3. Open admin UIs:
- FreshRSS: `http://SERVER_IP:8082`
- RSS-Bridge: `http://SERVER_IP:8083`

4. Add feed sources in FreshRSS:
- Native RSS feeds directly
- Non-RSS feeds using RSS-Bridge URLs

5. Run Scout as usual. It will pull from `FRESHRSS_FEED_URL` when `SCOUT_USE_FRESHRSS=true`.

### 4. Run Without Docker (Development)

```bash
cd backend

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the server
uvicorn app.main:app --reload --port 8000
```

---

## 📡 API Reference

### Core Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | System health check |
| `GET` | `/docs` | Interactive API documentation (Swagger) |
| `GET` | `/redoc` | Alternative API documentation |

### News Articles (`/api/v1/news`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/news/` | List articles (paginated, filtered) |
| `GET` | `/api/v1/news/{id}` | Get article details |
| `GET` | `/api/v1/news/breaking/latest` | Get latest breaking news |
| `GET` | `/api/v1/news/candidates/pending` | Get pending review articles |

### Sources (`/api/v1/sources`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/sources/` | List all RSS sources |
| `POST` | `/api/v1/sources/` | Register new source |
| `PUT` | `/api/v1/sources/{id}` | Update source |
| `DELETE` | `/api/v1/sources/{id}` | Remove source |
| `GET` | `/api/v1/sources/stats` | Source statistics |

### Editorial (`/api/v1/editorial`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/editorial/{id}/decide` | Approve/Reject/Rewrite |
| `GET` | `/api/v1/editorial/{id}/decisions` | Decision history |
| `POST` | `/api/v1/editorial/{id}/generate` | Trigger article writing |

### Dashboard (`/api/v1/dashboard`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/dashboard/stats` | Real-time statistics |
| `GET` | `/api/v1/dashboard/pipeline-runs` | Pipeline execution logs |
| `GET` | `/api/v1/dashboard/failed-jobs` | Dead Letter Queue |
| `POST` | `/api/v1/dashboard/agents/scout/run` | Trigger Scout Agent |
| `POST` | `/api/v1/dashboard/agents/router/run` | Trigger Router Agent |
| `POST` | `/api/v1/dashboard/agents/scribe/run` | Trigger Scribe Agent |
| `POST` | `/api/v1/dashboard/agents/trends/scan` | Trigger Trend Radar |
| `GET` | `/api/v1/dashboard/agents/status` | Agent statuses |

---

## 🔧 Configuration

All configuration is done through environment variables. See [`.env.example`](.env.example) for the full list.

### Key Configuration Groups

| Group | Variables | Description |
|-------|-----------|-------------|
| **AI** | `GEMINI_API_KEY`, `GROQ_API_KEY` | AI service credentials |
| **Database** | `POSTGRES_*` | PostgreSQL connection |
| **Cache** | `REDIS_*` | Redis connection |
| **Notifications** | `TELEGRAM_BOT_TOKEN`, `SLACK_WEBHOOK_URL` | Alert channels |
| **Thresholds** | `DEDUP_SIMILARITY_THRESHOLD`, `BREAKING_NEWS_URGENCY_THRESHOLD` | Processing parameters |
| **TTS** | `TTS_VOICE`, `TTS_RATE` | Audio generation settings |

---

## 🧪 Testing

```bash
cd backend

# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_utils.py -v
```

---

## 📊 Cost Analysis

| Operation | Model | Cost per Unit | Daily Estimate (500 articles) |
|-----------|-------|---------------|-------------------------------|
| Classification | Gemini Flash | ~$0.002 | ~$0.50 |
| Article Writing | Groq (free tier) | $0.00 | $0.00 |
| Trend Analysis | Gemini Flash | ~$0.005 | ~$0.48 |
| Audio Briefing | Edge-TTS | $0.00 | $0.00 |
| **Total** | | | **~$1/day** |

> 💡 Rule-based pre-filtering reduces AI calls by 50-80%, keeping costs minimal.

---

## 🛡️ Security

- **Zero Trust**: All inputs sanitized (XSS, injection protection)
- **No Hardcoded Secrets**: Everything via environment variables
- **CORS**: Configurable allowed origins
- **Input Validation**: Pydantic schemas on all endpoints
- **Error Isolation**: Global exception handler prevents info leaks

---

## 📋 Roadmap

- [x] Core pipeline (Scout → Router → Scribe)
- [x] Breaking news detection & alerts
- [x] Trend Radar with cross-platform validation
- [x] Audio news briefing generator
- [x] Editorial decision API with RLHF
- [x] Next.js Dashboard (frontend) ✅
- [ ] RAG with pgvector for archive search
- [ ] n8n workflow integration
- [ ] Investigative Agent (large document analysis)
- [ ] Multi-language support (Arabic, French, English)

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

---

<div align="center">

**Built with ❤️ for Algerian Journalism**

**صُنع بعناية لخدمة الصحافة الجزائرية 🇩🇿**

</div>
