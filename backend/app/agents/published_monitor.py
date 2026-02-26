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
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import aiohttp
import feedparser
from bs4 import BeautifulSoup

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.ai_service import ai_service
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
    "الذى": "الذي",
    "هاذا": "هذا",
    "هاذه": "هذه",
    "فى": "في",
    "الى": "إلى",
}

WHO_HINTS = {"الرئيس", "الوزير", "الوزارة", "الحكومة", "الجيش", "الوكالة", "مصدر", "مسؤول", "شركة"}
WHAT_HINTS = {"أعلن", "أعلنت", "أكد", "كشفت", "قرار", "بيان", "اتفاق", "نتائج", "تحقيق"}
WHERE_HINTS = {"الجزائر", "ولاية", "العاصمة", "محلية", "دولية", "أفريقيا", "غزة"}
WHEN_HINTS = {"اليوم", "أمس", "غدا", "هذا الأسبوع", "هذا الشهر", "خلال", "بتاريخ"}

STRONG_KEYWORDS = {"بيان", "قرار", "رسمي", "إحصائيات", "وثيقة", "مصدر", "أرقام", "تأكيد"}

EDITORIAL_QUALITY_PROMPT = """
أنت مدقق جودة تحريرية وإملائية محترف لبوابة أخبار عربية.
قيّم المادة التالية دون مجاملة وبمعايير غرفة أخبار احترافية.

المطلوب:
1) رصد أخطاء إملائية/نحوية أو صياغات غير صحفية.
2) رصد مشاكل مهنية: تهويل، غموض، ضعف إسناد، قفزات استنتاجية.
3) تقديم اقتراحات تحريرية عملية وقابلة للتنفيذ فورًا.
4) إعطاء تعديل رقمي على الدرجة score_adjustment من -15 إلى +5 فقط.

أعد JSON فقط بالشكل:
{
  "issues": ["..."],
  "suggestions": ["..."],
  "score_adjustment": -3,
  "checks": {
    "spelling": 0,
    "style": 0,
    "structure": 0,
    "accuracy": 0
  }
}

قواعد صارمة:
- لا تضف أي نص خارج JSON.
- إذا لم تكتشف ملاحظة في محور معين، اتركه بدرجة عالية بدون اختلاق مشاكل.
- ركّز على جودة التحرير الصحفي الفعلي، لا على الانطباعات العامة.
"""


class PublishedContentMonitorAgent:
    CACHE_KEY = "published_monitor:last"

    @staticmethod
    def _normalize_title_for_dedup(title: str) -> str:
        return re.sub(r"\s+", " ", (title or "").strip().lower())

    @staticmethod
    def _normalize_url_for_dedup(url: str) -> str:
        raw = (url or "").strip()
        if not raw:
            return ""
        try:
            parsed = urlparse(raw)
            filtered_query = [
                (k, v)
                for k, v in parse_qsl(parsed.query, keep_blank_values=False)
                if not k.lower().startswith("utm_")
                and k.lower() not in {"fbclid", "gclid", "igshid", "oc", "hl", "gl", "ceid"}
            ]
            normalized = parsed._replace(
                scheme=(parsed.scheme or "https").lower(),
                netloc=parsed.netloc.lower(),
                query=urlencode(filtered_query, doseq=True),
                fragment="",
            )
            return urlunparse(normalized).rstrip("/")
        except Exception:
            return raw.lower().rstrip("/")

    def _deduplicate_feed_entries(self, entries: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
        seen: set[str] = set()
        unique_entries: list[dict[str, Any]] = []
        for entry in entries:
            normalized_url = self._normalize_url_for_dedup(entry.get("link", ""))
            normalized_title = self._normalize_title_for_dedup(entry.get("title", ""))
            signature = f"{normalized_url}|{normalized_title}"
            if signature in seen:
                continue
            seen.add(signature)
            unique_entries.append(entry)
            if len(unique_entries) >= limit:
                break
        return unique_entries

    async def scan(self, feed_url: str | None = None, limit: int | None = None) -> dict[str, Any]:
        feed_url = (feed_url or settings.published_monitor_feed_url).strip()
        limit = max(1, min(limit or settings.published_monitor_limit, 30))
        timeout_total = max(6, settings.published_monitor_fetch_timeout)

        entries = await self._fetch_feed_entries(feed_url=feed_url, timeout_total=timeout_total)
        unique_entries = self._deduplicate_feed_entries(entries, limit)
        audits: list[dict[str, Any]] = []

        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector, headers={"User-Agent": "EchoroukSwarm/1.0"}) as session:
            for idx, entry in enumerate(unique_entries):
                title = (entry.get("title") or "").strip()
                summary = self._strip_html(entry.get("summary") or entry.get("description") or "")
                url = (entry.get("link") or "").strip()
                published_at = entry.get("published", "") or entry.get("updated", "")
                body_text = await self._fetch_article_text(session, url, timeout_total=timeout_total)
                audits.append(
                    await self._audit_entry(
                        title=title,
                        summary=summary,
                        body_text=body_text,
                        url=url,
                        published_at=published_at,
                        use_llm=(idx < max(0, settings.published_monitor_llm_items_limit)),
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
            "total_feed_entries": len(entries),
            "duplicates_filtered": max(0, len(entries) - len(unique_entries)),
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

    @staticmethod
    def _extend_unique(target: list[str], values: list[str], *, max_items: int) -> None:
        for value in values:
            clean = re.sub(r"\s+", " ", str(value or "").strip())
            if not clean or clean in target:
                continue
            target.append(clean)
            if len(target) >= max_items:
                return

    async def _llm_editorial_review(
        self,
        *,
        title: str,
        summary: str,
        body_text: str,
        first_chunk: str,
    ) -> dict[str, Any] | None:
        prompt = (
            f"{EDITORIAL_QUALITY_PROMPT}\n\n"
            f"العنوان: {title[:240]}\n"
            f"الملخص: {summary[:700]}\n"
            f"الفقرة الافتتاحية: {first_chunk[:700]}\n"
            f"مقتطف من المتن: {(body_text or summary)[:1800]}\n"
        )
        try:
            data = await ai_service.generate_json(prompt)
        except Exception as exc:  # noqa: BLE001
            logger.warning("published_monitor_llm_error", error=str(exc))
            return None

        if not isinstance(data, dict):
            return None
        issues = [str(x).strip() for x in (data.get("issues") or []) if str(x).strip()]
        suggestions = [str(x).strip() for x in (data.get("suggestions") or []) if str(x).strip()]
        if not issues and not suggestions:
            return None

        try:
            score_adjustment = int(float(data.get("score_adjustment", 0)))
        except Exception:
            score_adjustment = 0
        score_adjustment = max(-15, min(5, score_adjustment))

        checks_raw = data.get("checks") if isinstance(data.get("checks"), dict) else {}
        checks: dict[str, int] = {}
        for key in ("spelling", "style", "structure", "accuracy"):
            try:
                checks[key] = max(0, min(100, int(float(checks_raw.get(key, 0)))))
            except Exception:
                checks[key] = 0

        return {
            "issues": issues[:5],
            "suggestions": suggestions[:5],
            "score_adjustment": score_adjustment,
            "checks": checks,
        }

    async def _audit_entry(
        self,
        *,
        title: str,
        summary: str,
        body_text: str,
        url: str,
        published_at: str,
        use_llm: bool = True,
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
            issues.append(f"مؤشرات تهويل/Clickbait: {', '.join(clickbait_hits[:3])}")
            suggestions.append("استبدال الصياغة المثيرة بعنوان خبري مباشر ودقيق.")

        spelling_hits = []
        for wrong, correct in COMMON_SPELLING_MISTAKES.items():
            if wrong in lowered_text or wrong in lowered_title:
                spelling_hits.append((wrong, correct))
        if spelling_hits:
            score -= min(24, len(spelling_hits) * 4)
            issues.append("أخطاء إملائية شائعة مرصودة.")
            suggestions.append("إجراء مراجعة إملائية نهائية واعتماد الصيغة القياسية للأسماء والمصطلحات.")

        title_len = len(title_clean)
        if title_len < 35:
            score -= 8
            issues.append("العنوان قصير جداً لتحسين SEO.")
            suggestions.append("رفع طول العنوان إلى 35-75 حرفاً مع الحفاظ على الوضوح.")
        elif title_len > 95:
            score -= 10
            issues.append("العنوان طويل ويضعف القراءة.")
            suggestions.append("اختصار العنوان مع إبراز الفاعل والحدث.")

        if word_count < 180:
            score -= 12
            issues.append("المحتوى قصير ولا يغطي الخبر بشكل كافٍ.")
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

        llm_checks: dict[str, int] | None = None
        if use_llm and (title_clean or text):
            llm_review = await self._llm_editorial_review(
                title=title_clean,
                summary=summary_clean,
                body_text=body_text,
                first_chunk=first_chunk,
            )
            if llm_review:
                self._extend_unique(issues, llm_review.get("issues", []), max_items=8)
                self._extend_unique(suggestions, llm_review.get("suggestions", []), max_items=8)
                score += int(llm_review.get("score_adjustment", 0))
                llm_checks = llm_review.get("checks")

        score = max(0, min(100, score))
        grade = self._grade(score)

        metrics: dict[str, Any] = {
            "title_length": title_len,
            "word_count": word_count,
            "clickbait_hits": len(clickbait_hits),
            "spelling_hits": len(spelling_hits),
            "strong_keywords_hits": strong_kw_hits,
        }
        if llm_checks:
            metrics["llm_checks"] = llm_checks

        suggestions = self._practical_suggestions(issues, suggestions)

        return {
            "title": title_clean,
            "url": url,
            "published_at": published_at,
            "score": score,
            "grade": grade,
            "issues": issues,
            "suggestions": suggestions,
            "metrics": metrics,
        }

    @staticmethod
    def _practical_suggestions(issues: list[str], suggestions: list[str]) -> list[str]:
        practical: list[str] = []

        def add(value: str) -> None:
            clean = re.sub(r"\s+", " ", (value or "").strip())
            if not clean or clean in practical:
                return
            practical.append(clean)

        for issue in issues:
            normalized = (issue or "").lower()
            if "clickbait" in normalized or "تهويل" in normalized:
                add("استبدل صياغة الإثارة بمعلومة مباشرة تتضمن الجهة والنتيجة.")
            if "إملائ" in normalized or "املائ" in normalized or "spelling" in normalized:
                add("طبّق تدقيقًا إملائيًا نهائيًا وصحّح الكلمات المشار إليها قبل النشر.")
            if "العنوان قصير" in normalized:
                add("وسّع العنوان إلى 35-75 حرفًا بإضافة الفاعل والأثر المباشر.")
            if "العنوان طويل" in normalized:
                add("اختصر العنوان واحذف الحشو مع الإبقاء على الفاعل والفعل الرئيسيين.")
            if "المحتوى قصير" in normalized:
                add("أضف فقرة خلفية وفقرة أرقام/تصريحات موثقة من مصدر رسمي.")
            if "الهرم" in normalized:
                add("أعد صياغة المقدمة لتتضمن: من/ماذا/أين/متى في أول جملة.")
            if "الكلمات المفتاحية" in normalized:
                add("أدرج مصطلحين خبريين دقيقين في العنوان والفقرة الأولى دون تهويل.")

        vague_markers = {"تحسين", "جودة", "أفضل", "بشكل عام", "صياغة جيدة", "راجع النص"}
        for suggestion in suggestions:
            normalized = (suggestion or "").strip().lower()
            if not normalized:
                continue
            if any(marker in normalized for marker in vague_markers) and len(normalized.split()) < 7:
                continue
            add(suggestion)

        if not practical:
            add("نفّذ مراجعة تحريرية سريعة للعنوان والمقدمة والإسناد قبل إعادة النشر.")

        return practical[:6]

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
