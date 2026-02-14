-- Add regional/news RSS sources in bulk (idempotent).
-- Run with:
-- docker exec -i ech-postgres psql -U echorouk -d echorouk_db < scripts/add_regional_rss_sources.sql

INSERT INTO sources (name, method, url, rss_url, language, source_type, credibility, priority, enabled, created_at, updated_at)
VALUES
  ('Al Masry Al Youm', 'rss', 'https://www.almasryalyoum.com/rss/rssfeed', 'https://www.almasryalyoum.com/rss/rssfeed', 'ar', 'media', 'medium', 6, true, now(), now()),
  ('The New Arab', 'rss', 'https://www.newarab.com/rss', 'https://www.newarab.com/rss', 'en', 'media', 'medium', 5, true, now(), now()),
  ('Al Yaum', 'rss', 'https://www.alyaum.com/rssFeed/1005', 'https://www.alyaum.com/rssFeed/1005', 'ar', 'media', 'medium', 5, true, now(), now()),
  ('3sri', 'rss', 'https://3sri.net/feed/', 'https://3sri.net/feed/', 'ar', 'media', 'low', 4, true, now(), now()),
  ('Al Sharq', 'rss', 'https://al-sharq.com/rss/latestNews', 'https://al-sharq.com/rss/latestNews', 'ar', 'media', 'medium', 5, true, now(), now()),
  ('Doha News', 'rss', 'https://dohanews.co/feed/', 'https://dohanews.co/feed/', 'en', 'media', 'medium', 5, true, now(), now()),
  ('Al Dostor', 'rss', 'https://www.dostor.org/rss.aspx', 'https://www.dostor.org/rss.aspx', 'ar', 'media', 'medium', 5, true, now(), now()),
  ('Al Khaleej', 'rss', 'https://www.alkhaleej.ae/section/1110/rss.xml', 'https://www.alkhaleej.ae/section/1110/rss.xml', 'ar', 'media', 'medium', 6, true, now(), now()),
  ('Aswat24', 'rss', 'https://aswat24.com/feed/', 'https://aswat24.com/feed/', 'ar', 'media', 'low', 4, true, now(), now()),
  ('Al Jazeera Arabic', 'rss', 'https://www.aljazeera.com/xml/rss/all.xml', 'https://www.aljazeera.com/xml/rss/all.xml', 'ar', 'media', 'high', 7, true, now(), now()),
  ('Okaz', 'rss', 'https://www.okaz.com.sa/rssFeed/0', 'https://www.okaz.com.sa/rssFeed/0', 'ar', 'media', 'medium', 5, true, now(), now()),
  ('Alsumaria', 'rss', 'https://www.alsumaria.tv/Rss/iraq-latest-news/ar', 'https://www.alsumaria.tv/Rss/iraq-latest-news/ar', 'ar', 'media', 'medium', 5, true, now(), now()),
  ('El Shark Online', 'rss', 'https://www.elsharkonline.com/feed/', 'https://www.elsharkonline.com/feed/', 'ar', 'media', 'low', 4, true, now(), now()),
  ('Buratha News', 'rss', 'https://burathanews.com/rss.php', 'https://burathanews.com/rss.php', 'ar', 'media', 'medium', 5, true, now(), now()),
  ('Newsabah', 'rss', 'https://newsabah.com/feed', 'https://newsabah.com/feed', 'ar', 'media', 'low', 4, true, now(), now()),
  ('Assabah', 'rss', 'https://assabah.ma/feed', 'https://assabah.ma/feed', 'ar', 'media', 'medium', 5, true, now(), now()),
  ('The Arab Daily News', 'rss', 'https://thearabdailynews.com/feed/', 'https://thearabdailynews.com/feed/', 'en', 'media', 'low', 4, true, now(), now()),
  ('All Arab News', 'rss', 'https://allarab.news/feed/', 'https://allarab.news/feed/', 'ar', 'media', 'low', 4, true, now(), now()),
  ('Al Bawaba Arabic', 'rss', 'https://www.albawaba.com/rss/ar-all', 'https://www.albawaba.com/rss/ar-all', 'ar', 'media', 'medium', 5, true, now(), now()),
  ('Sky News Arabia', 'rss', 'https://www.skynewsarabia.com/rss.xml', 'https://www.skynewsarabia.com/rss.xml', 'ar', 'media', 'high', 7, true, now(), now()),
  ('The Arab Weekly', 'rss', 'https://thearabweekly.com/feeds', 'https://thearabweekly.com/feeds', 'en', 'media', 'medium', 5, true, now(), now()),
  ('The Arabian Post', 'rss', 'https://thearabianpost.com/feed/', 'https://thearabianpost.com/feed/', 'en', 'media', 'low', 4, true, now(), now()),
  ('Al Raid', 'rss', 'https://alraid.in/feed/', 'https://alraid.in/feed/', 'ar', 'media', 'low', 4, true, now(), now()),
  ('Aswaq Press', 'rss', 'https://aswaqpress.com/feed/', 'https://aswaqpress.com/feed/', 'ar', 'media', 'low', 4, true, now(), now()),
  ('Al Ahram Al Riyadi', 'rss', 'https://alahramalriyadi.com/feed/', 'https://alahramalriyadi.com/feed/', 'ar', 'media', 'low', 4, true, now(), now()),
  ('Marie Claire Arabia', 'rss', 'https://marieclairearabia.com/rss.xml', 'https://marieclairearabia.com/rss.xml', 'ar', 'media', 'medium', 4, true, now(), now()),
  ('Diventures Arabic', 'rss', 'https://diventures.co/ar/feed/', 'https://diventures.co/ar/feed/', 'ar', 'media', 'low', 3, true, now(), now()),
  ('The Arab Hospital', 'rss', 'https://www.thearabhospital.com/feed/', 'https://www.thearabhospital.com/feed/', 'ar', 'media', 'medium', 4, true, now(), now()),
  ('Alayam International', 'rss', 'https://feeds.feedburner.com/alayam-online-international-news', 'https://feeds.feedburner.com/alayam-online-international-news', 'ar', 'media', 'medium', 5, true, now(), now()),
  ('Haya Online', 'rss', 'https://haya-online.com/rss.xml', 'https://haya-online.com/rss.xml', 'ar', 'media', 'medium', 4, true, now(), now())
ON CONFLICT (url) DO UPDATE
SET
  rss_url = EXCLUDED.rss_url,
  method = EXCLUDED.method,
  enabled = true,
  updated_at = now();

-- NOTE:
-- BBC OPML is not an RSS feed item endpoint:
-- http://news.bbc.co.uk/rss/feeds.opml
-- Import OPML separately by parsing it into concrete RSS feed URLs.
