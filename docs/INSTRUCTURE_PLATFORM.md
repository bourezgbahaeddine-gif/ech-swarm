# INSTRUCTURE — مرجع منصة Echorouk AI Swarm

## 1) الهدف
هذا الملف هو المرجع التشغيلي والتقني والتحريري للمنصة. الهدف من المنصة:
- إدارة دورة الخبر من الالتقاط حتى **جاهز للنشر اليدوي**.
- فرض حوكمة تحريرية قبل الاعتماد النهائي.
- إبقاء النشر النهائي يدويًا 100%.

## 2) الحالة التشغيلية الحالية (تدقيق الوكيل المراقب)
تاريخ التدقيق: 2026-02-18

### ما تم اختباره فعليًا
- Backend unit tests:
  - الأمر: `\.venv\Scripts\python.exe -m pytest backend/tests -q`
  - النتيجة: **20 passed**
- Backend compile check:
  - الأمر: `\.venv\Scripts\python.exe -m compileall backend/app`
  - النتيجة: **pass**
- Frontend type check:
  - الأمر: `npx tsc --noEmit` داخل `frontend`
  - النتيجة: **pass**
- Frontend production build:
  - الأمر: `npm run build` داخل `frontend`
  - النتيجة: **pass**
- Frontend lint (فحص جودة الكود العام):
  - الأمر: `npm run lint`
  - النتيجة: **fails** (تفاصيل في قسم الأخطاء)

### عوائق منعت E2E كامل
- Docker daemon غير متاح محليًا:
  - خطأ: `dockerDesktopLinuxEngine pipe not found`
- Backend غير قابل للتشغيل مباشرة من `.venv` الحالي بسبب نقص تبعيات runtime (مثل `fastapi`).
- نتيجة ذلك: تم تنفيذ تدقيق شامل على مستوى build/type/tests + مراجعة مسارات الواجهة والكود، لكن ليس اختبار E2E حيّ عبر خادم شغال محليًا.

## 3) البنية التقنية

### Backend
- إطار العمل: `FastAPI`
- قاعدة البيانات: `PostgreSQL` (+ `pgvector`)
- Redis: للكاش/المهام الدورية
- ملفات المسارات الأساسية:
  - `backend/app/api/routes/auth.py`
  - `backend/app/api/routes/news.py`
  - `backend/app/api/routes/editorial.py`
  - `backend/app/api/routes/dashboard.py`
  - `backend/app/api/routes/constitution.py`
  - `backend/app/api/routes/journalist_services.py`
  - `backend/app/api/routes/settings.py`
  - `backend/app/api/routes/sources.py`
  - `backend/app/api/routes/rss.py`
- التسجيل في التطبيق: `backend/app/main.py`

### Frontend
- إطار العمل: `Next.js (App Router)`
- إدارة الاستعلامات: `@tanstack/react-query`
- المحرر الذكي: `TipTap`
- صفحات رئيسية:
  - `/` لوحة القيادة
  - `/news` و `/news/[id]`
  - `/workspace-drafts`
  - `/editorial`
  - `/constitution`
  - `/trends`
  - `/services/multimedia`
  - `/dashboard/metric/[metric]`

## 4) دورة الخبر الذكية (المعتمدة)
1. الالتقاط والتصنيف (Scout/Router/Cluster).
2. انتقال الخبر إلى `candidate`.
3. الصحفي يرشّح/يحرّر حتى النسخة الأخيرة في Smart Editor.
4. تشغيل بوابات: التحقق من الادعاءات + الجودة + SEO/Tech + readability.
5. المرور على **وكيل السياسة التحريرية للشروق**.
6. إرسال التنبيه إلى رئيس التحرير مع حالة:
   - مقبول من الوكيل، أو
   - طلب اعتماد مع تحفظات.
7. رئيس التحرير يعتمد أو يعيد للمراجعة.
8. عند الاعتماد النهائي: `ready_for_manual_publish` + Final Package كامل.
9. النشر يتم يدويًا خارج النظام.

## 5) الأدوار والصلاحيات

### الصحفي / محرر الجريدة
- متابعة الأخبار المرشحة.
- ترشيح الخبر.
- التحرير حتى النسخة الأخيرة.
- استخدام أدوات المحرر الذكي (تحسين/تحقق/SEO/جودة/سوشيال).
- لا يملك اعتمادًا نهائيًا ولا إعدادات API.

### رئيس التحرير
- طابور اعتماد نهائي.
- الاطلاع على تقارير السياسة التحريرية، التحقق، الجودة.
- قرار: اعتماد أو إرجاع للمراجعة.

### المدير
- كل الصلاحيات + إعدادات API + مراقبة النظام + الحوكمة.
- تحكم كامل في العضوية:
  - إضافة أعضاء جدد.
  - تعديل الدور/الأقسام/الحالة.
  - إعادة تعيين كلمة المرور.
  - مراجعة سجل نشاط كل عضو.

### السوشيال ميديا
- الاطلاع على الأخبار المعتمدة فقط.
- نسخ مخرجات السوشيال الجاهزة (Copy/Paste) من الخبر المعتمد.
- بدون تعديل النص التحريري الأصلي.

## 6) Final Package (مخرجات ما قبل النشر اليدوي)
- عنوان رئيسي + بديل.
- متن الخبر النهائي.
- SEO title + meta description + tags + keywords + slug.
- تقرير جودة.
- تقرير تحقق/claims.
- مصادر وأدلة.
- نسخ سوشيال (Facebook/X/Push/Breaking).
- حالة نهائية: `Ready for Manual Publish`.

## 7) نقاط الواجهة المهمة
- توحيد اللغة العربية في الشاشات والنتائج.
- Onboarding:
  - نافذة أول دخول.
  - شرح أول ضغطة للأزرار الحساسة.
  - أيقونة دليل ثابتة.
- Smart Editor:
  - Autosave.
  - Versioning + Diff + Restore.
  - اقتراحات AI بصيغة Suggestion فقط.

## 8) ملاحظات تدقيق فعلية (أخطاء/مخاطر مكتشفة)

### حرجة (تمنع جاهزية إطلاق نظيف)
1. فشل lint على الواجهة (`npm run lint`).
   - أخطاء `no-explicit-any` في ملفات منها:
     - `frontend/src/components/dashboard/AgentControl.tsx`
     - `frontend/src/app/agents/page.tsx`
     - `frontend/src/app/login/page.tsx`
     - `frontend/src/app/team/page.tsx`
   - أخطاء React Hook rule (`set-state-in-effect`) في:
     - `frontend/src/components/layout/AppShell.tsx`
     - `frontend/src/lib/auth.tsx`
2. بيئة التشغيل المحلية غير مكتملة لـ backend عبر venv (runtime deps ناقصة مثل `fastapi`).
3. Docker daemon غير شغال محليًا، وهذا يمنع اختبار E2E الحي.

### متوسطة
1. صفحة تسجيل الدخول ما زالت تحتوي رابط Word للدستور:
   - `frontend/src/app/login/page.tsx` يشير إلى `/Constitution.docx`.
2. عرض “الفرق التقني” في المحرر قد يطبع HTML خام عند وجود `diff_html`:
   - `frontend/src/app/workspace-drafts/page.tsx`.
3. قسم preview للتحسين في بعض الحالات قصير/مقتطع ويصعب القراءة للنسخ الطويلة:
   - `frontend/src/app/workspace-drafts/page.tsx`.

### منخفضة
- تحذيرات lint إضافية (`unused vars`, `<img>` بدل `next/image`) لا تمنع البناء لكنها تؤثر الجودة.

## 9) الأمن والحوكمة
- RBAC مفعل في API لمسارات حساسة.
- إعدادات API مخصصة للمدير.
- لا نشر نهائي تلقائي.
- بوابات منع قبل `ready_for_manual_publish`.

## 10) مراقبة التشغيل (Runbook مختصر)

### قبل الإطلاق
1. تأكد من تشغيل Docker.
2. طبّق migration.
3. شغّل backend/frontend.
4. نفّذ smoke flows لكل دور.

### أوامر تحقق أساسية
- Backend tests:
  - `\.venv\Scripts\python.exe -m pytest backend/tests -q`
- Frontend typecheck:
  - `cd frontend && npx tsc --noEmit`
- Frontend build:
  - `cd frontend && npm run build`
- Backend health (عند تشغيل السيرفر):
  - `curl.exe -sS http://127.0.0.1:8000/health`

### Membership APIs (المدير)
- `GET /api/v1/auth/users`
- `POST /api/v1/auth/users`
- `PUT /api/v1/auth/users/{user_id}`
- `GET /api/v1/auth/users/{user_id}/activity`

## 11) خارطة التحسين التالية (موصى بها قبل Go-Live)
1. إغلاق أخطاء lint الحرجة.
2. إزالة رابط Word نهائيًا من صفحة الدخول واستبداله برابط صفحة `/constitution`.
3. تنسيق `diff_html` إلى نص مفهوم للصحفي بدل العرض الخام.
4. تحسين مساحة/خط عرض النسخة المحسنة في المحرر.
5. تنفيذ E2E حي بعد تشغيل Docker + backend runtime dependencies.

---
هذا المرجع يجب تحديثه مع كل تغييرات هيكلية (Routes/Workflow/RBAC/Policy gates).
