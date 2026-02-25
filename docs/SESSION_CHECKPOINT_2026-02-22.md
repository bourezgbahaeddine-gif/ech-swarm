# SESSION CHECKPOINT — 2026-02-22

## الحالة الحالية
- تم تطبيق إعادة التسمية الرسمية إلى: `Echorouk Editorial OS`.
- تم اعتماد الشعار:
  - `The Operating System for Intelligent Editorial Workflows`
  - `نظام التشغيل الذكي لسير العمل التحريري`
- تم اعتماد الملكية القانونية:
  - `All Rights Reserved`
  - المالك/المصمم/المطور: `Bourezg Baha eddine` (بهاء الدين بورزق)
- تم دفع التعديلات إلى GitHub بنجاح.

## آخر Commitات مرفوعة
1. `774f66d`
   - Branding migration
   - versioning guide
   - docker compose project name
   - env prefix migration
2. `b8c062c`
   - تحويل الترخيص إلى Proprietary / All Rights Reserved
   - إضافة `NOTICE.md`

## تعديلات تقنية مهمة منفذة قبل الانهيار
- تحسين اقتراح الروابط (داخلي/خارجي):
  - تنويع داخلي حسب الموضوع
  - تقليل تكرار الكلمات
  - بوابة موضوعية أكثر صرامة
- تحسين مسح التراند:
  - منع enqueue المكرر لنفس المسح
  - إضافة `generated_at` في cache
  - refresh ذكي عند stale
- إعداد اسم المنتج الجديد في واجهات/Docs/Backend.

## حادثة التشغيل (Incident)
### الأعراض
- المنصة ظهرت فارغة.
- جداول PostgreSQL داخل البيئة الحالية كانت محدودة (`sources`, `users`) فقط.

### السبب المرجح
- تغيير `docker compose project name` أدى لاستخدام Volumes جديدة بدل القديمة، فتم الإقلاع على قاعدة بيانات جديدة/فارغة.

### ما تم التحقق منه
- الخدمات كانت Up.
- backend/worker logs طبيعية وظيفياً.
- `curl /health` كان يعمل بعد إعادة التشغيل.
- لكن البيانات التاريخية لم تكن على volume الحالية.

## المطلوب لاحقاً (Recovery Plan)
1. تحديد Volume PostgreSQL القديمة بالحجم/التاريخ.
2. نسخ محتواها إلى `ech-swarm_pgdata` بعد أخذ backup.
3. تشغيل stack والتحقق من رجوع جداول المقالات.

## أوامر استرجاع موصى بها لاحقاً
```bash
cd ~/ech-swarm

docker volume ls --format '{{.Name}}' | egrep 'pgdata|postgres'

# بعد تحديد OLD_VOL الصحيح:
CUR_VOL=ech-swarm_pgdata
OLD_VOL=<OLD_POSTGRES_VOLUME>

docker compose down

docker run --rm -v ${CUR_VOL}:/to alpine sh -c 'rm -rf /to/* /to/.[!.]* /to/..?* 2>/dev/null || true'
docker run --rm -v ${OLD_VOL}:/from -v ${CUR_VOL}:/to alpine sh -c 'cp -a /from/. /to/'

docker compose up -d postgres redis backend worker frontend
curl -sS --retry 8 --retry-connrefused --retry-delay 2 http://127.0.0.1:8000/health
docker compose exec -T postgres psql -U echorouk -d echorouk_db -c '\dt'
```

## إغلاق آمن للسيرفر (بدون حذف البيانات)
```bash
cd ~/ech-swarm
docker compose down
```

> تحذير: لا تستخدم `docker compose down -v` حتى لا يتم حذف الـ volumes.
