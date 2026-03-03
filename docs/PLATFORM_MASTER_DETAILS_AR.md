# Echorouk Editorial OS — الملف المرجعي الشامل للمنصة

> آخر تحديث: 2026-03-03  
> هذا الملف هو مرجع واحد يجمع الصورة الكاملة للمنصة: المنتج، المعمارية، الوحدات، الحوكمة، التشغيل، والسياسات الزمنية.

## 1) تعريف المنصة

**Echorouk Editorial OS** هو نظام تشغيل تحريري (Newsroom Operating System) لإدارة دورة الخبر من الالتقاط حتى **جاهز للنشر اليدوي** مع:

- Human-in-the-Loop إلزامي.
- حوكمة تحريرية صارمة.
- RBAC واضح حسب الدور.
- أتمتة ذكية في الالتقاط/التصنيف/الصياغة.
- أدوات مساعدة داخل غرفة التحرير (تحقق، جودة، SEO، سوشيال، ذاكرة مشروع، محاكاة جمهور، إلخ).

المنصة **ليست CMS للنشر التلقائي**.  
المخرجات النهائية تصل إلى `ready_for_manual_publish` ثم يتم النشر يدويًا خارج النظام.

---

## 2) الهدف التشغيلي

- تسريع دورة الخبر بدون فقدان الضبط التحريري.
- منع الهلوسة والانحراف عبر بوابات جودة + تدقيق ادعاءات + سياسة تحريرية.
- بناء غرفة أخبار قابلة للقياس (latency, queue depth, quality score, rejection causes).
- حماية القاعة من الأخبار القديمة أو غير المؤرخة بسياسة freshness صارمة.

---

## 3) المعمارية التقنية (High-Level)

### 3.1 طبقات النظام

- `Frontend`: Next.js (App Router) + React Query + TipTap.
- `Backend`: FastAPI + SQLAlchemy + Pydantic.
- `Data`: PostgreSQL (مع `pgvector`) + Redis.
- `Storage`: MinIO.
- `Async`: Celery workers + Redis broker/backend.
- `Feeds`: FreshRSS + RSS-Bridge (اختياري/موصى به للتوحيد).

### 3.2 خدمات Docker الرئيسية

- `ech-backend` (API)
- `ech-worker` (Celery worker)
- `ech-flower` (queue monitoring)
- `ech-frontend`
- `ech-postgres`
- `ech-redis`
- `ech-minio`
- `ech-freshrss-db` + `ech-freshrss`
- `ech-rssbridge`

### 3.3 المنافذ الافتراضية

- Backend API: `8000`
- Frontend: `3000`
- Flower: `5555`
- PostgreSQL: `5433 -> 5432`
- Redis: `6380 -> 6379`
- MinIO API/Console: `9000/9001`
- FreshRSS: `8082`
- RSS-Bridge: `8083`

---

## 4) بنية المشروع (مختصرة وعملية)

- `backend/app/agents/`: منطق الوكلاء (Scout/Router/Scribe/Trend/...).
- `backend/app/api/routes/`: REST API domains.
- `backend/app/services/`: orchestration وخدمات الأعمال.
- `backend/app/domain/`: state machine + quality gates.
- `backend/app/repositories/`: data access patterns.
- `backend/app/models/`: SQLAlchemy tables/enums.
- `backend/app/queue/`: Celery app + background tasks.
- `frontend/src/app/`: صفحات النظام.
- `frontend/src/components/`: مكونات الواجهة المشتركة.
- `alembic/versions/`: migrations.
- `docs/`: مرجع التشغيل والتصميم.

---

## 5) دورة الخبر (Workflow الرسمي)

### 5.1 المسار الأساسي

1. التقاط الخبر (Scout).
2. تنظيف/تصنيف/توجيه (Router).
3. إدخال الخبر كمرشح (`candidate`) أو تصنيف عادي.
4. تحرير داخل Smart Editor + أدوات AI.
5. تشغيل بوابات الجودة والتحقق والسياسة.
6. إرسال لرئيس التحرير.
7. قرار نهائي:
   - اعتماد نهائي -> `ready_for_manual_publish`
   - إعادة/رفض مع سبب.
8. النشر اليدوي خارج النظام.

### 5.2 حالات الخبر (`NewsStatus`)

القيم الفعلية في `backend/app/models/news.py`:

- `new`
- `cleaned`
- `deduped`
- `classified`
- `candidate`
- `approved`
- `approved_handoff`
- `draft_generated`
- `ready_for_chief_approval`
- `approval_request_with_reservations`
- `ready_for_manual_publish`
- `rejected`
- `published`
- `archived`

---

## 6) الوكلاء (Agents) وخط الإنتاج الآلي

### 6.1 Scout Agent

- الملف: `backend/app/agents/scout.py`
- الوظيفة: ingestion + dedup + freshness filtering.
- يدعم:
  - مصادر مباشرة RSS/Scraper.
  - FreshRSS feed موحد عند تفعيل `SCOUT_USE_FRESHRSS`.
- dedup متعدد الطبقات:
  - unique hash
  - URL-level dedup
  - fuzzy title dedup
  - cross-source dedup

### 6.2 Router Agent

- التصنيف (category/urgency/breaking).
- مزيج rules + AI fallback.
- يحدد ما يدخل إلى `candidate`.

### 6.3 Scribe Agent

- إعادة صياغة وصناعة draft قابل للتحرير.
- fallback provider routing (Groq/Gemini) حسب الصحة والتوفر.

### 6.4 Trend / Monitor / Other Jobs

- Trend radar scans.
- Published content monitor.
- MSI jobs.
- Audience simulator jobs.
- Script generation jobs.
- Document intelligence extract jobs.

---

## 7) API Domains (الخريطة الكاملة)

جميعها تحت `/api/v1`:

- `/auth` المصادقة والعضوية.
- `/news` الأخبار والبحث/العلاقات.
- `/editorial` دورة التحرير + Smart Editor + chief decisions.
- `/dashboard` إحصاءات + تشغيل الوكلاء + تشغيلية.
- `/sources` إدارة المصادر + policy + health/apply.
- `/rss` ربط مصادر RSS bridge.
- `/settings` إعدادات API + audit.
- `/constitution` الدستور التحريري + acknowledgment.
- `/services` أدوات الصحفي (editor/seo/fact-check/multimedia).
- `/memory` ذاكرة المشروع.
- `/msi` مؤشر MSI.
- `/sim` محاكي الجمهور.
- `/media-logger` تفريغ/تحليل وسائط.
- `/document-intel` استخراج محتوى الوثائق.
- `/competitor-xray` مراقبة المنافسين.
- `/jobs` job status/retry/queues/dead-letter/providers.
- `/stories` إدارة القصص التحريرية.
- `/scripts` Script Studio.
- `/events` مفكرة الأحداث.
- `/digital` عمليات فريق الديجيتال.

---

## 8) وحدات الواجهة (Frontend Modules)

الصفحات الأساسية في `frontend/src/app/`:

- `/` لوحة القيادة.
- `/news` و `/news/[id]`.
- `/editorial`.
- `/workspace-drafts` (Smart Editor Workspace).
- `/trends`.
- `/stories`.
- `/scripts`.
- `/events`.
- `/digital`.
- `/msi`.
- `/simulator`.
- `/competitor-xray`.
- `/memory`.
- `/services/multimedia`.
- `/services/fact-check`.
- `/services/media-logger`.
- `/services/document-intel`.
- `/sources` (مدير).
- `/agents` (مدير).
- `/team` (مدير).
- `/settings` (مدير).

---

## 9) RBAC (الأدوار والصلاحيات)

الأدوار الرسمية في backend (`UserRole`):

- `director`
- `editor_chief`
- `journalist`
- `social_media`
- `print_editor`

### 9.1 صلاحيات عملية

- `director`: صلاحيات كاملة (النظام/العضوية/المصادر/الإعدادات/المراقبة).
- `editor_chief`: اعتماد نهائي، إدارة التدفق التحريري.
- `journalist`: تحرير، ترشيح، أدوات AI، إرسال للمراجعة.
- `social_media`: إدارة مخرجات الديجيتال والسوشيال حسب القنوات.
- `print_editor`: دور تحريري قريب من الصحفي في workflow.

> ملاحظة تقنية: بعض شاشات الواجهة تحتوي role إضافي (`fact_checker`) لأغراض عرض/وصول، لكنه ليس ضمن enum backend الرسمي الحالي.

---

## 10) نموذج البيانات (Data Model)

### 10.1 الجداول الجوهرية

- `articles`
- `sources`
- `editorial_drafts`
- `editor_decisions`
- `article_quality_reports`
- `pipeline_runs`
- `failed_jobs`
- `users`
- `user_activity_logs`
- `api_settings`
- `settings_audit`
- `action_audit_logs`

### 10.2 نطاق القصص والسكريبت

- `stories`, `story_items`
- `script_projects`, `script_outputs`

### 10.3 نطاق الذكاء المعرفي والروابط

- `article_profiles`, `article_topics`, `article_entities`
- `article_chunks`, `article_vectors`, `article_fingerprints`, `article_relations`
- `story_clusters`, `story_cluster_members`
- `link_index_items`, `trusted_domains`, `link_recommendation_runs`, `link_recommendation_items`, `link_click_events`

### 10.4 نطاق الوحدات المتقدمة

- MSI: `msi_runs`, `msi_reports`, `msi_timeseries`, `msi_watchlist`, ...
- Simulator: `sim_runs`, `sim_results`, `sim_feedback`, ...
- Competitor X-Ray: `competitor_xray_sources`, `competitor_xray_runs`, ...
- Media Logger: `media_logger_runs`, `media_logger_segments`, ...
- Events/Digital: `event_memo_items`, `digital_team_scopes`, `program_slots`, `social_tasks`, `social_posts`

---

## 11) Queue & Async Architecture

### 11.1 Celery routing

الصفوف الفعلية:

- `ai_router`
- `ai_scribe`
- `ai_quality`
- `ai_simulator`
- `ai_msi`
- `ai_links`
- `ai_trends`
- `ai_scripts`

### 11.2 المبادئ التشغيلية

- Enqueue-only endpoints للعمليات الثقيلة.
- Backpressure قبل enqueue.
- Idempotency عبر `task_idempotency_keys`.
- DLQ عبر `dead_letter_jobs`.
- تتبع `request_id` + `correlation_id` من API حتى worker logs.

---

## 12) الحوكمة التحريرية والـ Quality Gates

### 12.1 بوابات الجودة النشطة

- `FACT_CHECK`
- `SEO_TECH`
- `READABILITY`
- `QUALITY_SCORE`
- `EDITORIAL_POLICY` (عند توفر تقرير السياسة)

### 12.2 مبدأ الحسم

- وجود blocker يمنع المرور السلس للاعتماد.
- رئيس التحرير يمكنه:
  - `approve`
  - `approve_with_reservations` (بسبب إلزامي)
  - `send_back`
  - `reject` (بسبب إلزامي)

---

## 13) سياسة الزمن (Freshness) — النقطة الأهم تشغيليًا

هذا القسم حرج لضمان أن قاعة التحرير لا تصبح "ميتة زمنيًا".

### 13.1 ما يطبقه Scout فعليًا

- رفض الخبر القديم: `entry_skipped_stale`.
- رفض الخبر المستقبلي بشكل غير منطقي: `entry_skipped_future_timestamp`.
- رفض المصادر/النطاقات المحظورة: `entry_skipped_blocked_source`.
- رفض بلا timestamp (حسب السياسة):
  - `entry_skipped_missing_timestamp`
  - `entry_skipped_missing_timestamp_aggregator`
  - `entry_skipped_missing_timestamp_scraper`
- clamp safety cap لعمر الخبر الأقصى (hard safety rail).

### 13.2 مفاتيح الإعداد المهمة

- `ECHOROUK_OS_SCOUT_MAX_ARTICLE_AGE_HOURS`
- `ECHOROUK_OS_SCOUT_MAX_ARTICLE_FUTURE_MINUTES`
- `ECHOROUK_OS_SCOUT_REQUIRE_TIMESTAMP_FOR_AGGREGATOR`
- `ECHOROUK_OS_SCOUT_REQUIRE_TIMESTAMP_FOR_ALL_SOURCES`
- `ECHOROUK_OS_SCOUT_ALLOW_URL_DATE_FALLBACK`
- `ECHOROUK_OS_SCOUT_INGEST_FILTERS_ENABLED`
- `ECHOROUK_OS_SCOUT_CROSS_SOURCE_DEDUP_ENABLED`
- `ECHOROUK_OS_SCOUT_BLOCKED_DOMAINS`

### 13.3 سياسة صارمة موصى بها للإنتاج

- `SCOUT_MAX_ARTICLE_AGE_HOURS=24`
- `SCOUT_MAX_ARTICLE_FUTURE_MINUTES=5`
- `SCOUT_REQUIRE_TIMESTAMP_FOR_AGGREGATOR=true`
- `SCOUT_REQUIRE_TIMESTAMP_FOR_ALL_SOURCES=true`
- `SCOUT_ALLOW_URL_DATE_FALLBACK=false` (عند الحاجة لصرامة أعلى)
- `SCOUT_INGEST_FILTERS_ENABLED=true`

### 13.4 استبعاد الشروق أونلاين من الالتقاط

بناءً على التوجيه التشغيلي: **لا تعتمد الشروق أونلاين ضمن المصادر**.

التنفيذ عبر:

- `ECHOROUK_OS_SCOUT_BLOCKED_DOMAINS=echoroukonline.com,www.echoroukonline.com`
- أو عبر API policy:
  - `GET /api/v1/sources/policy`
  - `PUT /api/v1/sources/policy`

---

## 14) FreshRSS / RSS-Bridge Integration

### 14.1 نمط التشغيل

- FreshRSS يجمع كل المصادر.
- Scout يسحب feed موحد من FreshRSS.
- RSS-Bridge يغطي المصادر غير RSS.

### 14.2 رابط feed الداخلي الصحيح (داخل شبكة Docker)

- الصيغة التشغيلية الموثوقة داخليًا:
  - `http://freshrss:80/i/?a=rss&state=all&nb=2000`

> يجب التأكد أن قيمة `.env` تكتب بشكل صحيح عند وجود `&` (بدون كسر السطر أو استبدال خاطئ).

---

## 15) المراقبة التشغيلية (Observability)

### 15.1 مؤشرات أساسية

- `dashboard/stats`
- `dashboard/ops/overview`
- `jobs/queues/depth`
- `jobs/providers/health`
- `jobs/dead-letter`
- logs:
  - `freshrss_fetch_started`
  - `scout_run_complete`
  - `entry_skipped_stale`
  - `feed_http_error`
  - `freshrss_feed_empty`

### 15.2 قواعد تشغيل

- لا bypass عبر تعديل DB مباشر للحالات.
- أي enqueue عند ضغط عالي يرجع 429 (backpressure).
- فحص queue depth قبل إطلاق burst jobs.

---

## 16) الأمن والامتثال

- Zero-trust sanitization للمدخلات.
- لا أسرار hardcoded.
- RBAC على المسارات الحساسة.
- audit logs للإعدادات والقرارات.
- فصل أدوار (تحرير/اعتماد/إدارة) لتقليل مخاطر الخطأ.

---

## 17) إعدادات حرجة يجب مراقبتها

### 17.1 جدولة وتشغيل

- `ECHOROUK_OS_AUTO_PIPELINE_ENABLED`
- `ECHOROUK_OS_SCOUT_INTERVAL_MINUTES`
- `ECHOROUK_OS_AUTO_SCRIBE_ENABLED`
- `FRESHRSS_CRON_MIN`

### 17.2 جودة/تكلفة/سعة

- `ECHOROUK_OS_ROUTER_BATCH_LIMIT`
- `ECHOROUK_OS_ROUTER_AI_CALLS_PER_BATCH_CAP`
- `ECHOROUK_OS_QUEUE_DEPTH_LIMIT_*`
- `ECHOROUK_OS_PROVIDER_*`

---

## 18) الحالة التشغيلية الحالية (وفق الأعمال المنجزة)

- تم تفعيل freshness صارم وتشغيل رفض الأخبار القديمة في Scout logs.
- تم أرشفة عدد كبير من العناصر القديمة خارج نافذة الزمن التحريرية.
- ظهر سلوك duplicates مرتفع عند إعادة سحب نفس FreshRSS batch وهذا متوقع.
- عند ضعف/خطأ URL feed في `.env` تظهر `feed_http_error` أو `freshrss_feed_empty`.
- تم تثبيت سياسة عدم الاعتماد على `echoroukonline.com` ضمن المصادر.

---

## 19) خارطة تطوير مقترحة (تنفيذية)

1. تثبيت سياسة freshness كافتراضي إنتاجي (24h + timestamp required).
2. تفعيل تنظيف آلي دوري للعناصر القديمة في الحالات غير المنشورة.
3. بناء شاشة "Time Integrity" في dashboard:
   - oldest candidate age
   - stale skipped count
   - sources with missing timestamps
4. تحسين مصدر FreshRSS:
   - ضبط التنويع لكل مصدر (`SCOUT_FRESHRSS_MAX_PER_SOURCE_PER_RUN`)
   - مراقبة فشل fetch لكل نطاق.
5. تقليل polling في الواجهة إلى SSE/WebSocket في الوحدات الثقيلة.
6. توحيد queue policies وإظهار SLA لكل job type.
7. إضافة connectors نشر اختيارية (WordPress/Drupal/Arc) مع إبقاء default يدوي.

---

## 20) تعريف النجاح التحريري (Operational DoD)

لكي نقول المنصة "صحيحة زمنيًا":

- لا عنصر أقدم من نافذة السياسة يظهر في حالات newsroom النشطة.
- `entry_skipped_stale` يعمل باستمرار عند وجود replay قديم.
- feed URL ثابت وصحيح من داخل backend container.
- queue latency ضمن SLA متفق عليه.
- chief queue تحتوي عناصر حديثة وقابلة للنشر.

---

## 21) مراجع داخلية مكملة

- `README.md`
- `docs/architecture.md`
- `docs/agents.md`
- `docs/M10_ASYNC_ARCHITECTURE.md`
- `docs/QUALITY_GATES.md`
- `docs/TROUBLESHOOTING_PLAYBOOK.md`
- `docs/OPERATIONS_QUICK_COMMANDS.md`
- `docs/PLATFORM_CONTENT_MAP.md`
- `docs/INSTRUCTURE_PLATFORM.md`
- `docs/SESSION_HANDOFF_2026-03-01_SCOUT_FRESHNESS.md`

---

## 22) Roadmap 90-Day (عملي حسب 4 مسارات)

هذه الخطة تحافظ على فلسفة المنصة: `Ready for Manual Publish` + `Human-in-the-Loop`.

### 22.1 المسار A: Time Integrity (الأولوية القصوى)

**الهدف:** منع أي عنصر ميت زمنيًا من دخول newsroom النشطة.

**التنفيذ:**

1. لوحة `Time Integrity` في dashboard:
   - `oldest_candidate_age`
   - `oldest_ready_for_chief_age`
   - عدادات `entry_skipped_*` حسب السبب
   - Top مصادر `missing timestamp`
   - نسبة القبول عبر `URL_DATE_FALLBACK` (عند تفعيله)
2. `Auto-cleaner` دوري:
   - أرشفة أي عنصر غير منشور تجاوز نافذة freshness
   - كتابة سبب موحد (مثل `auto_archived:strict_time_guard`)
3. `Source Health Score` زمني:
   - stale rate
   - missing timestamp rate
   - fetch error rate
   - duplicate rate
4. قائمة مراقبة للمصادر الرديئة (`watchlist`) مع إجراءات مقترحة:
   - reduce priority
   - disable temporarily
   - require manual review

**KPIs:**

- `0` عناصر أقدم من النافذة داخل الحالات النشطة.
- انخفاض متواصل في `oldest_candidate_age`.
- ثبات نسبة skip للأخبار القديمة عند replay بدل دخولها القاعة.

### 22.2 المسار B: Quality Gates 2.0

**الهدف:** تقليل الانحراف والرفض المتأخر قبل وصول المادة لرئيس التحرير.

**التنفيذ:**

1. توحيد مخرجات البوابات إلى:
   - `blocker`
   - `warning`
   - `info`
2. نظام `override` مقيد:
   - لا يملك override إلا `editor_chief`/`director`
   - السبب إجباري + audit log
3. `Claims Graph`:
   - استخراج claims
   - ربط كل claim بدليل (`support link`)
   - وسم `unverifiable` مع سبب عند الحاجة
4. قاعدة انتقال الحالة:
   - لا انتقال إلى `ready_for_chief_approval` إذا claim حساس بلا دعم أو بلا توثيق سبب
5. `Policy-as-code`:
   - قواعد تحريرية قابلة للتحديث عبر JSON/YAML
   - versioning + changelog + rollback

**KPIs:**

- انخفاض `chief_reject_rate`.
- ارتفاع نسبة اجتياز البوابات من أول محاولة.
- انخفاض زمن إعادة العمل بعد مراجعة رئيس التحرير.

### 22.3 المسار C: Newsroom Productivity

**الهدف:** تقليل زمن الانتقال من `candidate` إلى `ready_for_manual_publish`.

**التنفيذ:**

1. قوالب Smart Editor حسب نوع الخبر:
   - عاجل
   - تحليل
   - رياضة
   - اقتصاد
2. Checklist حي داخل المحرر مرتبط مباشرة بالبوابات (أخضر/أحمر).
3. Story Mode:
   - clustering تلقائي للمواد المتشابهة
   - `Story Workspace` مع timeline + sources + entities
4. دمج Audience Simulator داخل المحرر كـpanel:
   - توقع التفاعل
   - مخاطر سوء الفهم
   - عناوين بديلة

**KPIs:**

- انخفاض `time_to_ready_for_manual_publish`.
- انخفاض عدد الدورات بين الصحفي ورئيس التحرير.
- انخفاض التكرار في التغطية لنفس القصة.

### 22.4 المسار D: Reliability + Cost Control

**الهدف:** ثبات أعلى وتكلفة متوقعة تحت الضغط.

**التنفيذ:**

1. تعريف SLA لكل queue:
   - max latency
   - max depth
   - alert thresholds
2. Throttling/backpressure مضبوط حسب job type.
3. Provider routing واعي بالتكلفة:
   - task type
   - urgency
   - daily/weekly budget cap
4. Jobs Health dashboard:
   - retries
   - DLQ count
   - mean runtime
   - top failure causes
5. traceability كاملة:
   - `request_id` + `correlation_id` عبر API/worker/logs

**KPIs:**

- استقرار queue depth ضمن الحدود.
- انخفاض DLQ growth rate.
- انحراف تكلفة يومية أقل من الحد المتفق عليه.

### 22.5 خطة التسليم الزمنية (12 أسبوع)

1. **الأسبوع 1-2**
   - Time Integrity dashboard
   - auto-cleaner
   - source health basics
2. **الأسبوع 3-6**
   - Gates 2.0
   - claims extraction
   - support links enforcement
3. **الأسبوع 7-10**
   - Story clustering
   - editor templates
   - integrated checklist
4. **الأسبوع 11-12**
   - queue SLA
   - cost-aware provider routing
   - DLQ workflows

### 22.6 DoD لكل مرحلة

1. مرحلة Time Integrity:
   - لا عنصر قديم في newsroom النشطة.
2. مرحلة Gates 2.0:
   - انخفاض رفض رئيس التحرير بسبب اكتشاف مبكر للأسباب.
3. مرحلة Productivity:
   - انخفاض واضح في زمن التحرير.
4. مرحلة Reliability/Cost:
   - طوابير مستقرة + تكلفة متوقعة.
