# الملف التعريفي الشامل للمشروع

تاريخ التحديث: 2026-02-25  
اسم المشروع: `Echorouk Editorial OS`  
نوع المشروع: منصة تشغيل تحريري ذكية (Newsroom Operating System)

## 1) الملخص التنفيذي
`Echorouk Editorial OS` هي منصة مؤسسية لإدارة دورة حياة الخبر من الالتقاط إلى الجاهزية للنشر اليدوي، مع:
- حوكمة تحريرية صارمة.
- نموذج Human-in-the-Loop إلزامي.
- تشغيل متزامن/غير متزامن عبر API + Queue.
- دعم متعدد الوحدات: التحرير الذكي، التراند، تحليل الوثائق، Fact-check، SEO، Multimedia، MSI، Memory.

الهدف التشغيلي الأساسي:
- تسريع غرفة الأخبار.
- رفع جودة القرار التحريري.
- تقليل الضجيج الإخباري.
- توحيد تدفق العمل داخل منصة واحدة.

## 2) حدود النظام (Scope)
ما يقوم به النظام:
- جمع الأخبار من مصادر RSS/FreshRSS/RSS-Bridge.
- تصنيف وترتيب الأولوية.
- إنشاء مسودات تحريرية ذكية.
- تدقيق الجودة والادعاءات والجاهزية.
- إدارة الاعتماد النهائي.
- تقديم أدوات صحفية مساعدة (SEO/Fact-check/Multimedia/Document Intelligence).

ما لا يقوم به مباشرة:
- النشر النهائي يتم يدويًا خارج النظام (workflow ينتهي عند `ready_for_manual_publish`).

## 3) المكدس التقني (Tech Stack)
## Backend
- Python 3.11+
- FastAPI
- SQLAlchemy + Alembic
- PostgreSQL (مع `pgvector`)
- Redis
- Celery + Flower
- Structlog

## Frontend
- Next.js 16
- React 19
- TypeScript
- Tailwind CSS 4
- React Query
- Axios

## AI/Integrations
- Gemini
- Groq
- YouTube Data API (للتراند)
- FreshRSS + RSS-Bridge
- Tesseract / OCR (في Document Intelligence)
- Docling (اختياري حسب البناء)

## 4) هيكل المستودع
- `backend/`: منطق النظام + API + queue + models.
- `frontend/`: لوحة المنصة والصفحات التشغيلية.
- `alembic/`: migrations.
- `scripts/`: تهيئة/seed وتشغيل مساعد.
- `docs/`: وثائق تشغيلية وتقنية.
- `docker-compose.yml`: تعريف بيئة التشغيل الكاملة.
- `.env.example`: مرجع الإعدادات.

## 5) الخدمات (Docker Services) والبوابات
من `docker-compose.yml`:
- `backend`: API.
- `worker`: تنفيذ مهام Celery.
- `flower`: مراقبة المهام.
- `frontend`: واجهة المنصة.
- `postgres`: قاعدة البيانات.
- `redis`: cache + queue broker/result.
- `minio`: تخزين كائنات.
- `freshrss-db`: قاعدة FreshRSS.
- `freshrss`: مجمع RSS.
- `rssbridge`: تحويل مصادر غير RSS.

بوابات شائعة:
- Backend: `8000`
- Frontend: `3000`
- Postgres host-mapped: `5433`
- Redis host-mapped: `6380`
- Flower: `5555`
- MinIO: `9000/9001`
- FreshRSS: `8082`
- RSS-Bridge: `8083`

## 6) دورة الخبر (Pipeline Lifecycle)
الحالات الرئيسية (من `backend/app/models/news.py`):
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

التدفق العملي:
1. Scout يجلب ويزيل التكرارات.
2. Router يصنف ويعطي أولوية.
3. Editorial workspace ينشئ/يعدّل المسودات.
4. فحوصات الجودة/الادعاءات/SEO.
5. اعتماد رئيس التحرير.
6. تجهيز للنشر اليدوي.

## 7) الوكلاء والوظائف الأساسية
من `backend/app/agents/`:
- `scout.py`: ingestion + dedup.
- `router.py`: تصنيف/أولوية/توجيه.
- `scribe.py`: توليد/صياغة.
- `trend_radar.py`: رصد الترندات.
- `published_monitor.py`: جودة المحتوى المنشور.
- `audio_agent.py`: مهام صوتية.

## 8) المنظومة غير المتزامنة (Queue Architecture)
صفوف Celery الأساسية:
- `ai_router`
- `ai_scribe`
- `ai_quality`
- `ai_simulator`
- `ai_msi`
- `ai_links`
- `ai_trends`

تعريف المهام الأساسية في:
- `backend/app/queue/tasks/pipeline_tasks.py`

## 9) الجدولة الدورية (Periodic Loops)
من `backend/app/main.py`:
- Loop للـ pipeline.
- Loop للـ trends.
- Loop للـ published monitor.
- Loop للـ competitor xray.

الوضع الحالي الافتراضي للتراند:
- `trend_radar_interval_minutes = 120` (كل ساعتين) من `backend/app/core/config.py`.
- auto trends job يعمل على `geo=ALL` لتوليد snapshot شامل.

## 10) وحدات API (Route Map)
جميعها تحت prefix: `/api/v1`  
تعريف الربط موجود في `backend/app/main.py`.

الوحدات:
- `/auth`
- `/news`
- `/sources`
- `/editorial`
- `/dashboard`
- `/rss`
- `/settings`
- `/constitution`
- `/services` (journalist services)
- `/memory`
- `/msi`
- `/sim`
- `/media-logger`
- `/document-intel`
- `/competitor-xray`
- `/jobs`

مسارات النظام العامة:
- `GET /health`
- `GET /`

## 11) الصلاحيات والأدوار (RBAC)
الأدوار من `backend/app/models/user.py`:
- `director`
- `editor_chief`
- `journalist`
- `social_media`
- `print_editor`

الأقسام (Departments) مدعومة لكل مستخدم.

## 12) الواجهة الأمامية (Frontend Surface)
صفحات التشغيل الأساسية في `frontend/src/app/`:
- `dashboard`
- `news`
- `editorial`
- `workspace-drafts`
- `sources`
- `settings`
- `agents`
- `trends`
- `memory`
- `msi`
- `simulator`
- `competitor-xray`
- `team`
- `constitution`
- `services/*`:
  - `document-intel`
  - `editor`
  - `fact-check`
  - `media-logger`
  - `multimedia`
  - `seo`

## 13) التراند (الوضع التشغيلي الحالي)
الحالة المطبقة حاليًا:
- مسح شامل بضغط واحدة (`geo=ALL`).
- snapshot مجمع في cache.
- تصفية محلية حسب الجغرافيا/التصنيف بدون إعادة scan لكل خيار.
- تحديث تلقائي كل ساعتين.
- تحسين quality filter للكلمات لتقليل الكلمات الاعتباطية.
- دعم YouTube Trends عبر API Key من الإعدادات.

ملفات رئيسية:
- `backend/app/agents/trend_radar.py`
- `backend/app/api/routes/dashboard.py`
- `frontend/src/app/trends/page.tsx`
- `frontend/src/lib/api.ts`

## 14) ذكاء الوثائق (Document Intelligence)
الوحدة:
- `/api/v1/document-intel/extract`
- `/api/v1/document-intel/extract/submit`
- `/api/v1/document-intel/extract/{job_id}`

المنهج:
- محاولة Docling (إن كان متاحًا).
- fallback إلى parsers بديلة.
- OCR عبر Tesseract حسب الشروط/الإعدادات.
- استخراج:
  - مرشحات أخبار.
  - نقاط رقمية/بيانية.
  - preview_text.

## 15) الإعدادات الحرجة (Critical Configuration)
أمثلة مهمة:
- `ECHOROUK_OS_GEMINI_API_KEY`
- `ECHOROUK_OS_GROQ_API_KEY`
- `ECHOROUK_OS_YOUTUBE_DATA_API_KEY`
- `ECHOROUK_OS_YOUTUBE_TRENDS_ENABLED`
- `ECHOROUK_OS_TREND_RADAR_INTERVAL_MINUTES`
- `ECHOROUK_OS_DOCUMENT_INTEL_*`
- إعدادات DB/Redis/Queue
- إعدادات FreshRSS/RSSBridge

المرجع الكامل:
- `.env.example`
- `backend/app/core/config.py`

## 16) المراقبة والتتبّع (Observability)
- structured logs عبر `structlog`.
- `request_id` و `correlation_id`.
- جداول تشغيل ومهام:
  - `pipeline_runs`
  - `failed_jobs`
  - `job_runs` (من نموذج queue)
- Dashboard endpoints:
  - `/dashboard/stats`
  - `/dashboard/pipeline-runs`
  - `/dashboard/failed-jobs`
  - `/jobs/*`

## 17) قاعدة البيانات (Domain Models الرئيسية)
ملفات النماذج في `backend/app/models/` تشمل:
- `news.py`
- `job_queue.py`
- `quality.py`
- `settings.py`
- `project_memory.py`
- `msi.py`
- `simulator.py`
- `competitor_xray.py`
- `media_logger.py`
- `knowledge.py`
- `link_intelligence.py`
- `user.py`
- `user_activity.py`
- `constitution.py`
- `audit.py`

## 18) الأمان والتشغيل
- لا مفاتيح hardcoded.
- الاعتماد على env/config store.
- صلاحيات مبنية على الدور.
- حماية endpoint حسب الدور.
- fallback في حال فشل مزود AI.
- backpressure على الطوابير.

## 19) أسلوب النشر المعتمد (Git وسيط)
السير العملي الموصى به:
1. تعديل محلي (PowerShell).
2. `git add/commit/push`.
3. على السيرفر: `git pull`.
4. `docker compose build`.
5. `docker compose up -d --force-recreate`.
6. اختبارات API بعد النشر.

هذا يحافظ على consistency بين المحلي والسيرفر ويمنع drift.

## 20) أوامر تشغيل وصيانة سريعة
- تحقق الحالة:
  - `docker compose ps`
  - `curl http://127.0.0.1:8000/health`
- مراقبة backend:
  - `docker logs ech-backend --since 10m | tail -n 200`
- اختبار auth:
  - `POST /api/v1/auth/login`
- اختبار trends:
  - `POST /api/v1/dashboard/agents/trends/scan?geo=ALL&category=all`
  - `GET /api/v1/dashboard/agents/trends/latest?geo=ALL&category=all`
- اختبار document-intel:
  - `POST /api/v1/document-intel/extract` مع ملف `-F file=@...pdf`

## 21) المخاطر/النقاط المفتوحة
- جودة التراند تعتمد على جودة المصادر الخارجية وإشارات التحقق.
- OCR للـ PDF الثقيل قد يحتاج tuning حسب نوع الوثائق الرسمية.
- يجب مراقبة timeouts لمهام الذكاء والوثائق في الإنتاج.
- أي تغيير في `.env` يحتاج إعادة إنشاء الخدمة المعنية.

## 22) الوثائق المرجعية داخل المشروع
- `README.md`
- `docs/architecture.md`
- `docs/agents.md`
- `docs/M10_ASYNC_ARCHITECTURE.md`
- `docs/M5_SMART_EDITOR.md`
- `docs/DOCUMENT_INTEL_ROLLOUT.md`
- `docs/YOUTUBE_TRENDS_ROLLOUT.md`
- `docs/TROUBLESHOOTING_PLAYBOOK.md`
- `docs/OPERATIONS_QUICK_COMMANDS.md`

---

هذا الملف يمثل Snapshot تشغيلي/تقني شامل للمشروع.  
يفضل تحديثه بعد كل milestone كبيرة أو تعديل معماري.
