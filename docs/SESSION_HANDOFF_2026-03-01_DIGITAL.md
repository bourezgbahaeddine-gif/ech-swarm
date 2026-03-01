# Session Handoff - 2026-03-01 (Digital Team)

## الهدف في هذه الجلسة
- تحويل وحدة فريق الديجيتال من تنظيم مهام فقط إلى تدفق عملي لصياغة منشورات السوشيال.
- اعتماد **النشر اليدوي فقط** في هذا الإصدار.
- عدم ربط المنصة بسيرفر المادة الإعلامية للقناة في هذا الإصدار.

## القيود المعتمدة (قرار منتج)
1. النشر يتم يدويًا خارج المنصة (لا تكامل API مباشر مع Facebook/X/YouTube/TikTok/Instagram).
2. لا توجد مزامنة تلقائية مع Media Server القناة.
3. المنصة مسؤولة عن:
   - توليد الصياغة بحسب المنصة.
   - حفظ الصياغات داخل المهمة.
   - تقديم زر نسخ سريع للنص.

## الحالة الحالية (تم الإنجاز)

### 1) موديول Digital Team الأساسي
- قاعدة البيانات + الموديلات + الخدمات + API + واجهة:
  - `alembic/versions/20260301_digital_team_module.py`
  - `backend/app/models/digital_team.py`
  - `backend/app/schemas/digital.py`
  - `backend/app/services/digital_team_service.py`
  - `backend/app/api/routes/digital.py`
  - `frontend/src/app/digital/page.tsx`
  - `frontend/src/lib/api.ts`
  - `frontend/src/components/layout/Sidebar.tsx`

### 2) توليد الصياغة العملية
- Endpoint جديد للصياغة حسب المهمة والمنصة:
  - `POST /api/v1/digital/tasks/{task_id}/compose`
- منطق الصياغة:
  - يقرأ مصدر المهمة (خبر/حدث/برنامج) إن وجد.
  - يولد نصًا مناسبًا للمنصة + hashtags.
  - يستخدم AI variants مع fallback نصي في حال عدم التوفر.

### 3) واجهة عملية لفريق الديجيتال
داخل صفحة `/digital` تمت إضافة:
1. اختيار برنامج/مسلسل من الشبكة البرامجية.
2. اختيار متعدد للمنصات المستهدفة.
3. إدخال مسودة تشرح المقطع.
4. زر: **توليد حسب المنصات**.
5. عرض صياغة لكل منصة قابلة للتعديل.
6. زر **نسخ** مبسط لكل منصة.
7. زر **حفظ كل الصياغات** داخل المهمة.

## الشبكة البرامجية (Seed)
- ملف seed جاهز:
  - `backend/app/data/programs/program_grid.json`
- يتم استيراده عبر:
  - `POST /api/v1/digital/program-slots/import?overwrite=false`

## الإشعارات
- تم دمج تنبيهات `digital_task` في:
  - `GET /api/v1/dashboard/notifications`

## Commits المرتبطة بهذه المرحلة
- `edf1bb2` feat(digital): add full social media operations board for news/tv
- `375cfdb` feat(digital): add practical social post composer for tasks/programs/events
- `15c159c` feat(digital): program-based multi-platform post composer with save-all and copy

## اختبار سريع بعد النشر
1. افتح `/digital`.
2. اختر برنامج/مسلسل.
3. اختر منصة واحدة أو أكثر.
4. اكتب مسودة المقطع.
5. اضغط **توليد حسب المنصات**.
6. راجع وعدّل النص.
7. اضغط **حفظ كل الصياغات**.
8. انسخ النص بزر **نسخ** ثم انشر يدويًا.

## أوامر التشغيل على السيرفر
```bash
cd ~/ech-swarm
git pull origin "$(git branch --show-current)"
docker compose build backend worker frontend
docker compose up -d --force-recreate backend worker frontend
docker compose exec -T backend alembic upgrade head
```

## نقاط متابعة مقترحة للجلسة القادمة
1. إضافة نبرة الصياغة كخيار قبل التوليد:
   - `إخباري` / `شبابي` / `عاجل` / `ترويجي`.
2. إضافة Preflight checks قبل الحفظ:
   - طول النص حسب المنصة.
   - اكتشاف أخطاء لغوية/ترقيمية شائعة.
   - تنبيه صياغة غير مناسبة.
3. إضافة قوالب قابلة للحفظ لكل برنامج.
4. تحسين تقرير "ماذا نُشر يدويًا" (تتبع رابط المنشور والتاريخ والمنصة).

## ملاحظات بيئة محلية (Windows PowerShell)
- لا تستخدم `\` لتقسيم أوامر `git add` في PowerShell.
- الصيغة الصحيحة: مصفوفة `$files` ثم `git add -- $files`.

