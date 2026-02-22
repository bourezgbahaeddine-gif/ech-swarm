# M8 — Link Intelligence (Internal + External)

## الهدف
توفير خدمة موحدة داخل المحرر الذكي تقترح روابط:
- داخلية من أرشيف الشروق.
- خارجية من مصادر موثوقة (trusted domains).

الخدمة تعمل كمقترحات تحريرية فقط (لا نشر تلقائي).

## المكونات المنفذة

### 1) قاعدة البيانات
تمت إضافة الجداول التالية:
- `link_index_items`
- `trusted_domains`
- `link_recommendation_runs`
- `link_recommendation_items`
- `link_click_events`

Migration:
- `alembic/versions/20260222_link_intelligence_tables.py`

### 2) خدمة Backend
ملف الخدمة:
- `backend/app/services/link_intelligence_service.py`

وظائف أساسية:
- `sync_index_from_articles`: فهرسة داخلية/خارجية من مقالات النظام.
- `suggest_for_workspace`: توليد اقتراحات روابط حسب النمط `internal|external|mixed`.
- `validate_run`: فحص قابلية الوصول للروابط.
- `apply_links_to_html`: إدراج روابط بشكل احترافي ضمن أقسام "اقرأ أيضا" و"مراجع خارجية".
- `history`: سجل التشغيلات السابقة لكل `work_id`.

### 3) API Endpoints
أضيفت على `editorial workspace`:
- `POST /api/v1/editorial/workspace/drafts/{work_id}/ai/links/suggest`
- `POST /api/v1/editorial/workspace/drafts/{work_id}/ai/links/validate`
- `POST /api/v1/editorial/workspace/drafts/{work_id}/ai/links/apply`
- `GET  /api/v1/editorial/workspace/drafts/{work_id}/ai/links/history`

### 4) Frontend Integration
تم دمجها في المحرر الذكي:
- زر جديد: `روابط`
- داخل تبويب SEO:
  - اختيار النمط: `مختلط/داخلي/خارجي`
  - توليد الروابط
  - فحص الروابط
  - اختيار الروابط وتطبيقها على المسودة
  - عرض سجل آخر التشغيلات

ملفات:
- `frontend/src/lib/api.ts`
- `frontend/src/app/workspace-drafts/page.tsx`

## طريقة التشغيل

1. ترحيل قاعدة البيانات:
```bash
alembic upgrade head
```

2. إعادة تشغيل الخدمات:
```bash
docker compose up -d --build backend frontend
```

## اختبار سريع (Curl)

1. توليد Token:
```bash
TOKEN=$(curl -sS -X POST http://127.0.0.1:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"bourezgb","password":"password123"}' \
  | python3 -c 'import sys,json; print(json.load(sys.stdin).get("access_token",""))')
```

2. توليد اقتراحات روابط:
```bash
curl -sS -X POST "http://127.0.0.1:8000/api/v1/editorial/workspace/drafts/<WORK_ID>/ai/links/suggest" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"mode":"mixed","target_count":6}'
```

3. فحص الروابط:
```bash
curl -sS -X POST "http://127.0.0.1:8000/api/v1/editorial/workspace/drafts/<WORK_ID>/ai/links/validate" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"run_id":"LNK-..."}'
```

4. تطبيق الروابط على المسودة:
```bash
curl -sS -X POST "http://127.0.0.1:8000/api/v1/editorial/workspace/drafts/<WORK_ID>/ai/links/apply" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"run_id":"LNK-...","based_on_version":<VERSION>}'
```

## ملاحظات تنفيذية
- الروابط الخارجية تخضع لفلترة `trusted_domains`.
- في الوضع `mixed` يتم المزج بين روابط داخلية وخارجية تلقائياً.
- التطبيق ينشئ نسخة مسودة جديدة (versioning محفوظ).
- الإدراج الحالي احترافي وآمن (أقسام منظمة) مع إمكانية تطوير الإدراج inline في مرحلة لاحقة.
