# INSTRUCTURE — مرجع منصة Echorouk Editorial OS

هذا الملف هو المرجع التشغيلي والتقني والتحريري للمنصة.

آخر تحديث: 2026-03-09

## 1) الهدف
- إدارة دورة الخبر من الالتقاط حتى **جاهز للنشر اليدوي**.
- فرض حوكمة تحريرية قبل الاعتماد النهائي.
- إبقاء النشر النهائي يدويًا 100%.

## 2) مكوّنات المنصة
- Backend: FastAPI + SQLAlchemy + Alembic.
- Frontend: Next.js 16 + React + TypeScript + Tailwind.
- Data: PostgreSQL + pgvector + Redis.
- Async: Celery Workers + Redis Broker/Result.
- Storage: MinIO.
- Feeds: FreshRSS + RSS‑Bridge.

## 3) دورة الخبر المعتمدة
1) الالتقاط (Scout).
2) التصنيف والتوجيه (Router).
3) توليد مسودة أولية (Scribe).
4) تحرير داخل Smart Editor.
5) تشغيل بوابات الجودة والتحقق.
6) إرسال لرئيس التحرير.
7) اعتماد نهائي → ready_for_manual_publish.

## 4) المحرر الذكي (Smart Editor)
- وضع السرعة افتراضيًا لتخفيف الحمل البصري.
- زر “التالي” يقود لأهم إجراء.
- أدوات متقدمة تظهر عند الضغط.
- طبقة “مراجعة احترافية” و“ثقة وتفسير” مطويتان افتراضيًا.
- تدقيق لغوي/أسلوبي + تحسين بدون تغيير الحقائق.
- تاريخ نسخ + diff + restore.

## 5) ما بعد النشر (Published Monitor)
- فحص دوري للمحتوى المنشور عبر RSS.
- تقارير جودة مختصرة + تنبيه تيليغرام عند الانخفاض.
- صفحة مخصصة في الشريط العلوي.

## 6) أرشيف الشروق + RAG
- زاحف خلفي يبني الأرشيف تدريجياً.
- بحث دلالي ضمن `/archive`.
- RAG يضيف سياقاً للمسودة عندما يكون مفعلاً.

## 7) الأدوار والصلاحيات
- الصحفي: تحرير وتشغيل الأدوات دون اعتماد نهائي.
- رئيس التحرير: اعتماد نهائي أو إرجاع.
- المدير: صلاحيات كاملة + إعدادات النظام.

## 8) أوامر التشغيل الأساسية
تحديث وتشغيل:
```
cd ~/ech-swarm
git pull --ff-only origin main
docker compose up -d --build --force-recreate backend worker frontend
docker compose exec backend alembic upgrade head
curl http://127.0.0.1:8000/health
```

## 9) نقاط واجهة مهمة
- الشريط العلوي يحتوي أدوات أساسية + “المزيد من الأدوات”.
- تبويبات أساسية + “أدوات متقدمة”.
- المحرر يركز على القرار قبل التفاصيل.

## 10) مراجع مرتبطة
- `docs/PLATFORM_MASTER_DETAILS_AR.md`
- `docs/architecture.md`
- `docs/M5_SMART_EDITOR.md`
- `docs/PUBLISHED_CONTENT_MONITOR.md`
