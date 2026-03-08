from app.services.echorouk_archive_service import echorouk_archive_service


LISTING_HTML = """
<html>
  <head>
    <link rel="next" href="https://www.echoroukonline.com/economy/page/2" />
  </head>
  <body>
    <a href="https://www.echoroukonline.com/economy/page/2">Next</a>
    <a href="https://www.echoroukonline.com/economy/sample-story-one">Story 1</a>
    <a href="https://www.echoroukonline.com/economy/sample-story-two">Story 2</a>
    <a href="https://www.echoroukonline.com/tag/politics">Tag</a>
  </body>
</html>
"""

ARTICLE_HTML = """
<html lang="ar-DZ">
  <head>
    <link rel="canonical" href="https://www.echoroukonline.com/economy/sample-story-one/" />
    <meta property="og:type" content="article" />
    <meta property="og:title" content="قصة اقتصادية تجريبية" />
    <meta property="og:description" content="ملخص قصير للمقال." />
    <meta property="article:published_time" content="2026-03-08T11:00:00+00:00" />
    <meta name="author" content="كاتب تجريبي" />
  </head>
  <body>
    <article>
      <h1>قصة اقتصادية تجريبية</h1>
      <p>هذا نص طويل نسبيا يشرح تفاصيل الخبر الاقتصادي المحلي وما يرافقه من معطيات وسياق مهم.</p>
      <p>الفقرة الثانية تضيف تفاصيل كافية حتى يتجاوز المحتوى الحد الأدنى المطلوب للفهرسة المرجعية.</p>
      <p>الفقرة الثالثة موجودة لتأكيد أن الاستخراج سيحتفظ بمحتوى غني يصلح للاسترجاع المرجعي.</p>
      <p>الفقرة الرابعة تضيف بعض الكلمات الإضافية لضمان طول النص وعدم اعتباره صفحة غير صالحة.</p>
    </article>
  </body>
</html>
"""


def test_parse_listing_page_extracts_articles_and_next_page():
    article_urls, next_urls = echorouk_archive_service._parse_listing_page(
        "https://www.echoroukonline.com/economy",
        LISTING_HTML,
    )

    assert "https://echoroukonline.com/economy/sample-story-one" in article_urls
    assert "https://echoroukonline.com/economy/sample-story-two" in article_urls
    assert "https://echoroukonline.com/economy/page/2" in next_urls


def test_parse_article_page_extracts_payload():
    payload = echorouk_archive_service._parse_article_page(
        "https://www.echoroukonline.com/economy/sample-story-one",
        ARTICLE_HTML,
    )

    assert payload is not None
    assert payload.title == "قصة اقتصادية تجريبية"
    assert payload.author == "كاتب تجريبي"
    assert payload.canonical_url == "https://echoroukonline.com/economy/sample-story-one"
    assert payload.summary == "ملخص قصير للمقال."
    assert payload.category is not None
    assert len(payload.content) > 200
