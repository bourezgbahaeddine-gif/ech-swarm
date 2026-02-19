# PLATFORM CONTENT MAP — الخريطة الكاملة للمنصة

## 1) الهدف التشغيلي
المنصة تدير دورة الخبر من الالتقاط حتى **جاهز للنشر اليدوي** مع حوكمة تحريرية صارمة.

## 2) خريطة المجلدات
- `backend/`
  - `app/agents/`: منطق الوكلاء (Scout / Router / Scribe / Trend Radar).
  - `app/api/routes/`: واجهات REST الأساسية.
  - `app/models/`: نماذج قاعدة البيانات وحالات الخبر.
  - `app/services/`: خدمات الذكاء، التنبيهات، الإعدادات، المحرر الذكي.
  - `app/main.py`: تجميع التطبيق + المهام الدورية.
- `frontend/`
  - `src/app/`: صفحات المنصة.
  - `src/components/`: واجهات مشتركة (Sidebar, TopBar, Dashboard widgets).
  - `src/lib/`: API client + auth state + utils.
- `alembic/versions/`: migrations قاعدة البيانات.
- `docs/`: مرجع التشغيل والتجربة.

## 3) خريطة API (مختصرة)
### المصادقة والعضوية
- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`
- `GET /api/v1/auth/users` (مدير)
- `POST /api/v1/auth/users` (مدير)
- `PUT /api/v1/auth/users/{user_id}` (مدير)
- `GET /api/v1/auth/users/{user_id}/activity` (مدير)

### الأخبار
- `GET /api/v1/news/`
- `GET /api/v1/news/breaking/latest`
- `GET /api/v1/news/{article_id}`
- `GET /api/v1/news/{article_id}/related`
- `GET /api/v1/news/{article_id}/cluster`

### التحرير والمحرر الذكي
- `POST /api/v1/editorial/{article_id}/handoff`
- `POST /api/v1/editorial/workspace/manual-drafts`
- `GET /api/v1/editorial/workspace/drafts`
- `GET /api/v1/editorial/workspace/drafts/{work_id}/context`
- `POST /api/v1/editorial/workspace/drafts/{work_id}/autosave`
- `POST /api/v1/editorial/workspace/drafts/{work_id}/ai/rewrite`
- `POST /api/v1/editorial/workspace/drafts/{work_id}/ai/headlines`
- `POST /api/v1/editorial/workspace/drafts/{work_id}/ai/seo`
- `POST /api/v1/editorial/workspace/drafts/{work_id}/ai/social`
- `POST /api/v1/editorial/workspace/drafts/{work_id}/verify/claims`
- `POST /api/v1/editorial/workspace/drafts/{work_id}/quality/score`
- `GET /api/v1/editorial/workspace/drafts/{work_id}/publish-readiness`
- `POST /api/v1/editorial/workspace/drafts/{work_id}/submit-for-chief-approval`
- `GET /api/v1/editorial/chief/pending`
- `POST /api/v1/editorial/{article_id}/chief/final-decision`

### الجودة للمقال
- `POST /api/v1/editorial/{article_id}/quality/readability`
- `POST /api/v1/editorial/{article_id}/quality/technical`
- `POST /api/v1/editorial/{article_id}/quality/guardian`
- `GET /api/v1/editorial/{article_id}/quality/reports`

### المراقبة والتنبيهات
- `GET /api/v1/dashboard/stats`
- `GET /api/v1/dashboard/notifications`
- `POST /api/v1/dashboard/agents/scout/run`
- `POST /api/v1/dashboard/agents/router/run`
- `POST /api/v1/dashboard/agents/trends/scan`
- `GET /api/v1/dashboard/agents/trends/latest`

### الدستور التحريري
- `GET /api/v1/constitution/latest`
- `GET /api/v1/constitution/guide`
- `GET /api/v1/constitution/tips`
- `GET /api/v1/constitution/ack`
- `POST /api/v1/constitution/ack`

## 4) خريطة الواجهة حسب الدور
### الصحفي
- يرى: `news`, `editorial`, `workspace-drafts`, `trends`, `constitution`, `services/multimedia`, `services/fact-check`.
- لا يرى: `settings`, `sources`, `agents`, `team`.

### رئيس التحرير
- يرى: كل ما يخص الصحفي + طابور الاعتماد النهائي + المتابعة التحريرية.

### المدير
- يرى كل الصفحات + إعدادات API + إدارة العضوية + مراقبة النظام.

### السوشيال ميديا
- يرى الأخبار المعتمدة والنسخ الاجتماعية الجاهزة + الوسائط.

## 5) دورة الخبر المعتمدة
1. `NEW` -> `CLASSIFIED` عبر Scout/Router.
2. الخبر المهم يصبح `CANDIDATE`.
3. الصحفي يحرر عبر Smart Editor حتى النسخة النهائية.
4. تشغيل quality/claims/SEO/policy checks.
5. إرسال طلب الاعتماد لرئيس التحرير.
6. قرار رئيس التحرير:
   - قبول نهائي -> `READY_FOR_MANUAL_PUBLISH`
   - إرجاع للمراجعة.
7. النشر يتم يدويًا خارج النظام.

## 6) الجداول الجوهرية
- `articles`
- `sources`
- `editorial_drafts`
- `editor_decisions`
- `article_quality_reports`
- `pipeline_runs`
- `failed_jobs`
- `settings_audit_logs`
- `user_activity_logs`

## 7) التكاملات الخارجية
- Gemini (تحليل/توليد/تحسين).
- Telegram (العاجل).
- Slack (تنبيهات الفريق).
- Redis (كاش + نتائج trends).
- FreshRSS/RSSBridge (تغذية المصادر).

## 8) M7 Additions - ????? ???????
### Frontend
- `/simulator`
- Smart Editor action: `????? ???????`

### API
- `POST /api/v1/sim/run`
- `GET /api/v1/sim/runs/{run_id}`
- `GET /api/v1/sim/result?run_id=...`
- `GET /api/v1/sim/history`
- `GET /api/v1/sim/live?run_id=...` (SSE)

### Core backend files
- `backend/app/models/simulator.py`
- `backend/app/simulator/state.py`
- `backend/app/simulator/nodes.py`
- `backend/app/simulator/graph.py`
- `backend/app/simulator/service.py`
- `backend/app/api/routes/simulator.py`
- `backend/app/schemas/simulator.py`
- `backend/app/simulator/profiles/personas_dz_v1.json`

### DB tables
- `sim_runs`
- `sim_results`
- `sim_feedback`
- `sim_calibration`
- `sim_job_events`
