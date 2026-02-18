"""
Published Content Monitor Agent
-------------------------------
Monitors quality of already-published content from RSS feed using
editorial constitution rules (spelling, style, clickbait, structure).
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any

import aiohttp
import feedparser
from bs4 import BeautifulSoup

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.cache_service import cache_service
from app.services.notification_service import notification_service

logger = get_logger("agent.published_monitor")
settings = get_settings()


CLICKBAIT_TERMS = {
    "لن تصدق",
    "صدمة",
    "فضيحة",
    "كارثة",
    "شاهد الآن",
    "مفاجأة مدوية",
    "يفجر مفاجأة",
    "سر خطير",
    "انكشف المستور",
}

COMMON_SPELLING_MISTAKES = {
    "ان شاء الله": "إن شاء الله",
    "لكنن": "لكن",
    "الذى": "الذي",
    "هاذا": "هذا",
    "هاذه": "هذه",
    "فى": "في",
    "الى": "إلى",
    "مسؤولين": "مراجعة الضبط حسب السياق: مسؤولون / مسؤولين",
}

WHO_HINTS = {
    "الرئيس",
    "الوزير",
    "الوزارة",
    "الحكومة",
    "الجيش",
    "الوكالة",
    "مصدر",
    "مسؤول",
    "شركة",
}
WHAT_HINTS = {
    "أعلن",
    "أعلنت",
    "أكد",
    "كشفت",
    "قرار",
    "بيان",
    "اتفاق",
    "نتائج",
    "تحقيق",
}
WHERE_HINTS = {
    "الجزائر",
    "ولاية",
    "العاصمة",
    "محلية",
    "دولية",
    "أفريقيا",
    "غزة",
}
WHEN_HINTS = {
    "اليوم",
    "أمس",
    "غدا",
    "هذا الأسبوع",
    "هذا الشهر",
    "خلال",
    "بتاريخ",
}

STRONG_KEYWORDS = {
    "بيان",
    "قرار",
    "رسمي",
    "إحصائيات",
    "وثيقة",
    "مصدر",
    "أرقام",
    "تأكيد",
}


class PublishedContentMonitorAgent:
    CACHE_KEY = "published_monitor:last"

    async def scan(self, feed_url: str | None = None, limit: int | None = None) -> dict[str, Any]:
        feed_url = (feed_url or settings.published_monitor_feed_url).strip()
        limit = max(1, min(limit or settings.published_monitor_limit, 30))
        timeout_total = max(6, settings.published_monitor_fetch_timeout)

        entries = await self._fetch_feed_entries(feed_url=feed_url, timeout_total=timeout_total)
        audits: list[dict[str, Any]] = []

        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector, headers={"User-Agent": "EchoroukSwarm/1.0"}) as session:
            for entry in entries[:limit]:
                title = (entry.get("title") or "").strip()
                summary = self._strip_html(entry.get("summary") or entry.get("description") or "")
                url = (entry.get("link") or "").strip()
                published_at = entry.get("published", "") or entry.get("updated", "")
                body_text = await self._fetch_article_text(session, url, timeout_total=timeout_total)
                audits.append(
                    self._audit_entry(
                        title=title,
                        summary=summary,
                        body_text=body_text,
                        url=url,
                        published_at=published_at,
                    )
                )

        avg_score = round(sum(item["score"] for item in audits) / max(1, len(audits)), 2)
        weak_items = [item for item in audits if item["score"] < settings.published_monitor_alert_threshold]
        issues_count = sum(len(item["issues"]) for item in audits)

        report: dict[str, Any] = {
            "feed_url": feed_url,
            "executed_at": datetime.utcnow().isoformat(),
            "interval_minutes": settings.published_monitor_interval_minutes,
            "total_items": len(audits),
            "average_score": avg_score,
            "weak_items_count": len(weak_items),
            "issues_count": issues_count,
            "status": "alert" if weak_items else "ok",
            "items": audits,
        }

        ttl = timedelta(minutes=max(20, settings.published_monitor_interval_minutes * 3))
        await cache_service.set_json(self.CACHE_KEY, report, ttl=ttl)

        if weak_items:
            await notification_service.send_published_quality_alert(report)

        logger.info(
            "published_monitor_scan_complete",
            total_items=len(audits),
            average_score=avg_score,
            weak_items=len(weak_items),
            issues_count=issues_count,
        )
        return report

    async def latest(self) -> dict[str, Any] | None:
        return await cache_service.get_json(self.CACHE_KEY)

    async def _fetch_feed_entries(self, feed_url: str, timeout_total: int) -> list[dict[str, Any]]:
        try:
            async with aiohttp.ClientSession(headers={"User-Agent": "EchoroukSwarm/1.0"}) as session:
                async with session.get(feed_url, timeout=aiohttp.ClientTimeout(total=timeout_total)) as resp:
                    if resp.status != 200:
                        logger.warning("published_monitor_feed_http_error", status=resp.status, feed_url=feed_url)
                        return []
                    content = await resp.text()
        except Exception as exc:  # noqa: BLE001
            logger.error("published_monitor_feed_error", feed_url=feed_url, error=str(exc))
            return []

        parsed = feedparser.parse(content)
        entries: list[dict[str, Any]] = []
        for item in parsed.entries:
            entries.append(
                {
                    "title": item.get("title", ""),
                    "summary": item.get("summary", item.get("description", "")),
                    "link": item.get("link", ""),
                    "published": item.get("published", item.get("updated", "")),
                }
            )
        return entries

    async def _fetch_article_text(self, session: aiohttp.ClientSession, url: str, timeout_total: int) -> str:
        if not url:
            return ""
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout_total), allow_redirects=True) as resp:
                if resp.status != 200:
                    return ""
                html = await resp.text()
        except Exception:
            return ""
        return self._extract_text_from_html(html)

    @staticmethod
    def _strip_html(value: str) -> str:
        return BeautifulSoup(value or "", "html.parser").get_text(" ", strip=True)

    @staticmethod
    def _extract_text_from_html(html: str) -> str:
        soup = BeautifulSoup(html or "", "html.parser")
        paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
        text = "\n".join(p for p in paragraphs if p)
        return re.sub(r"\s+", " ", text).strip()

    def _audit_entry(
        self,
        *,
        title: str,
        summary: str,
        body_text: str,
        url: str,
        published_at: str,
    ) -> dict[str, Any]:
        score = 100
        issues: list[str] = []
        suggestions: list[str] = []

        title_clean = (title or "").strip()
        summary_clean = (summary or "").strip()
        text = f"{summary_clean} {body_text}".strip()
        lowered_text = text.lower()
        lowered_title = title_clean.lower()
        word_count = len(re.findall(r"\S+", body_text or summary_clean))

        clickbait_hits = [term for term in CLICKBAIT_TERMS if term in lowered_title or term in lowered_text]
        if clickbait_hits:
            score -= min(30, len(clickbait_hits) * 8)
            issues.append(f"مؤشرات Clickbait: {', '.join(clickbait_hits[:3])}")
            suggestions.append("استبدال الصياغة المثيرة بعنوان خبري مباشر ودقيق.")

        spelling_hits = []
        for wrong, correct in COMMON_SPELLING_MISTAKES.items():
            if wrong in lowered_text or wrong in lowered_title:
                spelling_hits.append((wrong, correct))
        if spelling_hits:
            score -= min(24, len(spelling_hits) * 4)
            issues.append("أخطاء إملائية شائعة مرصودة.")
            suggestions.append("مراجعة إملائية نهائية قبل النشر واعتماد الصيغة القياسية للأسماء.")

        title_len = len(title_clean)
        if title_len < 35:
            score -= 8
            issues.append("العنوان قصير جدا لتحسين SEO.")
            suggestions.append("رفع طول العنوان إلى 35-75 حرفا مع الحفاظ على الوضوح.")
        elif title_len > 95:
            score -= 10
            issues.append("العنوان طويل ويضعف القراءة.")
            suggestions.append("اختصار العنوان مع إبراز الفاعل والحدث.")

        if word_count < 180:
            score -= 12
            issues.append("المحتوى قصير ولا يغطي الخبر بشكل كاف.")
            suggestions.append("إضافة تفاصيل أساسية وسياق داعم من مصادر موثوقة.")

        first_chunk = self._first_chunk(body_text, summary_clean)
        missing_pyramid = self._missing_inverted_pyramid(first_chunk)
        if missing_pyramid:
            score -= min(16, len(missing_pyramid) * 4)
            issues.append(f"نقص في عناصر الهرم الإخباري: {', '.join(missing_pyramid)}")
            suggestions.append("تقوية الفقرة الافتتاحية بعناصر: من/ماذا/أين/متى.")

        strong_kw_hits = sum(1 for kw in STRONG_KEYWORDS if kw in (title_clean + " " + text))
        if strong_kw_hits < 2:
            score -= 6
            issues.append("ضعف في الكلمات المفتاحية التحريرية القوية.")
            suggestions.append("تعزيز المصطلحات الخبرية الدقيقة في العنوان والفقرة الأولى.")

        score = max(0, min(100, score))
        grade = self._grade(score)

        return {
            "title": title_clean,
            "url": url,
            "published_at": published_at,
            "score": score,
            "grade": grade,
            "issues": issues,
            "suggestions": suggestions,
            "metrics": {
                "title_length": title_len,
                "word_count": word_count,
                "clickbait_hits": len(clickbait_hits),
                "spelling_hits": len(spelling_hits),
                "strong_keywords_hits": strong_kw_hits,
            },
        }

    @staticmethod
    def _first_chunk(body_text: str, summary: str) -> str:
        if body_text:
            parts = re.split(r"[.\n]+", body_text)
            return (parts[0] or "").strip()
        return (summary or "").strip()

    @staticmethod
    def _missing_inverted_pyramid(first_chunk: str) -> list[str]:
        chunk = first_chunk or ""
        missing = []
        if not any(hint in chunk for hint in WHO_HINTS):
            missing.append("من")
        if not any(hint in chunk for hint in WHAT_HINTS):
            missing.append("ماذا")
        if not any(hint in chunk for hint in WHERE_HINTS):
            missing.append("أين")
        if not any(hint in chunk for hint in WHEN_HINTS):
            missing.append("متى")
        return missing

    @staticmethod
    def _grade(score: int) -> str:
        if score >= 90:
            return "ممتاز"
        if score >= 75:
            return "جيد"
        if score >= 60:
            return "مقبول"
        return "ضعيف"


published_content_monitor_agent = PublishedContentMonitorAgent()
