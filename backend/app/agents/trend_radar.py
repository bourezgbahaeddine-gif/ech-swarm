"""
Echorouk AI Swarm - Trend Radar Agent
=====================================
Detects rising trends by cross-referencing Google Trends,
RSS burst detection, and competitor feeds.
"""

from collections import Counter
from datetime import timedelta
from typing import Optional
import re

import aiohttp
import feedparser

from app.core.config import get_settings
from app.core.logging import get_logger
from app.schemas import TrendAlert
from app.services.ai_service import ai_service
from app.services.cache_service import cache_service
from app.services.notification_service import notification_service
from app.utils.hashing import normalize_text

logger = get_logger("agent.trend_radar")
settings = get_settings()

GOOGLE_TRENDS_URL = "https://trends.google.com/trends/trendingsearches/daily/rss"

COMPETITOR_FEEDS = [
    "https://www.echoroukonline.com/feed/",
    "https://www.elkhabar.com/feed/",
    "https://www.ennaharonline.com/feed/",
    "https://www.tsa-algerie.com/feed/",
    "https://www.aps.dz/xml/rss",
]

CATEGORY_KEYWORDS: dict[str, set[str]] = {
    "politics": {"سياسة", "حكومة", "برلمان", "election", "government", "president", "parlement", "gouvernement"},
    "economy": {"اقتصاد", "نفط", "غاز", "dinar", "market", "inflation", "économie", "pétrole", "banque"},
    "sports": {"رياضة", "كرة", "match", "football", "league", "olympic", "sport", "fifa", "caf"},
    "technology": {"ذكاء", "تقنية", "ai", "tech", "startup", "cyber", "robot", "innovation", "digital"},
    "society": {"مجتمع", "education", "school", "health", "crime", "santé", "éducation", "ramadan"},
    "international": {"ukraine", "gaza", "iran", "france", "europe", "africa", "usa", "israel", "onu"},
}

GEO_LABELS: dict[str, str] = {
    "DZ": "الجزائر",
    "MA": "المغرب",
    "TN": "تونس",
    "EG": "مصر",
    "FR": "فرنسا",
    "US": "الولايات المتحدة",
    "GB": "المملكة المتحدة",
    "GLOBAL": "دولي",
}

# For non-DZ scans, we relax cross-verification by providing
# geo-scoped fallback candidates from Google Trends itself.
NON_DZ_MIN_TRENDS = 6

WEAK_TERMS = {
    # Arabic
    "رئيس", "الجمهورية", "يستقبل", "قال", "أكد", "حول", "بعد", "قبل", "اليوم", "غدا", "أمس", "هذا", "هذه", "هناك",
    "الذي", "التي", "ذلك", "تلك", "على", "إلى", "من", "في", "عن", "مع", "ضد", "خلال", "ضمن", "عند", "حتى",
    # French
    "avec", "sans", "pour", "dans", "sur", "apres", "avant", "selon", "plus", "moins", "tout", "cette", "ceci",
    "president", "republique",
    # English
    "the", "a", "an", "and", "or", "to", "of", "in", "on", "for", "with", "from", "by", "at", "as",
    "today", "yesterday", "tomorrow", "says", "said", "president",
}


class TrendRadarAgent:
    """Trend Radar with category and geography outputs."""

    async def scan(self, geo: str = "DZ", category: str = "all", limit: int = 12) -> list[TrendAlert]:
        """Run a full trend scan cycle."""
        geo = (geo or "DZ").upper()
        category = (category or "all").lower()
        limit = max(1, min(limit, 30))
        try:
            google_trends = await self._fetch_google_trends(geo)
            # Important: competitor feeds + RSS bursts are currently Algeria-centric.
            # We must not pollute non-DZ scans with DZ signals.
            if geo == "DZ":
                competitor_keywords = await self._fetch_competitor_keywords()
                rss_bursts = await self._detect_rss_bursts()
            else:
                competitor_keywords = []
                rss_bursts = []

            verified_trends = self._cross_validate(
                google_trends,
                competitor_keywords,
                rss_bursts,
                geo=geo,
                category_filter=category,
            )

            # For non-DZ geographies, competitor/burst overlap can be low.
            # Promote top Google trends as fallback so newsroom still gets signals.
            if geo != "DZ" and len(verified_trends) < NON_DZ_MIN_TRENDS:
                verified_trends = self._expand_non_dz_fallback(
                    verified_trends=verified_trends,
                    google_trends=google_trends,
                    geo=geo,
                    category_filter=category,
                )

            if not verified_trends:
                logger.info("no_verified_trends", geo=geo, category=category)
                return []

            alerts: list[TrendAlert] = []
            for trend in verified_trends[:limit]:
                alert = await self._analyze_trend(trend, geo=geo)
                if alert:
                    alerts.append(alert)

            if alerts:
                await cache_service.set_json(
                    f"trends:last:{geo}:{category}",
                    {"alerts": [a.model_dump(mode="json") for a in alerts]},
                    ttl=timedelta(minutes=20),
                )

            for alert in alerts[:5]:
                await self._send_alert(alert)

            logger.info("trend_scan_complete", geo=geo, category=category, verified=len(verified_trends), alerts=len(alerts))
            return alerts
        except Exception as e:
            logger.error("trend_scan_error", geo=geo, category=category, error=str(e))
            return []

    def _expand_non_dz_fallback(
        self,
        verified_trends: list[dict],
        google_trends: list[str],
        geo: str,
        category_filter: str,
    ) -> list[dict]:
        existing = {normalize_text(v["keyword"]) for v in verified_trends}
        for trend in google_trends:
            norm = normalize_text(trend)
            if not norm or norm in existing or self._is_weak_term(norm):
                continue
            category = self._categorize_keyword(norm)
            if category_filter != "all" and category != category_filter:
                continue
            verified_trends.append(
                {
                    "keyword": norm,
                    "source_signals": ["google_trends", "geo_fallback"],
                    "strength": 5,
                    "category": category,
                    "geography": self._detect_geography(norm, geo),
                }
            )
            existing.add(norm)
            if len(verified_trends) >= NON_DZ_MIN_TRENDS:
                break
        return verified_trends

    async def _fetch_google_trends(self, geo: str) -> list[str]:
        """Fetch trending searches from Google Trends."""
        try:
            params = {"geo": geo} if geo != "GLOBAL" else {}
            async with aiohttp.ClientSession() as session:
                async with session.get(GOOGLE_TRENDS_URL, params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status != 200:
                        return []
                    content = await resp.text()
                    feed = feedparser.parse(content)
                    return [normalize_text(entry.title) for entry in feed.entries if entry.title]
        except Exception as e:
            logger.warning("google_trends_error", geo=geo, error=str(e))
            return []

    async def _fetch_competitor_keywords(self) -> list[str]:
        """Extract keywords from competitor headlines."""
        keywords: list[str] = []
        try:
            async with aiohttp.ClientSession() as session:
                for url in COMPETITOR_FEEDS:
                    try:
                        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                            if resp.status != 200:
                                continue
                            content = await resp.text()
                            feed = feedparser.parse(content)
                            for entry in feed.entries[:12]:
                                title = normalize_text(entry.get("title", ""))
                                if title:
                                    keywords.extend(self._extract_candidate_terms(title))
                    except Exception:
                        continue
        except Exception as e:
            logger.warning("competitor_fetch_error", error=str(e))
        return keywords

    async def _detect_rss_bursts(self) -> list[str]:
        """Find keywords that suddenly appear in multiple sources."""
        recent_titles = await cache_service.get_recent_titles(100)
        if not recent_titles:
            return []
        word_counts = Counter()
        for title in recent_titles:
            normalized = normalize_text(title)
            word_counts.update(self._extract_candidate_terms(normalized))
        # Keep bursts that repeat enough to be meaningful
        bursts: list[str] = []
        for term, count in word_counts.items():
            threshold = 2 if " " in term else 3
            if count >= threshold and not self._is_weak_term(term):
                bursts.append(term)
        return bursts

    def _cross_validate(
        self,
        google_trends: list[str],
        competitor_keywords: list[str],
        rss_bursts: list[str],
        geo: str,
        category_filter: str,
    ) -> list[dict]:
        """A trend is verified if it appears in at least 2 different sources."""
        verified: list[dict] = []

        all_google = set(google_trends)
        competitor_set = set(competitor_keywords)
        burst_set = set(rss_bursts)

        for trend in all_google:
            if not trend or len(trend) < 3:
                continue
            trend = normalize_text(trend)
            if self._is_weak_term(trend):
                continue
            detected_geo = self._detect_geography(trend, geo)
            if not self._is_geo_compatible(scan_geo=geo, detected_geo=detected_geo):
                continue
            sources = ["google_trends"]
            trend_terms = self._extract_candidate_terms(trend)
            trend_terms.append(trend)

            if any(term in competitor_set for term in trend_terms):
                sources.append("competitors")
            if any(term in burst_set for term in trend_terms):
                sources.append("rss_burst")

            if len(sources) < 2:
                continue

            category = self._categorize_keyword(trend)
            if category_filter != "all" and category != category_filter:
                continue

            verified.append(
                {
                    "keyword": trend,
                    "source_signals": sources,
                    "strength": min(len(sources) * 3 + 2, 10),
                    "category": category,
                    "geography": detected_geo,
                }
            )

        for burst_word in rss_bursts:
            if self._is_weak_term(burst_word):
                continue
            if burst_word in competitor_set and burst_word not in [v["keyword"] for v in verified]:
                category = self._categorize_keyword(burst_word)
                if category_filter != "all" and category != category_filter:
                    continue
                detected_geo = self._detect_geography(burst_word, geo)
                if not self._is_geo_compatible(scan_geo=geo, detected_geo=detected_geo):
                    continue
                verified.append(
                    {
                        "keyword": burst_word,
                        "source_signals": ["rss_burst", "competitors"],
                        "strength": 6,
                        "category": category,
                        "geography": detected_geo,
                    }
                )

        verified = self._merge_similar_trends(verified)
        verified.sort(key=lambda x: x["strength"], reverse=True)
        return verified

    def _extract_candidate_terms(self, text: str) -> list[str]:
        normalized = normalize_text(text)
        tokens = [
            t for t in re.split(r"[^\w\u0600-\u06FF]+", normalized)
            if t and len(t) > 2 and not t.isdigit() and t not in WEAK_TERMS
        ]
        terms: list[str] = []
        terms.extend(tokens)
        # bi-grams and tri-grams improve editorial quality vs single tokens
        for n in (2, 3):
            for i in range(0, max(0, len(tokens) - n + 1)):
                phrase = " ".join(tokens[i:i + n]).strip()
                if phrase and not self._is_weak_term(phrase):
                    terms.append(phrase)
        return list(dict.fromkeys(terms))

    def _is_weak_term(self, term: str) -> bool:
        t = normalize_text(term).strip()
        if not t:
            return True
        if t in WEAK_TERMS:
            return True
        if t.isdigit():
            return True
        if re.fullmatch(r"\d{2,4}", t):
            return True
        if len(t) <= 2:
            return True
        # terms made only of very common words are weak
        parts = [p for p in t.split() if p]
        if parts and all(p in WEAK_TERMS for p in parts):
            return True
        return False

    def _merge_similar_trends(self, trends: list[dict]) -> list[dict]:
        merged: list[dict] = []
        for trend in trends:
            trend_tokens = set(self._extract_candidate_terms(trend["keyword"]))
            if not trend_tokens:
                continue
            matched_idx = None
            for idx, current in enumerate(merged):
                current_tokens = set(self._extract_candidate_terms(current["keyword"]))
                if not current_tokens:
                    continue
                inter = len(trend_tokens & current_tokens)
                union = len(trend_tokens | current_tokens)
                jaccard = inter / union if union else 0
                if jaccard >= 0.6 or trend["keyword"] in current["keyword"] or current["keyword"] in trend["keyword"]:
                    matched_idx = idx
                    break
            if matched_idx is None:
                merged.append(trend)
            else:
                target = merged[matched_idx]
                target["strength"] = min(10, max(target["strength"], trend["strength"]) + 1)
                target["source_signals"] = sorted(set(target["source_signals"]) | set(trend["source_signals"]))
                # keep richer keyword phrase
                if len(trend["keyword"]) > len(target["keyword"]):
                    target["keyword"] = trend["keyword"]
        return merged

    def _categorize_keyword(self, keyword: str) -> str:
        normalized = normalize_text(keyword)
        for category, terms in CATEGORY_KEYWORDS.items():
            if any(term in normalized for term in terms):
                return category
        return "general"

    def _detect_geography(self, keyword: str, fallback_geo: str) -> str:
        normalized = normalize_text(keyword)
        if "الجزائر" in normalized or "alger" in normalized or "dz" in normalized:
            return "DZ"
        if "المغرب" in normalized or "morocco" in normalized:
            return "MA"
        if "تونس" in normalized or "tunisia" in normalized:
            return "TN"
        if "مصر" in normalized or "egypt" in normalized:
            return "EG"
        if "france" in normalized or "فرنسا" in normalized:
            return "FR"
        if "usa" in normalized or "america" in normalized or "الولايات المتحدة" in normalized:
            return "US"
        if "europe" in normalized or "أوروبا" in normalized:
            return "GLOBAL"
        return fallback_geo

    def _is_geo_compatible(self, scan_geo: str, detected_geo: str) -> bool:
        """Allow only trends that belong to selected geography (or global umbrella)."""
        if scan_geo == "GLOBAL":
            return True
        if detected_geo == scan_geo:
            return True
        if detected_geo == "GLOBAL":
            return True
        return False

    async def _analyze_trend(self, trend_data: dict, geo: str) -> Optional[TrendAlert]:
        """Use AI to analyze a verified trend and suggest editorial angles."""
        keyword = trend_data["keyword"]
        cache_key = f"trend:{geo}:{keyword}"
        cached = await cache_service.get_json(cache_key)
        if cached:
            try:
                return TrendAlert.model_validate(cached)
            except Exception:
                pass

        try:
            gemini = ai_service._get_gemini()
            if not gemini:
                return TrendAlert(
                    keyword=keyword,
                    source_signals=trend_data["source_signals"],
                    strength=trend_data["strength"],
                    category=trend_data.get("category", "general"),
                    geography=trend_data.get("geography", geo),
                    reason=f"تصاعد اهتمام الجمهور بموضوع {keyword} في {GEO_LABELS.get(trend_data.get('geography', geo), geo)}.",
                    suggested_angles=[
                        f"ما الذي يدفع صعود {keyword} الآن؟",
                        f"كيف يؤثر {keyword} على الجمهور محليًا؟",
                    ],
                )

            prompt = f"""Role: Chief editorial trend analyst for Echorouk.
Language: Arabic.
Keyword: {keyword}
Category: {trend_data.get("category", "general")}
Geography target: {trend_data.get("geography", geo)}
Source signals: {', '.join(trend_data['source_signals'])}

Return strict JSON:
{{
  "reason": "لماذا يصعد هذا الترند الآن؟ (جملة قصيرة)",
  "relevant": true,
  "angles": ["زاوية تحريرية 1", "زاوية تحريرية 2"],
  "archive_keywords": ["كلمة1", "كلمة2"]
}}"""

            import json
            model = gemini.GenerativeModel(settings.gemini_model_flash)
            response = model.generate_content(prompt)
            result_text = response.text.strip()
            if result_text.startswith("```"):
                result_text = result_text.split("\n", 1)[1]
                result_text = result_text.rsplit("```", 1)[0]

            data = json.loads(result_text)
            await cache_service.increment_counter("ai_calls_today")
            angles = data.get("angles", []) or []
            reason = (data.get("reason") or "").strip()
            if (not data.get("relevant", True)) or (not reason and len(angles) < 2):
                return None

            alert = TrendAlert(
                keyword=keyword,
                source_signals=trend_data["source_signals"],
                strength=trend_data["strength"],
                category=trend_data.get("category", "general"),
                geography=trend_data.get("geography", geo),
                reason=reason,
                suggested_angles=angles,
                archive_matches=data.get("archive_keywords", []),
            )
            await cache_service.set_json(cache_key, alert.model_dump(mode="json"), ttl=timedelta(minutes=30))
            return alert
        except Exception as e:
            logger.warning("trend_analysis_error", keyword=keyword, error=str(e))
            return TrendAlert(
                keyword=keyword,
                source_signals=trend_data["source_signals"],
                strength=trend_data["strength"],
                category=trend_data.get("category", "general"),
                geography=trend_data.get("geography", geo),
                reason=f"إشارة ترند مؤكدة حول {keyword} وتحتاج متابعة تحريرية سريعة.",
                suggested_angles=[
                    f"الخلفية الخبرية وراء {keyword}",
                    f"زاوية بيانات/تأثير مرتبطة بـ {keyword}",
                ],
            )

    async def _send_alert(self, alert: TrendAlert):
        """Send trend alert to editorial team."""
        stars = "🔥" * min(alert.strength // 2, 5)
        angles_text = "\n".join([f"  • {a}" for a in alert.suggested_angles]) if alert.suggested_angles else "  -"
        archive_text = ", ".join(alert.archive_matches) if alert.archive_matches else "-"
        geo_label = GEO_LABELS.get(alert.geography, alert.geography)

        message = (
            f"🚨 <b>ترند صاعد:</b> {alert.keyword}\n\n"
            f"📍 الجغرافيا: {geo_label}\n"
            f"🧭 التصنيف: {alert.category}\n"
            f"📊 قوة الزخم: {stars} ({alert.strength}/10)\n"
            f"📡 المصادر: {', '.join(alert.source_signals)}\n\n"
            f"💡 <b>السبب:</b> {alert.reason or 'تحليل غير متوفر'}\n\n"
            f"📝 <b>مقترحات العناوين:</b>\n{angles_text}\n\n"
            f"📚 <b>بحث في الأرشيف:</b> {archive_text}"
        )
        await notification_service.send_telegram(message)


trend_radar_agent = TrendRadarAgent()
