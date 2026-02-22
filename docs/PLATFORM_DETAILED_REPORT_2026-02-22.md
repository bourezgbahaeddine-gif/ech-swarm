# التقرير التفصيلي للمنصة — Echorouk Editorial OS

Echorouk Editorial OS is an enterprise operating system for managing editorial content lifecycle from capture to manual-publish readiness, with strict governance and mandatory Human-in-the-Loop.

تاريخ الإصدار: 22 فبراير 2026
الحالة: تشغيلي (Operational)

## 1) الملخص التنفيذي
منصة Echorouk Editorial OS هي نظام غرفة تحرير ذكية لإدارة دورة الخبر من الالتقاط إلى حالة **Ready for Manual Publish** مع:
- حوكمة تحريرية قبل الاعتماد.
- صلاحيات مبنية على الدور (RBAC).
- أدوات ذكاء اصطناعي مساعدة داخل سير العمل التحريري.
- بقاء النشر النهائي يدويًا 100%.

## 2) الهدف التشغيلي
- تسريع إنتاج الخبر دون التضحية بالجودة.
- توحيد سير العمل داخل غرفة الأخبار.
- تقليل الأخطاء التحريرية والادعاءات غير الموثقة.
- تجهيز حزمة نهائية متكاملة للنشر اليدوي.

## 3) المعمارية التقنية
## Frontend
- Next.js (App Router).
- صفحات تشغيلية حسب الدور (أخبار، تحرير، مسودات، MSI، محاكي الجمهور، خدمات الصحفي، إلخ).
- عميل API مركزي في `frontend/src/lib/api.ts`.

## Backend
- FastAPI في `backend/app/main.py`.
- مسارات API في `backend/app/api/routes`.
- منطق الخدمات في `backend/app/services`.
- وكلاء وتحليلات متقدمة في:
  - `backend/app/agents`
  - `backend/app/msi`
  - `backend/app/simulator`

## البيانات والبنية التحتية
- PostgreSQL + Alembic migrations.
- Redis للكاش والمهام الدورية.
- Docker Compose لخدمات التشغيل:
  - backend, frontend, postgres, redis, minio, freshrss, rssbridge, freshrss-db.

## 4) دورة الخبر (العملية المعتمدة)
1. التقاط الأخبار (Scout).
2. التصنيف والتوجيه والأولوية (Router).
3. إنشاء مسودة أولية (Scribe).
4. تحرير الصحفي داخل Smart Editor.
5. تشغيل التحقق والجودة وSEO.
6. المرور على سياسة التحرير.
7. قرار رئيس التحرير (اعتماد/إرجاع).
8. الانتقال إلى `ready_for_manual_publish`.
9. النشر يتم يدويًا خارج النظام.

## 5) الصلاحيات حسب الدور
## الصحفي
- متابعة المرشحات، التحرير، أدوات الذكاء داخل المسودة.

## رئيس التحرير
- اعتماد نهائي أو إرجاع للمراجعة.

## المدير
- تحكم شامل: إعدادات، مراقبة، أعضاء، سجل النشاط.

## السوشيال ميديا
- الوصول إلى المخرجات المعتمدة والنسخ الجاهزة.

## 6) الوحدات الأساسية المنفذة
## M5 — Smart Editor
- تحرير + autosave + versions + diff + restore.
- أدوات rewrite/headline/seo/social/quality/claims.

## Project Memory
- حفظ معرفة تشغيلية/تحريرية مسترجعة عبر API.

## MSI Monitor
- مؤشر يومي/أسبوعي لاستقرار التغطية الإعلامية.
- تخزين runs/reports/timeseries + watchlist.

## محاكي الجمهور (Audience Simulation)
- تقييم مخاطر/انتشار قبل النشر.
- إخراج منظم: درجات + red flags + نصائح تحريرية.

## Media Logger
- تفريغ صوت/فيديو (URL أو Upload) + استخراج highlights + Q&A.

## Competitor X-Ray
- رصد تغطية المنافسين واقتراح زاوية تفوق.

## M8 — Link Intelligence
- اقتراح روابط داخلية/خارجية للمسودة.
- فهرسة + توصية + تحقق + تطبيق على HTML.

## 7) نموذج البيانات (Core Tables)
أهم الجداول التشغيلية:
- `articles`
- `sources`
- `editorial_drafts`
- `article_quality_reports`
- `user_activity_logs`
- `project_memory_items` (حسب نموذج الذاكرة)
- `msi_*` (runs/reports/timeseries/watchlist/events)
- `sim_*` (runs/results/feedback/events)
- `media_logger_*`
- `link_*` (index/recommendation/click events)

## 8) المخرجات النهائية قبل النشر اليدوي
- عنوان رئيسي + بديل.
- متن نهائي.
- SEO title + meta description + tags + keywords + slug.
- تقرير جودة.
- تقرير تحقق/claims.
- مصادر وأدلة.
- نسخ سوشيال جاهزة.
- حالة واضحة: `Ready for Manual Publish`.

## 9) الحالة التشغيلية الحالية (22-02-2026)
- النظام يعمل مع استجابات API ناجحة.
- تم رصد بطء متقطع سببه تزامن:
  - polling واجهة مكثف.
  - وظائف دورية ثقيلة في الخلفية.
- يوجد fallback من Groq إلى Gemini بسبب نموذج Groq متقاعد، ما يضيف تأخيرًا لكنه لا يوقف الخدمة.

## 10) المخاطر التشغيلية الحالية
- ارتفاع latency عند ضغط متزامن بين loops الخلفية واستعلامات الواجهة.
- اعتماد fallback لنموذج Groq متوقف.
- الحاجة إلى ضبط إضافي لجودة اقتراح الروابط الخارجية حسب corpus.

## 11) توصيات التحسين (أولوية تنفيذ)
1. تحديث/تعطيل نموذج Groq المتقاعد لتقليل زمن الاستجابة.
2. تخفيف polling في الواجهة واعتماد SSE عند الإمكان.
3. تشغيل الخدمات الثقيلة بإيقاع متدرج (staged enablement).
4. تحسين scoring للروابط الخارجية مع تغذية domains موثوقة إضافية.
5. ضبط مؤشرات أداء تشغيلية (p95 latency, error rate, queue lag).

## 12) مؤشر النضج الحالي
- **تشغيلي ومناسب للتجربة التحريرية الواقعية**.
- قابل للتوسع والتحسين التدريجي دون كسر سير العمل.

## 13) مرجع الملفات
- البنية العامة: `docs/PLATFORM_CONTENT_MAP.md`
- التشغيل السريع: `docs/OPERATIONS_QUICK_COMMANDS.md`
- استكشاف الأعطال: `docs/TROUBLESHOOTING_PLAYBOOK.md`
- المحرر الذكي: `docs/M5_SMART_EDITOR.md`
- محاكي الجمهور: `docs/M7_AUDIENCE_SIMULATOR.md`
- الروابط الذكية: `docs/M8_LINK_INTELLIGENCE.md`
- مرجع المنصة الأساسي: `docs/INSTRUCTURE_PLATFORM.md`
