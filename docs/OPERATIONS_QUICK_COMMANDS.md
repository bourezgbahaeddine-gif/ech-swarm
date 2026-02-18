# OPERATIONS QUICK COMMANDS — أوامر التشغيل السريعة

## 1) رفع التعديلات من جهازك إلى GitHub (Windows CMD)
> في CMD استخدم سطر واحد لـ `git add` أو استخدم `^` فقط داخل CMD (ليس PowerShell).

```cmd
cd /d D:\AI Agent GOOGLE\echorouk-swarm
git status --short
git add backend frontend alembic docs
git commit -m "Docs: experiment package + content map + troubleshooting playbook"
git push origin main
```

## 2) استيراد التعديلات على السيرفر
```bash
cd ~/ech-swarm
git pull origin main
docker compose up -d --build backend frontend
docker compose run --rm backend alembic upgrade head
docker compose restart backend
```

## 3) تحقق التشغيل بعد النشر
```bash
curl -sS http://127.0.0.1:8000/health

TOKEN=$(curl -sS -X POST http://127.0.0.1:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"bourezgb","password":"password123"}' \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')

curl -sS "http://127.0.0.1:8000/api/v1/dashboard/stats" -H "Authorization: Bearer $TOKEN"
curl -sS "http://127.0.0.1:8000/api/v1/dashboard/notifications?limit=20" -H "Authorization: Bearer $TOKEN"
curl -sS "http://127.0.0.1:8000/api/v1/news/?page=1&per_page=20" -H "Authorization: Bearer $TOKEN"
```

## 4) مراقبة اللوج أثناء التجربة
```bash
docker logs ech-backend --since 15m | tail -n 200
docker logs ech-backend --since 15m | egrep -i "error|traceback|invalid input value|undefinedtable|telegram_sent|router_batch_complete"
```

## 5) أوامر تشخيص سريعة لقاعدة البيانات
```bash
docker exec -i ech-postgres psql -U echorouk -d echorouk_db -c "\dt article_quality_reports"
docker exec -i ech-postgres psql -U echorouk -d echorouk_db -c "\dt user_activity_logs"
docker exec -i ech-postgres psql -U echorouk -d echorouk_db -c "
SELECT e.enumlabel
FROM pg_enum e
JOIN pg_type t ON t.oid = e.enumtypid
WHERE t.typname = 'newsstatus'
ORDER BY e.enumsortorder;
"
```

## 6) ملاحظات مهمة
- لا تستخدم أوامر مخصصة لـ PowerShell داخل CMD (`Remove-Item`, التعليقات بـ `#`).
- في CMD:
  - التعليق يكون `REM`.
  - سطر متعدد الأوامر يكون بـ `^`.
- لا تستخدم backtick `` ` `` في CMD.
