# TROUBLESHOOTING PLAYBOOK — دليل الأعطال السريع

## 0) قاعدة عامة
قبل أي تشخيص:
1. `docker compose ps`
2. `docker logs ech-backend --since 10m | tail -n 200`
3. `docker compose run --rm backend alembic current`

---

## 1) 500 عند تسجيل الدخول: `user_activity_logs does not exist`
### العرض
- `POST /api/v1/auth/login` يرجع 500.
- اللوج يحتوي `relation "user_activity_logs" does not exist`.

### السبب
- migration الخاص بسجل نشاط المستخدم لم يطبق.

### الحل
```bash
docker compose run --rm backend alembic upgrade head
docker exec -i ech-postgres psql -U echorouk -d echorouk_db -c "\dt user_activity_logs"
docker compose restart backend
```

---

## 2) 500 في التنبيهات/الأخبار: `invalid input value for enum newsstatus`
### العرض
- `/dashboard/notifications` أو `/news?status=...` يرجع 500.
- اللوج يحتوي قيمة status بصيغة غير موجودة في enum.

### السبب
- عدم تطابق قيم `newsstatus` بين الكود وقاعدة البيانات.

### التشخيص
```bash
docker exec -i ech-postgres psql -U echorouk -d echorouk_db -c "
SELECT e.enumlabel
FROM pg_enum e
JOIN pg_type t ON t.oid = e.enumtypid
WHERE t.typname = 'newsstatus'
ORDER BY e.enumsortorder;
"
```

### الحل
```bash
docker exec -i ech-postgres psql -U echorouk -d echorouk_db -c "
ALTER TYPE newsstatus ADD VALUE IF NOT EXISTS 'ready_for_chief_approval';
ALTER TYPE newsstatus ADD VALUE IF NOT EXISTS 'approval_request_with_reservations';
ALTER TYPE newsstatus ADD VALUE IF NOT EXISTS 'ready_for_manual_publish';
ALTER TYPE newsstatus ADD VALUE IF NOT EXISTS 'READY_FOR_CHIEF_APPROVAL';
ALTER TYPE newsstatus ADD VALUE IF NOT EXISTS 'APPROVAL_REQUEST_WITH_RESERVATIONS';
ALTER TYPE newsstatus ADD VALUE IF NOT EXISTS 'READY_FOR_MANUAL_PUBLISH';
"
docker compose restart backend
```

---

## 3) 500 في الجودة: `article_quality_reports does not exist`
### العرض
- `/editorial/{id}/quality/*` يرجع 500.
- اللوج يظهر `relation "article_quality_reports" does not exist`.

### السبب
- migration جدول تقارير الجودة غير مطبق أو فشل سابقًا.

### الحل
```bash
docker compose run --rm backend alembic upgrade head
docker exec -i ech-postgres psql -U echorouk -d echorouk_db -c "\dt article_quality_reports"
docker compose restart backend
```

---

## 4) Alembic يفشل مع `StringDataRightTruncation` على `alembic_version`
### العرض
- upgrade يتوقف برسالة:
  - `value too long for type character varying(32)`

### السبب
- `revision id` أطول من سعة عمود `alembic_version.version_num`.

### الحل
- استخدم revision id قصير (<= 32) داخل ملف migration.
- مثال صحيح:
  - `revision = "20260218_policy_gate_statuses"`

---

## 5) تنبيهات التلغرام لا تصل
### التشخيص
```bash
docker logs ech-backend --since 10m | egrep -i "telegram_sent|telegram_error|telegram_not_configured"
```

### تحقق الإعدادات
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHANNEL_ALERTS`
- `TELEGRAM_CHANNEL_EDITORS`

### ملاحظة
- العاجل يرسل Telegram.
- التنبيهات غير العاجلة تكون In-App/Slack حسب السياسات.

---

## 6) `المصادر النشطة 51/130` لماذا؟
### التفسير
- هذه ليست مشكلة تشغيلية بالضرورة.
- تعني أن 51 مصدر فقط `enabled=true` والباقي معطل.

### فحص سريع
```bash
docker exec -i ech-postgres psql -U echorouk -d echorouk_db -c "
SELECT enabled, COUNT(*) FROM sources GROUP BY enabled;
"
```

### تفعيل مصدر
```bash
docker exec -i ech-postgres psql -U echorouk -d echorouk_db -c "
UPDATE sources SET enabled = true WHERE id = <SOURCE_ID>;
"
```

---

## 7) النتائج في المحرر تظهر HTML خام أو نص غير مفهوم
### السبب
- عرض `diff_html` مباشرة بدون تنسيق نصي.

### الإجراء
- راجع UI في `frontend/src/app/workspace-drafts/page.tsx` وتأكد أن العرض:
  - إما `plain text diff`
  - أو HTML sanitized + render مقروء.

---

## 8) فحص شامل سريع بعد أي إصلاح
```bash
TOKEN=$(curl -sS -X POST http://127.0.0.1:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"bourezgb","password":"password123"}' \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')

curl -sS "http://127.0.0.1:8000/api/v1/dashboard/stats" -H "Authorization: Bearer $TOKEN"
curl -sS "http://127.0.0.1:8000/api/v1/dashboard/notifications?limit=20" -H "Authorization: Bearer $TOKEN"
curl -sS "http://127.0.0.1:8000/api/v1/news/?page=1&per_page=10" -H "Authorization: Bearer $TOKEN"
```

---

## 9) UI stuck on constitution confirmation modal
### Symptoms
- User can log in but cannot navigate.
- Overlay `????? ????? ???????` remains blocking.

### Cause
- No active row in `constitution_meta`, so ack flow cannot complete reliably.

### Immediate Unblock
```bash
docker exec -i ech-postgres psql -U echorouk -d echorouk_db -c "
INSERT INTO constitution_meta(version, file_url, is_active, updated_at)
SELECT 'v1.0', '/constitution/guide', true, now()
WHERE NOT EXISTS (
  SELECT 1 FROM constitution_meta WHERE version='v1.0'
);
"
```

### Verify
```bash
docker exec -i ech-postgres psql -U echorouk -d echorouk_db -c "
SELECT id, version, file_url, is_active, updated_at
FROM constitution_meta
ORDER BY updated_at DESC
LIMIT 5;
"
```

---

## 10) `POST /api/v1/sim/run` returns 500
### Symptoms
- API returns generic 500 from simulator run endpoint.
- Frontend simulator panel shows no result.

### Most common cause
- Simulator migrations not applied (`sim_runs` table missing).

### Fix
```bash
docker compose run --rm backend alembic upgrade head
docker exec -i ech-postgres psql -U echorouk -d echorouk_db -c "\dt sim_*"
docker compose restart backend
```

### Health check
```bash
docker logs ech-backend --since 10m | egrep -i "sim_|error|traceback"
```

---

## 11) Browser shows `Minified React error #418`
### Symptoms
- UI crashes with minified React error.
- Often appears in news details page render.

### Cause
- Invalid HTML payload in article body (full HTML document tags inside fragment).

### Fix
- Ensure frontend normalizes article HTML before `dangerouslySetInnerHTML`.
- Hard refresh client cache after deploy (`Ctrl+F5`).
