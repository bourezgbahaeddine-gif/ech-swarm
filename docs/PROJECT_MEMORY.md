# ذاكرة المشروع (Project Memory)

## الهدف
ذاكرة مشتركة تحفظ:
- القرارات التشغيلية.
- الدروس من الأعطال.
- المراجع المعرفية.
- خلاصات الجلسات.

حتى لا يتكرر نفس الخطأ ولتسريع اتخاذ القرار داخل غرفة التحرير.

## الأنواع
- `operational`: إجراءات تشغيلية وحلول أعطال.
- `knowledge`: معرفة ثابتة (سياسات، تكاملات، قواعد).
- `session`: مخرجات جلسات العمل اليومية.

## الصلاحيات
- قراءة: المدير، رئيس التحرير، الصحفي، السوشيال ميديا، محرر النسخة المطبوعة.
- كتابة: المدير، رئيس التحرير، الصحفي، محرر النسخة المطبوعة.
- أرشفة/إعادة تفعيل: المدير، رئيس التحرير.

## API
- `GET /api/v1/memory/overview`
- `GET /api/v1/memory/items`
- `POST /api/v1/memory/items`
- `GET /api/v1/memory/items/{id}`
- `PATCH /api/v1/memory/items/{id}`
- `POST /api/v1/memory/items/{id}/use`
- `GET /api/v1/memory/items/{id}/events`

## واجهة الاستخدام
- صفحة: `/memory`
- مكونات رئيسية:
- بحث وفلاتر.
- قائمة عناصر الذاكرة.
- لوحة تفاصيل + سجل الاستخدام.
- نموذج إضافة عنصر جديد.

## ملاحظات تشغيل
- بعد السحب من GitHub: نفذ migration:
```bash
docker compose run --rm backend alembic upgrade head
```
- ثم أعد تشغيل الخدمات:
```bash
docker compose restart backend frontend
```
