# EXPERIMENT SMOKE TEST PLAN — خطة التجربة النهائية

## 1) المتطلبات قبل البدء
- تشغيل الحاويات:
  - `docker compose up -d --build`
- تطبيق المايغريشن:
  - `docker compose run --rm backend alembic upgrade head`
- التحقق من الصحة:
  - `curl -sS http://127.0.0.1:8000/health`

## 2) Smoke سريع (API)
1. تسجيل الدخول:
   - `POST /api/v1/auth/login`
2. إحصائيات:
   - `GET /api/v1/dashboard/stats`
3. تنبيهات:
   - `GET /api/v1/dashboard/notifications?limit=20`
4. قائمة الأخبار:
   - `GET /api/v1/news/?page=1&per_page=20`
5. الدستور:
   - `GET /api/v1/constitution/latest`
   - `GET /api/v1/constitution/tips`

## 3) سيناريو الصحفي (E2E)
1. فتح خبر من `/news`.
2. تنفيذ handoff إلى مساحة المسودات.
3. التعديل اليدوي + autosave.
4. تشغيل أدوات AI:
   - تحسين صياغة
   - توليد عناوين
   - توليد SEO
   - تحقق الادعاءات
   - تقييم الجودة
5. التأكد أن النتائج تظهر كنص واضح (بدون HTML خام).
6. إرسال `submit-for-chief-approval`.

معيار نجاح:
- لا أخطاء 500.
- تظهر حالة الخبر في مسار الاعتماد.

## 4) سيناريو رئيس التحرير
1. فتح `editorial/chief/pending`.
2. مراجعة ملاحظات السياسة التحريرية/الجودة/التحقق.
3. اعتماد نهائي أو إرجاع للمراجعة.

معيار نجاح:
- عند الاعتماد: حالة الخبر `ready_for_manual_publish`.
- عند الإرجاع: يعود لطابور التحرير.

## 5) سيناريو السوشيال ميديا
1. فتح feed المعتمد:
   - `GET /api/v1/editorial/social/approved-feed`
2. نسخ نسخة Facebook/X/Push من الخبر المعتمد.

معيار نجاح:
- لا تظهر أخبار غير معتمدة.
- النسخ جاهزة Copy/Paste.

## 6) سيناريو المدير
1. إدارة المستخدمين:
   - إضافة مستخدم.
   - تعديل صلاحياته.
   - مراجعة activity logs.
2. مراجعة إعدادات API.
3. مراجعة `/dashboard/agents/status` و `/dashboard/pipeline-runs`.

معيار نجاح:
- CRUD العضوية يعمل.
- سجل النشاط يظهر العمليات الحرجة.

## 7) فحص العاجل
1. تشغيل الموجه:
   - `POST /api/v1/dashboard/agents/router/run`
2. مراقبة اللوج:
   - `docker logs ech-backend --since 10m | egrep -i "router_batch_complete|telegram_sent|breaking"`
3. التأكد أن الخبر العاجل يظهر في:
   - `dashboard/notifications`
   - قناة Telegram المخصصة.

## 8) نتيجة التجربة
سجّل لكل سيناريو:
- `PASS` أو `FAIL`
- وقت التنفيذ
- رابط/معرّف الخبر
- لقطة الخطأ (إن وجدت)
- مرجع الحل من `TROUBLESHOOTING_PLAYBOOK.md`
