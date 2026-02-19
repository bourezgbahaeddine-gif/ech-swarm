# M7 - محاكي الجمهور (Audience Simulation Sandbox)

تاريخ الإضافة: 2026-02-19

## الهدف
تقييم ردود الفعل المتوقعة قبل النشر عبر:
- `Risk Score` من 1 إلى 10
- `Virality Score` من 1 إلى 10
- تفكيك المخاطر/الانتشار
- تعليقات Personas (Skeptic / Memer / Traditionalist)
- نصائح تحرير + 3 عناوين بديلة

## بنية التنفيذ
- Graph مستقل بـ `LangGraph`:
  1. `load_policy_profile`
  2. `sanitize_input`
  3. `run_persona_simulation`
  4. `compute_scores`
  5. `generate_editor_advice`
  6. `persist_and_return`
- التشغيل يتم عبر Task غير متزامن في الخدمة وليس داخل طلب HTTP المباشر.
- بث التقدم متاح عبر SSE.

## الجداول
- `sim_runs`
- `sim_results`
- `sim_feedback`
- `sim_calibration`
- `sim_job_events`

## API
- `POST /api/v1/sim/run`
- `GET /api/v1/sim/runs/{run_id}`
- `GET /api/v1/sim/result?run_id=...`
- `GET /api/v1/sim/history`
- `GET /api/v1/sim/live?run_id=...` (SSE)

## RBAC
- تشغيل المحاكاة: `journalist`, `editor_chief`, `director`
- عرض النتائج: كل أدوار غرفة التحرير

## الواجهة
- صفحة مستقلة: `/simulator`
- زر داخل المحرر الذكي: `محاكي الجمهور` في شريط الأدوات
- تبويب نتائج داخل المحرر الذكي: `محاكي الجمهور`

## ملاحظات تشغيل
- في حال فشل LLM يتم fallback heuristic آمن.
- المخرجات تستخدم JSON صارم ويتم تجاهل أي نص جانبي.
