# M5 — Smart Editor (المحرر الذكي)

آخر تحديث: 2026-03-09

## النطاق
المحرر الذكي هو واجهة التحرير الأساسية:
- تحرير نصي احترافي (TipTap).
- مراجعة لغوية/أسلوبية/جودة.
- التحقق من الادعاءات وربط الأدلة.
- بوابة نشر تمنع الإرسال عند وجود موانع.
- تاريخ نسخ + مقارنة + استعادة.

## فلسفة UX
- تقليل الحمل المعرفي: القرار أولاً ثم التفاصيل.
- وضع السرعة افتراضيًا، والعمق عند الطلب.
- زر “التالي” يقود لأهم إجراء.
- أدوات متقدمة تُفتح عند الحاجة.

## الواجهة الحالية
- مركز قرار: عاجل الآن + يحسّن الجودة (في وضع السرعة).
- طبقات مطوية: مراجعة احترافية + ثقة وتفسير.
- تبويبات أساسية: تحقق، تدقيق، جودة، SEO.
- أدوات متقدمة: روابط، سوشيال، MSI، محاكي، منافسين، سياق.

## المسارات الأساسية (API)
- `GET /api/v1/editorial/workspace/drafts/{work_id}/context`
- `POST /api/v1/editorial/workspace/drafts/{work_id}/autosave`
- `POST /api/v1/editorial/workspace/drafts/{work_id}/ai/rewrite`
- `POST /api/v1/editorial/workspace/drafts/{work_id}/ai/headlines`
- `POST /api/v1/editorial/workspace/drafts/{work_id}/ai/seo`
- `POST /api/v1/editorial/workspace/drafts/{work_id}/ai/social`
- `POST /api/v1/editorial/workspace/drafts/{work_id}/verify/claims`
- `POST /api/v1/editorial/workspace/drafts/{work_id}/quality/score`
- `GET /api/v1/editorial/workspace/drafts/{work_id}/publish-readiness`
- `POST /api/v1/editorial/workspace/drafts/{work_id}/ai/apply`

## حماية الجودة
- بوابة النشر تمنع الإرسال إذا فشل FACT_CHECK أو QUALITY أو READABILITY أو SEO.
- الادعاءات الخطرة تُعرض أولاً داخل مركز القرار.

## الملفات الرئيسية
- Frontend: `frontend/src/app/workspace-drafts/page.tsx`
- Backend: `backend/app/services/smart_editor_service.py`

## تشغيل محلي سريع
```
docker compose up -d --build backend frontend
docker compose exec backend alembic upgrade head
```
