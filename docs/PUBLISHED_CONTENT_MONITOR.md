# نظام مراقبة المحتوى المنشور (RSS Quality Monitor)

## الهدف
- مراقبة جودة المحتوى المنشور من `https://www.echoroukonline.com/feed`.
- تطبيق قواعد الدستور التحريري (Clickbait + أخطاء إملائية + بنية الخبر + SEO).
- إرسال تنبيه تيليغرام عند وجود مقالات أقل من عتبة الجودة.

## دورة التشغيل
1. تشغيل دوري كل 15 دقيقة (قابل للتغيير من البيئة).
2. جلب أحدث المقالات من RSS.
3. تحليل كل مقال وتوليد:
- `score` من 0 إلى 100
- `grade` (ممتاز / جيد / مقبول / ضعيف)
- `issues`
- `suggestions`
4. حفظ آخر تقرير في Redis.
5. عند وجود عناصر ضعيفة: إرسال تنبيه تلقائي إلى تيليغرام.

## القواعد الحالية
- كشف عبارات Clickbait.
- كشف أخطاء إملائية شائعة.
- فحص طول العنوان.
- فحص طول المحتوى.
- فحص الهرم الإخباري في الفقرة الأولى (من/ماذا/أين/متى).
- فحص وجود كلمات خبرية قوية.

## إعدادات البيئة
```env
PUBLISHED_MONITOR_ENABLED=true
PUBLISHED_MONITOR_INTERVAL_MINUTES=15
PUBLISHED_MONITOR_FEED_URL=https://www.echoroukonline.com/feed
PUBLISHED_MONITOR_LIMIT=12
PUBLISHED_MONITOR_FETCH_TIMEOUT=12
PUBLISHED_MONITOR_ALERT_THRESHOLD=75
```

## API
- `POST /api/v1/dashboard/agents/published-monitor/run`
  - باراميترات اختيارية: `feed_url`, `limit`, `wait=true|false`
- `GET /api/v1/dashboard/agents/published-monitor/latest`
  - باراميترات: `refresh_if_empty=true|false`, `limit`

## الواجهة
- زر جديد في الشريط العلوي: `جودة المنشور`.
- يفتح نافذة تفصيلية فيها:
- مؤشرات عامة.
- قائمة المقالات المفحوصة.
- المشاكل والاقتراحات.
- زر `فحص الآن`.

## التيليغرام
- يتم الإرسال عند وجود مقالات أقل من العتبة فقط.
- القناة الأساسية: `TELEGRAM_CHANNEL_ALERTS` (ثم fallback إلى `TELEGRAM_CHANNEL_EDITORS`).
