from __future__ import annotations

import asyncio
import re
import time
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

import aiohttp
from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models import Article, ArticleQualityReport, EditorialDraft

logger = get_logger("quality_gate_service")

TRANSITION_WORDS_AR = {
    "لكن", "بالمقابل", "في المقابل", "إضافة إلى", "من جهة", "من ناحية", "بالتالي", "لذلك", "علاوة على ذلك",
}
PASSIVE_PATTERNS_AR = [
    r"\bتم\b",
    r"\bيتم\b",
    r"\bأُعلن\b",
    r"\bأُكد\b",
    r"\bأُشير\b",
]
TRUSTED_EXTERNAL_HINTS = ["reuters", "bbc", "apnews", "france24", "who.int", "worldbank", "imf.org", "un.org"]


class QualityGateService:
    async def save_report(
        self,
        db: AsyncSession,
        *,
        article_id: int,
        stage: str,
        passed: bool,
        score: int | None,
        blocking_reasons: list[str],
        actionable_fixes: list[str],
        report_json: dict[str, Any],
        created_by: str | None = None,
    ) -> ArticleQualityReport:
        row = ArticleQualityReport(
            article_id=article_id,
            stage=stage,
            passed=1 if passed else 0,
            score=score,
            blocking_reasons=blocking_reasons,
            actionable_fixes=actionable_fixes,
            report_json=report_json,
            created_by=created_by,
            created_at=datetime.utcnow(),
        )
        db.add(row)
        await db.flush()
        return row

    def readability_report(self, text: str) -> dict[str, Any]:
        clean = (text or "").strip()
        paragraphs = [p.strip() for p in re.split(r"\n+", clean) if p.strip()]
        sentences = [s.strip() for s in re.split(r"[.!؟;\n]+", clean) if s.strip()]
        sentence_lengths = [len(re.findall(r"\S+", s)) for s in sentences] or [0]
        avg_sentence_len = sum(sentence_lengths) / max(1, len(sentence_lengths))
        long_sentence_ratio = sum(1 for n in sentence_lengths if n > 25) / max(1, len(sentence_lengths))

        passive_hits = 0
        for p in PASSIVE_PATTERNS_AR:
            passive_hits += len(re.findall(p, clean))
        passive_ratio = passive_hits / max(1, len(sentences))

        para_word_lengths = [len(re.findall(r"\S+", p)) for p in paragraphs] or [0]
        long_paragraph_count = sum(1 for n in para_word_lengths if n > 120)
        transitions_count = sum(clean.count(w) for w in TRANSITION_WORDS_AR)

        score = 100
        score -= min(35, int(max(0.0, avg_sentence_len - 18) * 2))
        score -= min(25, int(long_sentence_ratio * 100 * 0.8))
        score -= min(20, int(passive_ratio * 100 * 0.6))
        score -= min(20, long_paragraph_count * 8)
        score = max(0, score)

        blocking: list[str] = []
        fixes: list[str] = []
        if avg_sentence_len > 24:
            blocking.append("متوسط طول الجملة مرتفع")
            fixes.append("قسّم الجمل الطويلة إلى جمل أقصر (15-22 كلمة)")
        if long_sentence_ratio > 0.35:
            blocking.append("نسبة الجمل الطويلة أعلى من المعيار")
            fixes.append("أعد صياغة الفقرات بجمل قصيرة مباشرة")
        if passive_ratio > 0.30:
            fixes.append("خفض المبني للمجهول وفضّل الصياغة المباشرة بالفعل والفاعل")
        if long_paragraph_count > 0:
            fixes.append("قسّم الفقرات الطويلة إلى فقرات أقصر")
        if transitions_count < 2:
            fixes.append("أضف كلمات انتقالية لتحسين السلاسة بين الفقرات")

        passed = len(blocking) == 0
        return {
            "stage": "READABILITY_PASSED" if passed else "DRAFT_READY",
            "passed": passed,
            "score": score,
            "metrics": {
                "avg_sentence_len": round(avg_sentence_len, 2),
                "long_sentence_ratio": round(long_sentence_ratio, 3),
                "passive_ratio": round(passive_ratio, 3),
                "long_paragraph_count": long_paragraph_count,
                "transitions_count": transitions_count,
            },
            "blocking_reasons": blocking,
            "actionable_fixes": fixes,
        }

    async def technical_audit(self, db: AsyncSession, article: Article) -> dict[str, Any]:
        body = (article.body_html or "").strip()
        if not body:
            latest_draft_res = await db.execute(
                select(EditorialDraft)
                .where(EditorialDraft.article_id == article.id)
                .order_by(EditorialDraft.updated_at.desc(), EditorialDraft.id.desc())
                .limit(1)
            )
            latest_draft = latest_draft_res.scalar_one_or_none()
            body = (latest_draft.body or "").strip() if latest_draft else ""

        soup = BeautifulSoup(body, "html.parser")
        plain_text = soup.get_text(" ", strip=True) if body else ""

        seo_title = (article.seo_title or article.title_ar or article.original_title or "").strip()
        seo_desc = (article.seo_description or article.summary or "").strip()
        slug_source = article.published_url or article.original_url or ""
        slug = urlparse(slug_source).path.strip("/").split("/")[-1] if slug_source else ""

        h1_count = len(soup.find_all("h1")) if body else 0
        h2_count = len(soup.find_all("h2")) if body else 0
        h3_count = len(soup.find_all("h3")) if body else 0

        imgs = soup.find_all("img") if body else []
        imgs_missing_alt = sum(1 for img in imgs if not (img.get("alt") or "").strip())

        links = soup.find_all("a", href=True) if body else []
        internal_links = [a for a in links if "echoroukonline.com" in a["href"] or a["href"].startswith("/")]
        external_links = [a for a in links if a["href"].startswith("http") and a not in internal_links]
        trusted_external = sum(1 for a in external_links if any(h in a["href"].lower() for h in TRUSTED_EXTERNAL_HINTS))

        keyword = ""
        m = re.search(r"[\u0600-\u06FFA-Za-z]{3,}", seo_title)
        if m:
            keyword = m.group(0).lower()
        density = 0.0
        if keyword and plain_text:
            words = re.findall(r"\S+", plain_text.lower())
            hits = sum(1 for w in words if keyword in w)
            density = hits / max(1, len(words))

        blocking: list[str] = []
        fixes: list[str] = []
        if not body:
            blocking.append("محتوى المقال فارغ")
            fixes.append("أنشئ مسودة نهائية قبل النشر")
        if not seo_title:
            blocking.append("SEO Title مفقود")
            fixes.append("أضف عنوان SEO بطول 30-65 حرفًا")
        if seo_title and not (30 <= len(seo_title) <= 65):
            blocking.append("SEO Title خارج الطول الموصى به")
        if not seo_desc:
            blocking.append("Meta Description مفقود")
        if seo_desc and not (80 <= len(seo_desc) <= 170):
            fixes.append("عدّل Meta Description ليكون بين 80 و170 حرفًا")
        if not slug or not re.fullmatch(r"[a-z0-9\-_/%.]+", slug.lower()):
            blocking.append("Slug غير نظيف أو مفقود")
        if h1_count != 1:
            blocking.append("يجب وجود H1 واحد فقط")
        if h3_count > 0 and h2_count == 0:
            fixes.append("يفضل ترتيب العناوين H2 قبل H3")
        if imgs and imgs_missing_alt > 0:
            blocking.append("بعض الصور بدون ALT")
        if len(internal_links) < 1:
            fixes.append("أضف رابطًا داخليًا واحدًا على الأقل")
        if len(external_links) > 0 and trusted_external < 1:
            fixes.append("يفضل إضافة رابط خارجي لمصدر موثوق")
        if density > 0.02:
            fixes.append("خفّض تكرار الكلمة المفتاحية (Keyword stuffing)")

        passed = len(blocking) == 0
        score = max(0, 100 - len(blocking) * 18 - len(fixes) * 4)
        return {
            "stage": "SEO_TECH_PASSED" if passed else "DRAFT_READY",
            "passed": passed,
            "score": score,
            "metrics": {
                "seo_title_len": len(seo_title),
                "meta_description_len": len(seo_desc),
                "h1_count": h1_count,
                "h2_count": h2_count,
                "h3_count": h3_count,
                "images_count": len(imgs),
                "images_missing_alt": imgs_missing_alt,
                "internal_links": len(internal_links),
                "external_links": len(external_links),
                "trusted_external_links": trusted_external,
                "keyword_density": round(density, 4),
            },
            "blocking_reasons": blocking,
            "actionable_fixes": fixes,
        }

    async def guardian_check(self, url: str) -> dict[str, Any]:
        url = (url or "").strip()
        if not url:
            return {
                "stage": "PUBLISHED",
                "passed": False,
                "score": 0,
                "blocking_reasons": ["رابط المنشور غير متوفر"],
                "actionable_fixes": ["احفظ رابط النشر ثم أعد الفحص"],
                "metrics": {},
            }

        headers = {"User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"}
        blocking: list[str] = []
        fixes: list[str] = []
        metrics: dict[str, Any] = {"url": url}

        try:
            timeout = aiohttp.ClientTimeout(total=20)
            start = time.perf_counter()
            async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                async with session.get(url, allow_redirects=True) as resp:
                    html = await resp.text(errors="ignore")
                    ttfb_ms = int((time.perf_counter() - start) * 1000)
                    metrics["status_code"] = resp.status
                    metrics["ttfb_ms"] = ttfb_ms
                    metrics["final_url"] = str(resp.url)

            soup = BeautifulSoup(html, "html.parser")
            robots = (soup.find("meta", attrs={"name": "robots"}) or {}).get("content", "")
            canonical = (soup.find("link", rel="canonical") or {}).get("href", "")
            og_title = (soup.find("meta", property="og:title") or {}).get("content", "")
            og_type = (soup.find("meta", property="og:type") or {}).get("content", "")

            metrics["has_canonical"] = bool(canonical)
            metrics["robots"] = robots
            metrics["has_og_title"] = bool(og_title)
            metrics["has_og_type"] = bool(og_type)

            if metrics["status_code"] != 200:
                blocking.append("Status code ليس 200")
            if "noindex" in (robots or "").lower():
                blocking.append("الصفحة تحمل وسم noindex")
            if not canonical:
                blocking.append("canonical مفقود")
            if not og_title:
                fixes.append("أضف OG title")
            if not og_type:
                fixes.append("أضف OG type")
            if ttfb_ms > 2500:
                fixes.append("زمن الاستجابة مرتفع، راجع الأداء/الكاش")
        except Exception as e:
            logger.warning("guardian_check_failed", url=url, error=str(e))
            return {
                "stage": "PUBLISHED",
                "passed": False,
                "score": 0,
                "blocking_reasons": [f"فشل الزحف: {e}"],
                "actionable_fixes": ["تحقق من الرابط والخادم ثم أعد الفحص"],
                "metrics": metrics,
            }

        passed = len(blocking) == 0
        score = max(0, 100 - len(blocking) * 20 - len(fixes) * 5)
        return {
            "stage": "POST_PUBLISH_VERIFIED" if passed else "PUBLISHED",
            "passed": passed,
            "score": score,
            "blocking_reasons": blocking,
            "actionable_fixes": fixes,
            "metrics": metrics,
        }

    async def guardian_check_with_retry(self, db: AsyncSession, article: Article, created_by: str | None = None) -> None:
        url = article.published_url or article.original_url or ""
        report = await self.guardian_check(url)
        await self.save_report(
            db,
            article_id=article.id,
            stage="POST_PUBLISH",
            passed=bool(report["passed"]),
            score=report.get("score"),
            blocking_reasons=report.get("blocking_reasons", []),
            actionable_fixes=report.get("actionable_fixes", []),
            report_json=report,
            created_by=created_by,
        )
        await db.commit()

        if not report["passed"]:
            await asyncio.sleep(30 * 60)
            retry = await self.guardian_check(url)
            await self.save_report(
                db,
                article_id=article.id,
                stage="POST_PUBLISH_RETRY",
                passed=bool(retry["passed"]),
                score=retry.get("score"),
                blocking_reasons=retry.get("blocking_reasons", []),
                actionable_fixes=retry.get("actionable_fixes", []),
                report_json=retry,
                created_by=created_by,
            )
            await db.commit()


quality_gate_service = QualityGateService()

