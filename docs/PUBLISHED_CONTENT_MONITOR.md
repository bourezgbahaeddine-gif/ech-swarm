# نظام مراقبة المحتوى المنشور (Published Content Monitor)

آخر تحديث: 2026-03-09

## الهدف
- مراقبة جودة المحتوى المنشور عبر RSS.
- اكتشاف مشاكل تحريرية/لغوية/أسلوبية بعد النشر.
- إصدار تقرير مختصر يساعد غرفة الأخبار على قرار سريع.
- إرسال تنبيه تيليغرام عند وجود مواد منخفضة الجودة.

## دورة التشغيل
1) تشغيل دوري كل 15 دقيقة (قابل للتعديل).
2) جلب أحدث المقالات من RSS.
3) تحليل كل مقال وإنتاج:
   - `score` من 0 إلى 100
   - `grade` (ممتاز/جيد/مقبول/ضعيف)
   - قائمة ملاحظات مرتّبة حسب الخطورة
   - اقتراحات موضعية مختصرة
4) حفظ آخر تقرير في Redis.
5) إرسال تنبيه عند انخفاض الدرجة عن العتبة.

## معايير الفحص
- وضوح العنوان وتطابقه مع المتن.
- بنية الخبر (هرم مقلوب).
- أخطاء لغوية وإملائية.
- الحشو والتكرار.
- وضوح القراءة على الهاتف.
- وجود ادعاءات غير مسندة.

## إعدادات البيئة
```env
ECHOROUK_OS_PUBLISHED_MONITOR_ENABLED=true
ECHOROUK_OS_PUBLISHED_MONITOR_INTERVAL_MINUTES=15
ECHOROUK_OS_PUBLISHED_MONITOR_FEED_URL=https://www.echoroukonline.com/feed
ECHOROUK_OS_PUBLISHED_MONITOR_LIMIT=12
ECHOROUK_OS_PUBLISHED_MONITOR_FETCH_TIMEOUT=12
ECHOROUK_OS_PUBLISHED_MONITOR_ALERT_THRESHOLD=75
```

## API
- `POST /api/v1/dashboard/agents/published-monitor/run`
  - اختياري: `feed_url`, `limit`, `wait=true|false`
- `GET /api/v1/dashboard/agents/published-monitor/latest`
  - اختياري: `refresh_if_empty=true|false`, `limit`

## الواجهة
- زر أعلى الشريط: **جودة المحتوى المنشور**.
- يعرض مؤشرات عامة + قائمة المقالات + المشاكل + التوصيات.
- زر “فحص الآن” لتشغيل يدوي.

## التنبيه (Telegram)
- يُرسل فقط عند وجود مواد أقل من العتبة.
- القنوات: `TELEGRAM_CHANNEL_ALERTS` (مع fallback إلى `TELEGRAM_CHANNEL_EDITORS`).
