# Echorouk Editorial OS — Architecture Documentation

Echorouk Editorial OS is an enterprise operating system for managing editorial content lifecycle from capture to manual-publish readiness, with strict governance and mandatory Human-in-the-Loop.


## System Architecture

### Data Flow Pipeline

```
                    ┌──────────────────────────────────────────────────────────────────┐
                    │                  ECHOROUK EDITORIAL OS                           │
                    │                                                                  │
  RSS Feeds ────►   │  ┌─────────┐    ┌──────────┐    ┌─────────┐    ┌─────────────┐  │
  (300+ sources)    │  │  Scout  │───►│  Router  │───►│ Scribe  │───►│  Editorial  │  │
                    │  │ Agent   │    │  Agent   │    │ Agent   │    │  Dashboard  │  │
                    │  └────┬────┘    └────┬─────┘    └────┬────┘    └──────┬──────┘  │
                    │       │              │               │                │          │
                    │       ▼              ▼               ▼                ▼          │
                    │  ┌──────────────────────────────────────────────────────────┐    │
                    │  │                    PostgreSQL + pgvector                 │    │
                    │  │                    Redis (Cache + Queue)                 │    │
                    │  │                    MinIO (Object Storage)                │    │
                    │  └──────────────────────────────────────────────────────────┘    │
                    │                                                                  │
                    │  ┌────────────┐    ┌───────────────┐                             │
                    │  │   Trend    │    │    Audio      │                             │
                    │  │   Radar    │    │    Agent      │                             │
                    │  └────────────┘    └───────────────┘                             │
                    └──────────────────────────────────────────────────────────────────┘
```

### Article Status Pipeline

```
NEW → CLEANED → DEDUPED → CLASSIFIED → CANDIDATE → APPROVED → PUBLISHED → ARCHIVED
                                            │                      │
                                            ├──► REJECTED          │
                                            │                      │
                                            └──► REWRITE ────►────┘
```

### Deduplication Strategy (Three-Layer)

1. **Layer 1: SHA1 Hash** — Exact URL + title match check against Redis (24h TTL)
2. **Layer 2: Database Check** — Fallback to PostgreSQL unique_hash index
3. **Layer 3: Levenshtein Fuzzy** — Token-sort ratio against recent 200 titles (threshold: 70%)

### Cost Optimization: Tiered AI Processing

```
Input Text
    │
    ▼
┌─────────────────┐
│  Python Rules   │──── If confident (2+ keyword matches) → FREE classification
│  (Keywords)     │
└────────┬────────┘
         │ uncertain
         ▼
┌─────────────────┐
│  Gemini Flash   │──── Fast, cheap classification + analysis
│  ($0.002/call)  │
└────────┬────────┘
         │ complex/investigative
         ▼
┌─────────────────┐
│  Gemini Pro     │──── Deep analysis, large docs (only when needed)
│  ($0.01/call)   │
└─────────────────┘
```

### Database Schema (ER Diagram)

```
┌──────────────┐     ┌──────────────┐     ┌───────────────────┐
│   sources    │     │   articles   │     │ editor_decisions  │
├──────────────┤     ├──────────────┤     ├───────────────────┤
│ id           │     │ id           │     │ id                │
│ name         │◄────│ source_id    │────►│ article_id        │
│ url          │     │ unique_hash  │     │ editor_name       │
│ category     │     │ status       │     │ decision          │
│ trust_score  │     │ category     │     │ reason            │
│ priority     │     │ importance   │     │ edited_title      │
│ enabled      │     │ urgency      │     │ edited_body       │
│ error_count  │     │ title_ar     │     │ decided_at        │
└──────────────┘     │ summary      │     └───────────────────┘
                     │ body_html    │
                     │ entities     │     ┌───────────────────┐
                     │ keywords     │     │  feedback_logs    │
                     │ truth_score  │     ├───────────────────┤
                     │ ai_model     │     │ id                │
                     │ trace_id     │     │ article_id        │
                     └──────────────┘     │ field_name        │
                                          │ original_value    │
                     ┌──────────────┐     │ corrected_value   │
                     │ failed_jobs  │     │ correction_type   │
                     ├──────────────┤     └───────────────────┘
                     │ id           │
                     │ job_type     │     ┌───────────────────┐
                     │ payload      │     │  pipeline_runs    │
                     │ error_msg    │     ├───────────────────┤
                     │ retry_count  │     │ id                │
                     │ resolved     │     │ run_type          │
                     └──────────────┘     │ total_items       │
                                          │ new_items         │
                                          │ duplicates        │
                                          │ errors            │
                                          │ status            │
                                          └───────────────────┘
```

## Security Model

### Input Validation Pipeline

```
Raw Input → Strip HTML → Remove Scripts → Decode Entities → Remove XSS Patterns → Clean Whitespace → Output
```

### Secret Management

- All secrets in `.env` (never committed)
- `.env.example` for documentation only
- Docker secrets for production deployment
- API keys validated on startup
