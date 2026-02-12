"""
Echorouk AI Swarm — Trend Radar Agent (رادار التراند)
=======================================================
Content Intelligence: Detects rising trends by cross-
referencing Google Trends, RSS burst detection, and
social signals.

Algorithm: Semantic Intersection across multiple sources.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional
from collections import Counter

import aiohttp
import feedparser

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.ai_service import ai_service
from app.services.cache_service import cache_service
from app.services.notification_service import notification_service
from app.schemas import TrendAlert
from app.utils.hashing import normalize_text

logger = get_logger("agent.trend_radar")
settings = get_settings()

# Google Trends RSS for Algeria
GOOGLE_TRENDS_URL = "https://trends.google.com/trends/trendingsearches/daily/rss?geo=DZ"

# Competitor RSS feeds for cross-referencing
COMPETITOR_FEEDS = [
    "https://www.echoroukonline.com/feed/",
    "https://www.elkhabar.com/feed/",
    "https://www.ennaharonline.com/feed/",
    "https://www.tsa-algerie.com/feed/",
    "https://www.aps.dz/xml/rss",
]


class TrendRadarAgent:
    """
    Trend Radar — detects verified trends using cross-platform validation.
    A trend is "verified" only if it appears in multiple sources simultaneously.
    """

    async def scan(self) -> list[TrendAlert]:
        """Run a full trend scan cycle."""
        try:
            # ── Phase 1: Multi-Source Scanning ──
            google_trends = await self._fetch_google_trends()
            competitor_keywords = await self._fetch_competitor_keywords()
            rss_bursts = await self._detect_rss_bursts()

            # ── Phase 2: Cross-Platform Verification ──
            verified_trends = self._cross_validate(
                google_trends,
                competitor_keywords,
                rss_bursts,
            )

            if not verified_trends:
                logger.info("no_verified_trends")
                return []

            # ── Phase 3: AI Contextual Analysis ──
            alerts = []
            for trend in verified_trends[:5]:  # Limit to top 5
                alert = await self._analyze_trend(trend)
                if alert:
                    alerts.append(alert)

            # ── Phase 4: Distribution ──
            for alert in alerts:
                await self._send_alert(alert)

            logger.info("trend_scan_complete", verified=len(verified_trends), alerts=len(alerts))
            return alerts

        except Exception as e:
            logger.error("trend_scan_error", error=str(e))
            return []

    async def _fetch_google_trends(self) -> list[str]:
        """Fetch trending searches from Google Trends (DZ region)."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(GOOGLE_TRENDS_URL, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status != 200:
                        return []
                    content = await resp.text()
                    feed = feedparser.parse(content)
                    return [normalize_text(entry.title) for entry in feed.entries if entry.title]
        except Exception as e:
            logger.warning("google_trends_error", error=str(e))
            return []

    async def _fetch_competitor_keywords(self) -> list[str]:
        """Extract keywords from competitor headlines."""
        keywords = []
        try:
            async with aiohttp.ClientSession() as session:
                for url in COMPETITOR_FEEDS:
                    try:
                        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                            if resp.status == 200:
                                content = await resp.text()
                                feed = feedparser.parse(content)
                                for entry in feed.entries[:10]:
                                    title = normalize_text(entry.get("title", ""))
                                    if title:
                                        words = title.split()
                                        keywords.extend([w for w in words if len(w) > 3])
                    except Exception:
                        continue
        except Exception as e:
            logger.warning("competitor_fetch_error", error=str(e))

        return keywords

    async def _detect_rss_bursts(self) -> list[str]:
        """
        Burst Detection: Find keywords that suddenly appear
        in multiple sources within a short timeframe.
        """
        # Get recent titles from cache
        recent_titles = await cache_service.get_recent_titles(100)
        if not recent_titles:
            return []

        # Tokenize and count
        word_counts = Counter()
        for title in recent_titles:
            normalized = normalize_text(title)
            words = [w for w in normalized.split() if len(w) > 3]
            word_counts.update(words)

        # Words that appear in 3+ different titles = burst
        bursts = [word for word, count in word_counts.items() if count >= 3]
        return bursts

    def _cross_validate(
        self,
        google_trends: list[str],
        competitor_keywords: list[str],
        rss_bursts: list[str],
    ) -> list[dict]:
        """
        Core Algorithm: Semantic Intersection.
        A trend is verified if it appears in at least 2 different sources.
        This eliminates fake/manufactured trends.
        """
        verified = []

        all_google = set(google_trends)
        competitor_set = set(competitor_keywords)
        burst_set = set(rss_bursts)

        for trend in all_google:
            sources = ["google_trends"]
            trend_words = trend.split()

            # Check if any word from the trend appears in competitors
            for word in trend_words:
                if word in competitor_set:
                    sources.append("competitors")
                    break

            # Check if any word appears in RSS bursts
            for word in trend_words:
                if word in burst_set:
                    sources.append("rss_burst")
                    break

            # Verified = appears in 2+ sources
            if len(sources) >= 2:
                verified.append({
                    "keyword": trend,
                    "source_signals": sources,
                    "strength": min(len(sources) * 3 + 2, 10),
                })

        # Also check RSS bursts against competitor keywords
        for burst_word in rss_bursts:
            if burst_word in competitor_set and burst_word not in [v["keyword"] for v in verified]:
                verified.append({
                    "keyword": burst_word,
                    "source_signals": ["rss_burst", "competitors"],
                    "strength": 6,
                })

        # Sort by strength
        verified.sort(key=lambda x: x["strength"], reverse=True)
        return verified

    async def _analyze_trend(self, trend_data: dict) -> Optional[TrendAlert]:
        """Use AI to analyze a verified trend and suggest editorial angles."""
        keyword = trend_data["keyword"]

        # Check if we already analyzed this trend recently
        cache_key = f"trend:{keyword}"
        cached = await cache_service.get(cache_key)
        if cached:
            return None  # Already analyzed

        try:
            gemini = ai_service._get_gemini()
            if not gemini:
                return TrendAlert(
                    keyword=keyword,
                    source_signals=trend_data["source_signals"],
                    strength=trend_data["strength"],
                )

            prompt = f"""Role: Senior Editor at Echorouk Online (Algeria).
Task: Analyze this viral keyword data.

Keyword: {keyword}
Source Signals: {', '.join(trend_data['source_signals'])}

Instructions:
1. Why is this trending NOW in Algeria?
2. Is this relevant to news/sports/culture?
3. Provide 2 journalistic angles suitable for Echorouk's audience.
4. Suggest search terms to find related content in our archive.

Output Format (JSON only):
{{
  "reason": "Brief explanation in Arabic",
  "relevant": true/false,
  "angles": ["Angle 1", "Angle 2"],
  "archive_keywords": ["keyword1", "keyword2"]
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

            if not data.get("relevant", True):
                return None

            # Cache this analysis for 30 minutes
            from datetime import timedelta
            await cache_service.set(cache_key, "analyzed", ttl=timedelta(minutes=30))

            return TrendAlert(
                keyword=keyword,
                source_signals=trend_data["source_signals"],
                strength=trend_data["strength"],
                reason=data.get("reason", ""),
                suggested_angles=data.get("angles", []),
                archive_matches=data.get("archive_keywords", []),
            )

        except Exception as e:
            logger.warning("trend_analysis_error", keyword=keyword, error=str(e))
            return TrendAlert(
                keyword=keyword,
                source_signals=trend_data["source_signals"],
                strength=trend_data["strength"],
            )

    async def _send_alert(self, alert: TrendAlert):
        """Send trend alert to editorial team."""
        stars = "🔥" * min(alert.strength // 2, 5)
        angles_text = "\n".join([f"  • {a}" for a in alert.suggested_angles]) if alert.suggested_angles else "  -"
        archive_text = ", ".join(alert.archive_matches) if alert.archive_matches else "-"

        message = (
            f"🚨 <b>تراند صاعد:</b> {alert.keyword}\n\n"
            f"📊 قوة الزخم: {stars} ({alert.strength}/10)\n"
            f"📡 المصادر: {', '.join(alert.source_signals)}\n\n"
            f"💡 <b>السبب:</b> {alert.reason or 'تحليل غير متوفر'}\n\n"
            f"📝 <b>مقترحات العناوين:</b>\n{angles_text}\n\n"
            f"📚 <b>بحث في الأرشيف:</b> {archive_text}"
        )

        await notification_service.send_telegram(message)


# Singleton
trend_radar_agent = TrendRadarAgent()
