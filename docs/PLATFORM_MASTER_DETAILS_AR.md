# تفاصيل المنصة الرئيسية — Echorouk Editorial OS

آخر تحديث: 2026-03-09

هذا الملف مرجع شامل للمنصة (المنتج + المعمارية + الوحدات + الحوكمة + التشغيل + السياسات الزمنية).

## 1) تعريف المنصة
منصة تشغيل لغرفة الأخبار تدير دورة الخبر من الالتقاط حتى الجاهزية للنشر اليدوي مع حوكمة صارمة وHuman‑in‑the‑Loop.
المنصة ليست CMS ولا تنشر تلقائياً.

## 2) المبادئ التشغيلية
- القرار التحريري النهائي بيد الإنسان.
- الأعمال الثقيلة تُنفّذ لا تزامنيًا عبر طوابير.
- فصل واضح بين الالتقاط، الكتابة، الاعتماد، والمتابعة بعد النشر.
- تتبع كامل عبر `request_id` و`correlation_id`.

## 3) المعمارية المختصرة
- الواجهة: Next.js + React + React Query.
- الـ API: FastAPI + Pydantic + SQLAlchemy.
- البيانات: PostgreSQL + pgvector + Redis.
- الطوابير: Celery + Redis Broker/Result.
- التخزين: MinIO.
- التغذية: FreshRSS + RSS‑Bridge.

الخدمات الأساسية (Docker):
- `ech-backend`
- `ech-worker`
- `ech-frontend`
- `ech-postgres`
- `ech-redis`
- `ech-minio`
- `ech-freshrss-db`
- `ech-freshrss`
- `ech-rssbridge`

المنافذ الافتراضية:
- Backend: `8000`
- Frontend: `3000`
- Flower: `5555`
- Postgres: `5433`
- Redis: `6380`
- MinIO: `9000/9001`
- FreshRSS: `8082`
- RSS‑Bridge: `8083`

## 4) تدفق الخبر (Pipeline)
- Scout يلتقط ويُنظّف ويزيل التكرار.
- Router يصنّف ويُرتّب الأولويات.
- Scribe يُنتج مسودة أولية قابلة للتحرير.
- Smart Editor يتيح التحرير + المراجعات + الاعتماد.
- Chief Approval اعتماد نهائي.
- النشر يدوي خارج المنصة.

حالات `news_status` الأساسية:
`new` → `cleaned` → `deduped` → `classified` → `candidate` → `approved` → `approved_handoff` → `draft_generated` → `ready_for_chief_approval` → `approval_request_with_reservations` → `ready_for_manual_publish` → `published`/`archived`.

## 5) الوكلاء والمهام الآلية
- Scout: التقاط + تنظيف + إزالة تكرار.
- Router: تصنيف + توجيه + أولوية.
- Scribe: مسودات + SEO + دعم بالسياق.
- Trend Radar: رصد الترندات.
- Published Monitor: مراقبة جودة المحتوى المنشور.
- Audience Simulator: محاكاة ردود الجمهور.
- Competitor X‑Ray: زوايا المنافسين.
- MSI: مؤشرات الاستقرار السياقي.
- Document Intelligence + Media Logger.

## 6) المحرر الذكي (Smart Editor)
- محرر TipTap بآلية Diff‑first (لا تعديل تلقائي).
- مركز قرار: عاجل الآن، يحسّن الجودة، تحسينات إضافية.
- وضع السرعة (افتراضي) ووضع العمق.
- طبقة مراجعة احترافية + طبقة ثقة وتفسير (مطويتان افتراضياً).
- زر “التالي” يقود لأهم إجراء.
- تبويبات أساسية مع “أدوات متقدمة” عند الحاجة.
- تدقيق لغوي + أسلوبي + قواعد تحريرية.
- بوابة نشر تمنع الإرسال عند وجود موانع.

## 7) مراقبة المحتوى المنشور (Post‑Publish Monitor)
- فحص دوري كل 15 دقيقة للمحتوى المنشور عبر RSS.
- تقييم تلقائي للعنوان والبنية واللغة والأسلوب.
- إرسال تنبيه عند انخفاض الدرجة عن العتبة.
- واجهة مخصصة في الشريط العلوي (جودة المحتوى المنشور).

إعدادات البيئة الأساسية:
- `ECHOROUK_OS_PUBLISHED_MONITOR_ENABLED`
- `ECHOROUK_OS_PUBLISHED_MONITOR_INTERVAL_MINUTES`
- `ECHOROUK_OS_PUBLISHED_MONITOR_FEED_URL`
- `ECHOROUK_OS_PUBLISHED_MONITOR_ALERT_THRESHOLD`

## 8) أرشيف الشروق + RAG
- زاحف خلفي يبني الأرشيف تدريجياً.
- الجداول: `archive_crawl_states`, `archive_crawl_urls`.
- الحالات: `discovered`, `processing`, `fetched`, `indexed`, `failed`, `skipped`.
- تصفية المسارات غير المقالية عبر `NON_ARTICLE_PREFIXES`.
- إعادة ضبط العالق عبر `ECHOROUK_OS_ECHOROUK_ARCHIVE_STALE_PROCESSING_MINUTES`.

واجهات الأرشيف:
- `GET /api/v1/archive/echorouk/status`
- `GET /api/v1/archive/echorouk/search?q=...&limit=...`
- `POST /api/v1/archive/echorouk/run?listing_pages=...&article_pages=...`

RAG:
- `ECHOROUK_OS_ECHOROUK_ARCHIVE_RAG_ENABLED`
- `ECHOROUK_OS_ECHOROUK_ARCHIVE_RAG_MIN_SCORE`
- `ECHOROUK_OS_ECHOROUK_ARCHIVE_RAG_LIMIT`
- `ECHOROUK_OS_ECHOROUK_ARCHIVE_RAG_PREFER_CATEGORY_MATCH`

## 9) الوحدات الرئيسية
- News + Editorial + Smart Editor.
- Stories + Story Clusters.
- Script Studio.
- Trends Radar.
- Events Memo + Digital Team.
- Competitor X‑Ray.
- MSI + Simulator.
- Document Intelligence + Media Logger.
- Project Memory.
- Archive Search UI.

## 10) RBAC
الأدوار:
- `director`
- `editor_chief`
- `journalist`
- `social_media`
- `print_editor`

## 11) ملخص قاعدة البيانات
- أساسي: `articles`, `sources`, `editorial_drafts`, `editor_decisions`, `article_quality_reports`, `pipeline_runs`, `job_runs`, `failed_jobs`, `users`.
- معرفة/متجهات: `article_profiles`, `article_chunks`, `article_vectors`, `article_entities`, `story_clusters`.
- أرشيف: `archive_crawl_states`, `archive_crawl_urls`.
- رقمي/سوشيال: `social_tasks`, `social_posts`.
- محاكاة/سياق: `sim_runs`, `sim_results`, `msi_runs`.
- منافسون: `competitor_xray_items`.

## 12) التشغيل السريع (Ops)
تحديث ونشر:
1) `git pull --ff-only origin main`
2) `docker compose up -d --build --force-recreate backend worker frontend`
3) `docker compose exec backend alembic upgrade head`
4) فحص الصحة: `curl http://127.0.0.1:8000/health`

## 13) أهم متغيرات البيئة
- مفاتيح المزودات: `ECHOROUK_OS_GEMINI_API_KEY`, `ECHOROUK_OS_GROQ_API_KEY`.
- الأرشيف: `ECHOROUK_OS_ECHOROUK_ARCHIVE_*`.
- RAG: `ECHOROUK_OS_ECHOROUK_ARCHIVE_RAG_*`.
- المراقبة بعد النشر: `ECHOROUK_OS_PUBLISHED_MONITOR_*`.
- FreshRSS/RSS‑Bridge: `ECHOROUK_OS_FRESHRSS_*`, `ECHOROUK_OS_RSSBRIDGE_*`.
- الطوابير: `ECHOROUK_OS_QUEUE_*`.

## 14) الواجهة
- الإنتاج: `https://echswarm.agentdz.com/`
- المحرر الذكي: `/workspace-drafts`
- الأرشيف: `/archive`

---
مرجع إضافي: `docs/INSTRUCTURE_PLATFORM.md`, `docs/architecture.md`, `docs/M5_SMART_EDITOR.md`, `docs/PUBLISHED_CONTENT_MONITOR.md`.
