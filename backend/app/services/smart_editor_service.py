from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import bleach
from bs4 import BeautifulSoup

ALLOWED_TAGS = [
    "p",
    "h1",
    "h2",
    "h3",
    "strong",
    "em",
    "ul",
    "ol",
    "li",
    "blockquote",
    "a",
    "br",
]

ALLOWED_ATTRS = {
    "a": ["href", "target", "rel"],
}

OPINION_WORDS_AR = {
    "فضيحة",
    "كارثة",
    "صادم",
    "مذهل",
    "مهزلة",
    "خطير جدا",
}

CLAIM_TRIGGER_WORDS_AR = {
    "قال",
    "أعلن",
    "صرح",
    "أكد",
    "كشف",
    "ذكر",
    "نقل",
    "أفاد",
}

SIDE_COMMENT_PATTERNS = [
    r"(?im)^\s*(حسنًا|حسنا|إليك|ملاحظات|ملاحظة|آمل|يمكنني|إذا كان لديك)\b.*$",
    r"(?im)^\s*(based on|note|explanation|comments?)\b.*$",
]

TEMPLATE_NOISE_PATTERNS = [
    r"\[[^\]]{2,120}\]",
    r"\bمثال\b",
    r"\bالبند\s+\d+\b",
    r"\?{3,}",
    r"(?i)\btemplate\b",
]


@dataclass
class DiffResult:
    diff: str
    added: int
    removed: int


class SmartEditorService:
    @staticmethod
    def _get_ai_service():
        try:
            from app.services.ai_service import ai_service

            return ai_service
        except Exception:
            return None

    @staticmethod
    def _contains_html(value: str) -> bool:
        return bool(re.search(r"<[a-zA-Z][^>]*>", value or ""))

    @staticmethod
    def _strip_side_comments(value: str) -> str:
        text = (value or "").strip()
        for pattern in SIDE_COMMENT_PATTERNS:
            text = re.sub(pattern, "", text)
        text = text.replace("```html", "").replace("```", "")
        text = re.sub(r"(?m)^\s*[-*]\s+", "", text)
        text = re.sub(r"\n{3,}", "\n\n", text).strip()
        return text

    @staticmethod
    def _contains_template_noise(text: str) -> bool:
        sample = text or ""
        return any(re.search(pattern, sample) for pattern in TEMPLATE_NOISE_PATTERNS)

    @staticmethod
    def _normalize_slug(value: str) -> str:
        text = re.sub(r"[^\w\u0600-\u06FF\s-]", " ", (value or "").lower())
        text = re.sub(r"\s+", "-", text.strip())
        text = re.sub(r"-{2,}", "-", text)
        return text.strip("-")[:90]

    @staticmethod
    def _ensure_meta_length(value: str, fallback: str, min_len: int = 140, max_len: int = 155) -> str:
        text = re.sub(r"\s+", " ", (value or "").strip())
        backup = re.sub(r"\s+", " ", (fallback or "").strip())
        if not text:
            text = backup
        if len(text) > max_len:
            return text[: max_len - 3].rstrip() + "..."
        if len(text) >= min_len:
            return text
        combined = f"{text} {backup}".strip()
        combined = re.sub(r"\s+", " ", combined)
        if len(combined) < min_len:
            pad = " تفاصيل إضافية وخلفيات الخبر في التغطية الكاملة."
            while len(combined) < min_len:
                combined = f"{combined} {pad}".strip()
                combined = re.sub(r"\s+", " ", combined)
        if len(combined) > max_len:
            combined = combined[: max_len - 3].rstrip() + "..."
        return combined

    @staticmethod
    def _uniq(values: list[str], limit: int) -> list[str]:
        out: list[str] = []
        seen: set[str] = set()
        for value in values:
            key = re.sub(r"\s+", " ", value.strip().lower())
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(value.strip())
            if len(out) >= limit:
                break
        return out

    @staticmethod
    def _text_to_html(title: str, text: str) -> str:
        lines = [line.strip() for line in re.split(r"\n+", text or "") if line.strip()]
        if not lines:
            return f"<h1>{title}</h1><p></p>"
        body = "\n".join(f"<p>{line}</p>" for line in lines)
        return f"<h1>{title}</h1>\n{body}"

    def sanitize_html(self, value: str) -> str:
        cleaned = bleach.clean(
            value or "",
            tags=ALLOWED_TAGS,
            attributes=ALLOWED_ATTRS,
            protocols=["http", "https", "mailto"],
            strip=True,
        )
        cleaned = re.sub(
            r'href\s*=\s*["\']\s*javascript:[^"\']*["\']',
            'href="#"',
            cleaned,
            flags=re.IGNORECASE,
        )
        return cleaned.strip()

    @staticmethod
    def html_to_text(value: str) -> str:
        if not value:
            return ""
        soup = BeautifulSoup(value, "html.parser")
        return soup.get_text(" ", strip=True)

    @staticmethod
    def build_diff(old_text: str, new_text: str) -> DiffResult:
        old_lines = (old_text or "").splitlines()
        new_lines = (new_text or "").splitlines()
        diff_lines = list(
            difflib.unified_diff(
                old_lines,
                new_lines,
                fromfile="before",
                tofile="after",
                lineterm="",
                n=2,
            )
        )
        added = sum(1 for line in diff_lines if line.startswith("+") and not line.startswith("+++"))
        removed = sum(1 for line in diff_lines if line.startswith("-") and not line.startswith("---"))
        return DiffResult(diff="\n".join(diff_lines), added=added, removed=removed)

    @staticmethod
    def _local_proofread_text(text: str) -> tuple[str, list[dict[str, Any]]]:
        fixed = text or ""
        issues: list[dict[str, Any]] = []

        double_space_matches = re.findall(r"[ \t]{2,}", fixed)
        if double_space_matches:
            issues.append(
                {
                    "kind": "spacing",
                    "message": "تم رصد مسافات زائدة داخل النص.",
                    "count": len(double_space_matches),
                }
            )
            fixed = re.sub(r"[ \t]{2,}", " ", fixed)

        space_before_punct = re.findall(r"\s+[،؛:,.!?؟]", fixed)
        if space_before_punct:
            issues.append(
                {
                    "kind": "punctuation",
                    "message": "تم رصد مسافة قبل علامات الترقيم.",
                    "count": len(space_before_punct),
                }
            )
            fixed = re.sub(r"\s+([،؛:,.!?؟])", r"\1", fixed)

        missing_space_after_punct = re.findall(r"([،؛:,.!?؟])([^\s\n])", fixed)
        if missing_space_after_punct:
            issues.append(
                {
                    "kind": "punctuation",
                    "message": "تم رصد غياب مسافة بعد بعض علامات الترقيم.",
                    "count": len(missing_space_after_punct),
                }
            )
            fixed = re.sub(r"([،؛:,.!?؟])([^\s\n])", r"\1 \2", fixed)

        latin_comma_matches = re.findall(r"(?<=[\u0600-\u06FF]),(?=[\u0600-\u06FF])", fixed)
        if latin_comma_matches:
            issues.append(
                {
                    "kind": "spelling",
                    "message": "تم رصد استخدام فاصلة لاتينية داخل سياق عربي.",
                    "count": len(latin_comma_matches),
                }
            )
            fixed = re.sub(r"(?<=[\u0600-\u06FF]),(?=[\u0600-\u06FF])", "،", fixed)

        repeated_punct = re.findall(r"([،؛:,.!?؟]){2,}", fixed)
        if repeated_punct:
            issues.append(
                {
                    "kind": "punctuation",
                    "message": "تم رصد تكرار علامات ترقيم متتالية.",
                    "count": len(repeated_punct),
                }
            )
            fixed = re.sub(r"([،؛:,.!?؟]){2,}", r"\1", fixed)

        fixed = re.sub(r"[ \t]+\n", "\n", fixed)
        fixed = re.sub(r"\n[ \t]+", "\n", fixed)
        fixed = re.sub(r"\n{3,}", "\n\n", fixed).strip()
        return fixed, issues

    @staticmethod
    def _normalize_proofread_issues(value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []
        out: list[dict[str, Any]] = []
        for item in value:
            if isinstance(item, dict):
                out.append(
                    {
                        "kind": str(item.get("kind") or "language").strip()[:40],
                        "message": str(item.get("message") or item.get("issue") or "").strip()[:280],
                        "before": str(item.get("before") or "").strip()[:280],
                        "after": str(item.get("after") or "").strip()[:280],
                        "count": item.get("count"),
                    }
                )
            elif isinstance(item, str):
                out.append({"kind": "language", "message": item.strip()[:280], "before": "", "after": "", "count": None})
        return [x for x in out if x.get("message")]

    async def rewrite_suggestion(
        self,
        *,
        source_text: str,
        draft_title: str,
        draft_html: str,
        mode: str = "formal",
        instruction: str = "",
    ) -> dict[str, Any]:
        prompt = f"""
أنت مساعد تحرير صحفي داخل غرفة أخبار الشروق.
المطلوب: إعادة صياغة النص بصياغة عربية صحفية واضحة فقط.

أعد JSON فقط بالمفاتيح:
title, body_html, note

قواعد إلزامية:
- لا تضف أي معلومة غير موجودة في السياق.
- ممنوع أي تعليقات جانبية مثل: ملاحظة، مثال، يمكنني، آمل.
- body_html يجب أن يحتوي H1 واحد فقط، ثم فقرات HTML نظيفة.
- لا تستخدم markdown ولا code fences.

النمط: {mode}
تعليمات إضافية: {instruction or "لا يوجد"}

السياق:
{source_text[:7000]}

العنوان الحالي:
{draft_title}

المتن الحالي:
{draft_html[:10000]}
"""
        ai = self._get_ai_service()
        data = await ai.generate_json(prompt) if ai else {}
        title = str(data.get("title") or draft_title or "").strip() or "عنوان الخبر"
        candidate = str(data.get("body_html") or draft_html or "").strip()
        note = str(data.get("note") or f"rewrite_mode:{mode}").strip()

        candidate = self._strip_side_comments(candidate)
        if not self._contains_html(candidate):
            candidate = self._text_to_html(title, candidate)
        if "<h1" not in candidate.lower():
            candidate = f"<h1>{title}</h1>\n{candidate}"

        sanitized = self.sanitize_html(candidate)
        before_text = self.html_to_text(draft_html)
        after_text = self.html_to_text(sanitized)
        diff_text = self.build_diff(before_text, after_text)
        diff_html = self.build_diff(draft_html, sanitized)
        return {
            "title": title,
            "body_html": sanitized,
            "body_text": after_text,
            "note": note,
            "diff": diff_text.diff,
            "diff_html": diff_html.diff,
            "diff_stats": {"added": diff_text.added, "removed": diff_text.removed},
            "preview": {
                "before_text": before_text[:1400],
                "after_text": after_text[:1400],
            },
            "generated_at": datetime.utcnow().isoformat(),
        }

    async def proofread_suggestion(
        self,
        *,
        source_text: str,
        draft_title: str,
        draft_html: str,
    ) -> dict[str, Any]:
        plain_before = self.html_to_text(draft_html)
        local_after_text, local_issues = self._local_proofread_text(plain_before)
        local_html = self._text_to_html(draft_title or "نسخة منقحة", local_after_text) if local_after_text else draft_html

        prompt = f"""
أنت مدقق لغوي وصحفي في غرفة أخبار.
المطلوب: تدقيق إملائي ونحوي وترقيمي لنص عربي جاهز للنشر.

أعد JSON فقط بالمفاتيح:
title, body_html, note, issues

شروط إلزامية:
- body_html يجب أن يكون HTML صالحاً مع H1 واحد وفقرة/فقرات واضحة.
- لا تضف معلومات جديدة غير موجودة في النص الأصلي.
- أصلح فقط: الإملاء، النحو، الترقيم، وضوح الصياغة.
- issues يجب أن تكون قائمة مختصرة بعناصر من الشكل:
  kind, message, before, after
- ممنوع أي شروحات خارج JSON.

العنوان الحالي:
{draft_title}

النص الحالي:
{draft_html[:10000]}

السياق:
{source_text[:4000]}
"""
        ai = self._get_ai_service()
        data = await ai.generate_json(prompt) if ai else {}
        title = str(data.get("title") or draft_title or "").strip() or "نسخة منقحة"
        candidate = str(data.get("body_html") or "").strip()
        note = str(data.get("note") or "proofread").strip()

        if not candidate:
            candidate = local_html
        candidate = self._strip_side_comments(candidate)
        if not self._contains_html(candidate):
            candidate = self._text_to_html(title, candidate)
        if "<h1" not in candidate.lower():
            candidate = f"<h1>{title}</h1>\n{candidate}"

        sanitized = self.sanitize_html(candidate)
        after_text = self.html_to_text(sanitized)

        issues = self._normalize_proofread_issues(data.get("issues"))
        if not issues:
            issues = local_issues

        diff_text = self.build_diff(plain_before, after_text)
        diff_html = self.build_diff(draft_html, sanitized)
        return {
            "title": title,
            "body_html": sanitized,
            "body_text": after_text,
            "note": note,
            "issues": issues,
            "diff": diff_text.diff,
            "diff_html": diff_html.diff,
            "diff_stats": {"added": diff_text.added, "removed": diff_text.removed},
            "preview": {
                "before_text": plain_before[:1400],
                "after_text": after_text[:1400],
            },
            "generated_at": datetime.utcnow().isoformat(),
        }

    async def headline_suggestions(self, *, source_text: str, draft_title: str) -> list[dict[str, str]]:
        prompt = f"""
أنت محرر عناوين في الشروق.
أعد 5 عناوين فقط بصيغة JSON array.
كل عنصر يجب أن يحتوي:
label, headline

الترتيب:
official, breaking, seo, engaging, mobile_short

بدون أي نص إضافي.

السياق:
{source_text[:5000]}

العنوان الحالي:
{draft_title}
"""
        ai = self._get_ai_service()
        data = await ai.generate_json(prompt) if ai else {}
        if isinstance(data, list):
            out: list[dict[str, str]] = []
            for item in data[:5]:
                out.append(
                    {
                        "label": str(item.get("label") or "").strip(),
                        "headline": self._strip_side_comments(str(item.get("headline") or "").strip()),
                    }
                )
            if len(out) == 5 and all(x["headline"] for x in out):
                return out

        base = draft_title or "عنوان مقترح"
        return [
            {"label": "official", "headline": base},
            {"label": "breaking", "headline": f"عاجل | {base}"},
            {"label": "seo", "headline": base},
            {"label": "engaging", "headline": base},
            {"label": "mobile_short", "headline": base[:55]},
        ]

    async def seo_suggestions(self, *, source_text: str, draft_title: str, draft_html: str) -> dict[str, Any]:
        prompt = f"""
You are a newsroom SEO editor. Return production-ready Yoast SEO fields.
Return JSON only with keys:
seo_title, meta_description, focus_keyphrase, secondary_keyphrases, keywords, tags, slug, og_title, og_description, twitter_title, twitter_description

Mandatory rules:
- seo_title must be clear, journalistic, 50-60 chars.
- meta_description must be between 140 and 155 chars.
- focus_keyphrase must be one concise phrase.
- secondary_keyphrases must contain 3 items.
- keywords must contain 6 items.
- tags must contain 6 items.
- slug must be kebab-case.
- og/twitter fields should be publish-ready and non-clickbait.
- no explanations outside JSON.

Headline:
{draft_title}

Body:
{draft_html[:9000]}

Context:
{source_text[:4000]}
"""
        ai = self._get_ai_service()
        data = await ai.generate_json(prompt) if ai else {}

        plain_text = self.html_to_text(draft_html)
        fallback_meta = f"{draft_title}. {plain_text[:260]}".strip()

        seo_title = self._strip_side_comments(str(data.get("seo_title") or draft_title or "").strip())[:60]
        meta = self._strip_side_comments(str(data.get("meta_description") or "").strip())
        meta = self._ensure_meta_length(meta, fallback_meta, min_len=140, max_len=155)

        focus_keyphrase = self._strip_side_comments(str(data.get("focus_keyphrase") or "").strip())
        if not focus_keyphrase:
            focus_keyphrase = self._strip_side_comments((draft_title or "").split(" - ")[0].strip())

        secondary = data.get("secondary_keyphrases") or []
        keywords = data.get("keywords") or []
        tags = data.get("tags") or []
        if not isinstance(secondary, list):
            secondary = []
        if not isinstance(keywords, list):
            keywords = []
        if not isinstance(tags, list):
            tags = []

        secondary = self._uniq([self._strip_side_comments(str(x)) for x in secondary], 3)
        keywords = self._uniq([self._strip_side_comments(str(x)) for x in keywords], 6)
        tags = self._uniq([self._strip_side_comments(str(x)) for x in tags], 6)

        if not keywords:
            tokens = re.findall(r"[؀-ۿA-Za-z]{4,}", plain_text)
            keywords = self._uniq(tokens, 6)
        if not tags:
            tags = keywords[:6]

        slug_raw = self._strip_side_comments(str(data.get("slug") or "").strip())
        slug = self._normalize_slug(slug_raw or draft_title or focus_keyphrase)

        og_title = self._strip_side_comments(str(data.get("og_title") or seo_title).strip())[:65]
        og_description = self._ensure_meta_length(
            self._strip_side_comments(str(data.get("og_description") or meta).strip()),
            meta,
            min_len=140,
            max_len=155,
        )
        twitter_title = self._strip_side_comments(str(data.get("twitter_title") or og_title).strip())[:65]
        twitter_description = self._ensure_meta_length(
            self._strip_side_comments(str(data.get("twitter_description") or og_description).strip()),
            og_description,
            min_len=140,
            max_len=155,
        )

        return {
            "seo_title": seo_title,
            "meta_description": meta,
            "focus_keyphrase": focus_keyphrase,
            "secondary_keyphrases": secondary,
            "keywords": keywords,
            "tags": tags,
            "slug": slug,
            "og_title": og_title,
            "og_description": og_description,
            "twitter_title": twitter_title,
            "twitter_description": twitter_description,
            "yoast": {
                "meta_length": len(meta),
                "meta_ok": 140 <= len(meta) <= 155,
                "title_length": len(seo_title),
                "title_ok": 40 <= len(seo_title) <= 60,
            },
        }

    async def social_variants(self, *, source_text: str, draft_title: str, draft_html: str) -> dict[str, str]:
        prompt = f"""
أنت محرر منصات اجتماعية في غرفة أخبار.
أعد JSON فقط بالمفاتيح:
facebook, x, push, summary_120, breaking_alert

الشروط:
- عربية واضحة ومحترفة.
- بدون تعليقات جانبية.
- push بين 15 و18 كلمة.
- summary_120 قرابة 120 كلمة.

العنوان:
{draft_title}

المتن:
{draft_html[:9000]}

السياق:
{source_text[:3000]}
"""
        ai = self._get_ai_service()
        data = await ai.generate_json(prompt) if ai else {}
        out: dict[str, str] = {}
        for key in ["facebook", "x", "push", "summary_120", "breaking_alert"]:
            out[key] = self._strip_side_comments(str(data.get(key) or "").strip())
        return out

    def extract_claims(self, *, text: str, source_url: str | None = None) -> list[dict[str, Any]]:
        sentences = [s.strip() for s in re.split(r"[.!؟\n]+", text or "") if s.strip()]
        claims: list[dict[str, Any]] = []
        for idx, sentence in enumerate(sentences, start=1):
            has_number = bool(re.search(r"\d", sentence))
            has_date = bool(re.search(r"\b(20\d{2}|19\d{2})\b", sentence))
            has_statement = any(trigger in sentence for trigger in CLAIM_TRIGGER_WORDS_AR)
            has_quote = '"' in sentence or "«" in sentence or "”" in sentence
            if not (has_number or has_date or has_statement or has_quote):
                continue

            claim_type = "statement"
            if has_number:
                claim_type = "number"
            elif has_date:
                claim_type = "date"

            confidence = 0.55
            if has_statement:
                confidence += 0.15
            if has_quote:
                confidence += 0.10
            if has_number or has_date:
                confidence += 0.10
            if source_url:
                confidence += 0.05
            confidence = min(confidence, 0.95)

            claims.append(
                {
                    "id": f"clm-{idx}",
                    "text": sentence,
                    "claim_type": claim_type,
                    "confidence": round(confidence, 2),
                    "blocking": confidence < 0.70,
                    "verify_hint": "تحقق من المصدر الرسمي أو وكالة موثوقة",
                    "evidence_links": [source_url] if source_url else [],
                }
            )
        return claims

    def fact_check_report(self, *, text: str, source_url: str | None = None, threshold: float = 0.70) -> dict[str, Any]:
        clean_text = self._strip_side_comments(text or "")
        template_noise = self._contains_template_noise(clean_text)
        claims = self.extract_claims(text=clean_text, source_url=source_url)
        unresolved = [c for c in claims if c["confidence"] < threshold]

        blocking_reasons: list[str] = []
        actionable_fixes: list[str] = []
        if template_noise:
            blocking_reasons.append("النص يحتوي قوالب أو تعليقات جانبية وغير صالح للنشر")
            actionable_fixes.append("استخدم زر تحسين الصياغة لإزالة القوالب والتعليقات")
        if unresolved:
            blocking_reasons.append("توجد ادعاءات غير مؤكدة تحت الحد المطلوب")
            actionable_fixes.append("تحقق من الادعاءات منخفضة الثقة قبل طلب النشر")

        passed = not blocking_reasons
        score = max(0, 100 - len(unresolved) * 20 - (30 if template_noise else 0))
        return {
            "stage": "FACT_CHECK_PASSED" if passed else "FACT_CHECK_BLOCKED",
            "passed": passed,
            "score": score,
            "claims": claims,
            "blocking_reasons": blocking_reasons,
            "actionable_fixes": actionable_fixes,
            "threshold": threshold,
        }

    def quality_score(self, *, title: str, html: str, source_text: str = "") -> dict[str, Any]:
        text = self.html_to_text(html)
        words = re.findall(r"\S+", text)
        sentences = [s.strip() for s in re.split(r"[.!؟\n]+", text) if s.strip()]
        sentence_lengths = [len(re.findall(r"\S+", s)) for s in sentences] or [0]
        avg_sentence = sum(sentence_lengths) / max(1, len(sentence_lengths))

        clarity = max(0, min(100, int(100 - max(0.0, avg_sentence - 20) * 4)))
        structure = 100 if "<h1" in (html or "").lower() else 60
        if "<h2" in (html or "").lower():
            structure = min(100, structure + 15)

        lead = sentences[0] if sentences else ""
        lead_score = 0
        if re.search(r"\d", lead):
            lead_score += 25
        if any(x in lead for x in ["في", "اليوم", "أمس", "الجزائر", "حسب"]):
            lead_score += 25
        if len(lead.split()) >= 12:
            lead_score += 25
        if title:
            lead_score += 25
        inverted_pyramid = lead_score

        duplicates = 0
        seen: set[str] = set()
        for sentence in sentences:
            key = re.sub(r"\s+", " ", sentence).strip()
            if key in seen:
                duplicates += 1
            seen.add(key)
        redundancy = max(0, 100 - duplicates * 20)

        length_score = 100
        if len(words) < 140:
            length_score = 60
        elif len(words) > 700:
            length_score = 70

        neutral_penalty = sum(12 for word in OPINION_WORDS_AR if word in text.lower())
        tone_neutrality = max(0, 100 - neutral_penalty)
        source_citations = len(re.findall(r"(قال|أعلن|بحسب|وفق|ذكرت|الوزارة|الهيئة|بيان)", text))
        source_presence = min(100, source_citations * 20)

        total = int(
            clarity * 0.18
            + structure * 0.14
            + inverted_pyramid * 0.16
            + redundancy * 0.14
            + length_score * 0.12
            + tone_neutrality * 0.14
            + source_presence * 0.12
        )

        fixes: list[str] = []
        if clarity < 75:
            fixes.append("قصّر الجمل الطويلة لتحسين الوضوح.")
        if structure < 80:
            fixes.append("أضف عنوانًا رئيسيًا H1 واحدًا مع عنوان فرعي H2 على الأقل.")
        if inverted_pyramid < 70:
            fixes.append("قوِّ الفقرة الأولى بعناصر: ماذا/من/أين/متى.")
        if source_presence < 60:
            fixes.append("أضف إسنادًا واضحًا للمصادر داخل النص.")
        if tone_neutrality < 85:
            fixes.append("أزل الأوصاف الانفعالية وحافظ على الحياد.")

        passed = total >= 70
        return {
            "stage": "QUALITY_SCORE",
            "passed": passed,
            "score": total,
            "metrics": {
                "clarity": clarity,
                "structure": structure,
                "inverted_pyramid": inverted_pyramid,
                "redundancy": redundancy,
                "length_suitability": length_score,
                "tone_neutrality": tone_neutrality,
                "sources_attribution": source_presence,
                "word_count": len(words),
            },
            "blocking_reasons": [] if passed else ["درجة الجودة أقل من الحد المطلوب للنشر."],
            "actionable_fixes": fixes,
            "source_excerpt": source_text[:280],
        }

    async def editorial_policy_review(
        self,
        *,
        title: str,
        body_html: str,
        source_text: str,
        readability_report: dict[str, Any] | None = None,
        quality_report: dict[str, Any] | None = None,
        fact_report: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        body_text = self.html_to_text(body_html or "")
        reasons: list[str] = []
        required_fixes: list[str] = []

        if not body_text.strip():
            reasons.append("المتن فارغ أو غير صالح للتحرير.")
            required_fixes.append("أعد تحرير متن الخبر قبل طلب الاعتماد.")
        if self._contains_template_noise(body_text):
            reasons.append("تم رصد نصوص قالبية أو تعليقات جانبية داخل المتن.")
            required_fixes.append("احذف القوالب والتعليقات الجانبية ثم أعد الإرسال.")

        fact_blockers = (fact_report or {}).get("blocking_reasons") or []
        if fact_blockers:
            reasons.append("تقرير التحقق يحتوي على موانع يجب معالجتها.")
            required_fixes.append("عالج ادعاءات التحقق منخفضة الثقة قبل الاعتماد.")

        quality_blockers = (quality_report or {}).get("blocking_reasons") or []
        if quality_blockers:
            reasons.append("تقرير الجودة يشير إلى مشاكل تحريرية مؤثرة.")
            required_fixes.extend((quality_report or {}).get("actionable_fixes") or [])

        readability_blockers = (readability_report or {}).get("blocking_reasons") or []
        if readability_blockers:
            reasons.append("قابلية القراءة غير مطابقة لمعيار التحرير.")
            required_fixes.extend((readability_report or {}).get("actionable_fixes") or [])

        baseline_decision = "approved" if not reasons else "reservations"
        baseline_confidence = 0.86 if baseline_decision == "approved" else 0.72

        prompt = f"""
أنت وكيل السياسة التحريرية للشروق.
أعد JSON فقط بالمفاتيح:
decision, reasons, required_fixes, confidence

شروط القرار:
- decision = approved أو reservations
- إذا النص يحتوي ادعاءات غير محسومة أو صياغة غير مهنية: reservations
- ممنوع أي شروحات خارج JSON

العنوان:
{title}

المتن:
{body_text[:8000]}

السياق المصدر:
{source_text[:2500]}

نتيجة أولية داخلية:
decision={baseline_decision}
reasons={reasons}
required_fixes={required_fixes}
"""
        ai = self._get_ai_service()
        data: dict[str, Any] = {}
        if ai:
            try:
                raw = await ai.generate_json(prompt)
                if isinstance(raw, dict):
                    data = raw
            except Exception:
                data = {}

        decision = str(data.get("decision") or baseline_decision).strip().lower()
        if decision not in {"approved", "reservations"}:
            decision = baseline_decision

        ai_reasons = data.get("reasons") if isinstance(data.get("reasons"), list) else []
        ai_fixes = data.get("required_fixes") if isinstance(data.get("required_fixes"), list) else []
        merged_reasons = [self._strip_side_comments(str(x).strip()) for x in [*reasons, *ai_reasons] if str(x).strip()]
        merged_fixes = [self._strip_side_comments(str(x).strip()) for x in [*required_fixes, *ai_fixes] if str(x).strip()]
        merged_reasons = list(dict.fromkeys(merged_reasons))[:10]
        merged_fixes = list(dict.fromkeys(merged_fixes))[:10]

        confidence_raw = data.get("confidence", baseline_confidence)
        try:
            confidence = float(confidence_raw)
        except Exception:
            confidence = baseline_confidence
        confidence = max(0.0, min(1.0, confidence))

        if merged_reasons and decision == "approved":
            # Keep deterministic safety: any blocking reason means reservations.
            decision = "reservations"

        return {
            "stage": "EDITORIAL_POLICY",
            "decision": decision,
            "passed": decision == "approved",
            "confidence": round(confidence, 3),
            "score": int(round(confidence * 100)),
            "reasons": merged_reasons,
            "required_fixes": merged_fixes,
            "blocking_reasons": merged_reasons if decision == "reservations" else [],
            "actionable_fixes": merged_fixes,
        }


smart_editor_service = SmartEditorService()
