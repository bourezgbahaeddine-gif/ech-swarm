# الملف التعريفي للمشروع — Echorouk Editorial OS

آخر تحديث: 2026-03-09

## 1) ملخص تنفيذي
منصة تشغيل لغرفة الأخبار تدير دورة الخبر من الالتقاط حتى الجاهزية للنشر اليدوي، مع حوكمة صارمة وHuman‑in‑the‑Loop.

## 2) أهداف التشغيل
- تسريع تدفق الأخبار دون التضحية بالتحكم التحريري.
- رفع جودة القرار عبر بوابات جودة وتحليل ادعاءات.
- منع النشر التلقائي: الاعتماد والنشر دائمًا بشري.
- تعزيز السياق عبر الأرشيف والبحث الدلالي.

## 3) النطاق
يشمل:
- الالتقاط من RSS/FreshRSS/RSS‑Bridge.
- التنظيف وإزالة التكرار والتصنيف.
- توليد مسودات أولية.
- تدقيق لغوي/أسلوبي + جودة + بوابة نشر.
- وحدة المحرر الذكي مع نسخ ودِف وتاريخ.
- الأرشيف + البحث الدلالي + RAG.
- المراقبة بعد النشر + التنبيهات.

لا يشمل:
- النشر النهائي التلقائي على الـ CMS (النشر يدوي فقط).

## 4) الحزمة التقنية
- Backend: FastAPI + SQLAlchemy + Alembic.
- Data: PostgreSQL + pgvector + Redis.
- Async: Celery + Redis Broker/Result.
- Frontend: Next.js 16 + React + TypeScript + Tailwind.
- Storage: MinIO.

## 5) الوحدات الرئيسية
- Newsroom Pipeline (Scout/Router/Scribe).
- Smart Editor + Chief Approval.
- Quality Gates + Fact‑Check.
- Published Content Monitor.
- Echorouk Archive + RAG.
- Trends, MSI, Audience Simulator.
- Competitor X‑Ray + Document Intel + Media Logger.
- Project Memory.

## 6) الواجهات الأساسية
- `/news` الأخبار.
- `/workspace-drafts` المحرر الذكي.
- `/archive` الأرشيف.
- `/trends` الترندات.
- `/memory` ذاكرة المشروع.

## 7) التشغيل المختصر
- تحديث الكود: `git pull`.
- بناء وتشغيل: `docker compose up -d --build --force-recreate backend worker frontend`.
- ترحيل: `docker compose exec backend alembic upgrade head`.
- فحص الصحة: `curl http://127.0.0.1:8000/health`.

مرجع موسّع: `docs/PLATFORM_MASTER_DETAILS_AR.md`.
