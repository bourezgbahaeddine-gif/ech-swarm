from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import bleach
from bs4 import BeautifulSoup

try:
    from app.services.ai_service import ai_service
except Exception:  # pragma: no cover - optional AI backend
    ai_service = None

try:
    from app.services.fact_check_tools_service import fact_check_tools_service
except Exception:  # pragma: no cover - optional external service
    fact_check_tools_service = None

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

STYLE_RULES = [
    {
        "id": "avoid_qam_ba",
        "pattern": r"\bقام(?:ت|وا|ن)?\s+ب",
        "message": "صياغة ثقيلة تعتمد على «قام بـ».",
        "rule": "يُفضّل استخدام الفعل المباشر بدل «قام بـ».",
        "replacement": "استخدم الفعل المباشر (مثل: زار/افتتح/أعلن).",
        "severity": "medium",
        "confidence": 0.7,
    },
    {
        "id": "avoid_tamma_masdar",
        "pattern": r"\bتم\s+\w+",
        "message": "صياغة مبنية للمجهول «تم + مصدر».",
        "rule": "تجنّب «تم + مصدر» عندما توجد صياغة عربية أقوى.",
        "replacement": "استخدم الفعل المباشر (مثل: أُعلن/أُنشئ/أُقرّ).",
        "severity": "medium",
        "confidence": 0.65,
    },
    {
        "id": "avoid_akkada_bi",
        "pattern": r"\bأكد\s+بأن\b",
        "message": "تركيب غير مفضّل تحريرياً «أكد بأن».",
        "rule": "يُفضّل «أكد أن» بدلاً من «أكد بأن».",
        "replacement": "أكد أن",
        "severity": "low",
        "confidence": 0.8,
    },
    {
        "id": "avoid_da3a_ila_darura",
        "pattern": r"\bدعا\s+إلى\s+ضرورة\b",
        "message": "حشو لغوي في «دعا إلى ضرورة».",
        "rule": "يُفضّل الاختصار: «دعا إلى المشاركة».",
        "replacement": "دعا إلى المشاركة",
        "severity": "low",
        "confidence": 0.75,
    },
]

HEADLINE_VAGUE_PATTERN = r"\b(هذا|هذه|هؤلاء|ذلك|تلك)\b"


@dataclass
class DiffResult:
    diff: str
    added: int
    removed: int


class SmartEditorService:
    @staticmethod
    def _get_ai_service():
        return ai_service

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
    def _ensure_title_length(value: str, fallback: str, min_len: int = 40, max_len: int = 60) -> str:
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
        if len(combined) > max_len:
            combined = combined[: max_len - 3].rstrip() + "..."
        return combined

    @staticmethod
    def _contains_phrase(text: str, phrase: str) -> bool:
        if not text or not phrase:
            return False
        return phrase.strip().lower() in text.strip().lower()

    @staticmethod
    def _ensure_title_with_phrase(title: str, phrase: str, fallback: str, min_len: int, max_len: int) -> str:
        base = re.sub(r"\s+", " ", (title or "").strip())
        if phrase and not SmartEditorService._contains_phrase(base, phrase):
            if base:
                base = f"{phrase} | {base}"
            else:
                base = phrase
        return SmartEditorService._ensure_title_length(base, fallback, min_len=min_len, max_len=max_len)

    @staticmethod
    def _ensure_meta_with_phrase(meta: str, phrase: str, fallback: str, min_len: int, max_len: int) -> str:
        base = re.sub(r"\s+", " ", (meta or "").strip())
        if phrase and not SmartEditorService._contains_phrase(base, phrase):
            base = f"{phrase} - {base}".strip(" -")
        combined = SmartEditorService._ensure_meta_length(base, fallback, min_len=min_len, max_len=max_len)
        if phrase and not SmartEditorService._contains_phrase(combined, phrase):
            trimmed = f"{phrase} - {fallback}".strip(" -")
            combined = SmartEditorService._ensure_meta_length(trimmed, fallback, min_len=min_len, max_len=max_len)
        return combined

    @staticmethod
    def _extract_first_paragraph(html: str, plain_text: str) -> str:
        if not html:
            return (plain_text or "").strip().split("\n")[0]
        soup = BeautifulSoup(html, "html.parser")
        first = soup.find("p")
        if first:
            return first.get_text(" ", strip=True)
        return (plain_text or "").strip().split("\n")[0]

    @staticmethod
    def _extract_headings(html: str) -> list[str]:
        if not html:
            return []
        soup = BeautifulSoup(html, "html.parser")
        headings = [tag.get_text(" ", strip=True) for tag in soup.find_all(["h2", "h3"])]
        return [h for h in headings if h]

    @staticmethod
    def _extract_links(html: str) -> tuple[list[str], list[str]]:
        if not html:
            return [], []
        soup = BeautifulSoup(html, "html.parser")
        hrefs: list[str] = []
        texts: list[str] = []
        for tag in soup.find_all("a"):
            href = str(tag.get("href") or "").strip()
            if href:
                hrefs.append(href)
                texts.append(tag.get_text(" ", strip=True) or "")
        return hrefs, texts

    @staticmethod
    def _extract_images(html: str) -> tuple[int, int]:
        if not html:
            return 0, 0
        soup = BeautifulSoup(html, "html.parser")
        imgs = soup.find_all("img")
        total = len(imgs)
        with_alt = 0
        for img in imgs:
            alt = str(img.get("alt") or "").strip()
            if alt:
                with_alt += 1
        return total, with_alt

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
                        "rule": str(item.get("rule") or "").strip()[:280],
                        "severity": str(item.get("severity") or "").strip()[:32],
                        "confidence": item.get("confidence"),
                    }
                )
            elif isinstance(item, str):
                out.append(
                    {
                        "kind": "language",
                        "message": item.strip()[:280],
                        "before": "",
                        "after": "",
                        "count": None,
                        "rule": "",
                        "severity": "",
                        "confidence": None,
                    }
                )
        return [x for x in out if x.get("message")]

    @staticmethod
    def _dedupe_issues(issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: set[str] = set()
        out: list[dict[str, Any]] = []
        for item in issues or []:
            key = f"{item.get('kind')}::{item.get('message')}::{item.get('before')}"
            if key in seen:
                continue
            seen.add(key)
            out.append(item)
        return out

    @staticmethod
    def _editorial_style_issues(title: str, text: str) -> list[dict[str, Any]]:
        issues: list[dict[str, Any]] = []
        clean_title = (title or "").strip()
        clean_text = (text or "").strip()

        if clean_title and re.search(HEADLINE_VAGUE_PATTERN, clean_title):
            issues.append(
                {
                    "kind": "headline",
                    "message": "العنوان يستخدم ضمير إشارة وقد يكون مبهماً.",
                    "before": clean_title[:160],
                    "after": "",
                    "rule": "العنوان يجب أن يفصح عن العنصر الخبري الأساسي.",
                    "severity": "medium",
                    "confidence": 0.7,
                }
            )
        if clean_title:
            words = re.findall(r"\\S+", clean_title)
            if len(words) < 5 or len(words) > 16:
                issues.append(
                    {
                        "kind": "headline",
                        "message": "طول العنوان غير مناسب (قصير جداً أو طويل جداً).",
                        "before": clean_title[:160],
                        "after": "",
                        "rule": "طول العنوان الصحفي المفضل بين 8 و14 كلمة.",
                        "severity": "low",
                        "confidence": 0.6,
                    }
                )

        for rule in STYLE_RULES:
            for match in re.finditer(rule["pattern"], clean_text):
                snippet = clean_text[max(0, match.start() - 40) : match.end() + 40]
                issues.append(
                    {
                        "kind": "style",
                        "message": rule["message"],
                        "before": snippet[:180],
                        "after": rule.get("replacement", ""),
                        "rule": rule["rule"],
                        "severity": rule["severity"],
                        "confidence": rule["confidence"],
                    }
                )

        sentences = [s.strip() for s in re.split(r"[.!؟\\n]+", clean_text) if s.strip()]
        for sentence in sentences:
            if len(re.findall(r"\\S+", sentence)) >= 35:
                issues.append(
                    {
                        "kind": "clarity",
                        "message": "جملة طويلة قد تُضعف الوضوح وتحتاج اختصاراً.",
                        "before": sentence[:180],
                        "after": "",
                        "rule": "يفضل تقسيم الجمل الطويلة لضمان وضوح القراءة.",
                        "severity": "medium",
                        "confidence": 0.55,
                    }
                )
                break

        return issues

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
أنت محرّر أول في غرفة أخبار الشروق.
المطلوب: تحسين المسودة الحالية تحريرياً ولغوياً دون تغيير المعنى أو اختراع معلومات.

أعد JSON فقط بالمفاتيح:
title, body_html, note

قواعد إلزامية:
- لا تضف أي معلومة غير موجودة في السياق أو المتن الأصلي.
- حافظ على الأسماء والأرقام والتواريخ والاقتباسات كما وردت.
- لا تحذف معلومة أساسية؛ يجوز الاختصار فقط للتكرار والحشو.
- حسّن ترتيب الفقرات وفق الهرم المقلوب: أهم ما في البداية ثم التفاصيل والخلفية.
- جُمَل قصيرة وواضحة، فقرات من 2-4 جمل.
- تجنّب "تم + مصدر" و"قام بـ" متى أمكن.
- ممنوع أي تعليقات جانبية أو شرح خارج النص.
- body_html يجب أن يكون HTML نظيفاً مع H1 واحد فقط ثم فقرات <p>، و<h2> اختياري.
- حافظ على الروابط الموجودة، وأضف رابطاً داخلياً واحداً على الأقل إن لم يوجد (href يبدأ بـ /news أو /).
- حافظ على طول النص قريباً من الأصل (±20%).
- لا تستخدم Markdown ولا code fences.

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
أنت مدقق لغوي وصحفي في غرفة أخبار الشروق.
المطلوب: تدقيق لغوي دقيق للمسودة دون إعادة صياغة شاملة أو تغيير المعنى.

أعد JSON فقط بالمفاتيح:
title, body_html, note, issues

شروط إلزامية:
- لا تضف أي معلومة جديدة غير موجودة في النص الأصلي.
- أصلح فقط: الإملاء، النحو، الترقيم، الاتساق الأسلوبي الخفيف.
- يُسمح باستبدال صيغ ثقيلة (مثل "تم + مصدر" أو "أكد بأن") بصيغ عربية أخف عند الحاجة.
- لا تغيّر ترتيب الفقرات أو بنية الخبر.
- body_html يجب أن يكون HTML صالحاً مع H1 واحد وفقرات واضحة.
- issues قائمة مختصرة بعناصر: kind, message, before, after, rule, severity, confidence.
- kind يجب أن يكون واحداً من: spelling | grammar | punctuation | style | clarity | headline.
- severity واحدة من: critical | high | medium | low.
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
        style_issues = self._editorial_style_issues(title, after_text)
        if style_issues:
            issues = self._dedupe_issues(issues + style_issues)

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

    async def inline_suggestion(
        self,
        *,
        text: str,
        action: str,
        instruction: str = "",
        source_text: str = "",
    ) -> dict[str, Any]:
        action = (action or "rewrite").strip().lower()
        clean_input = (text or "").strip()
        if not clean_input:
            return {"text": ""}

        action_map = {
            "rewrite": "أعد صياغة المقطع بأسلوب صحفي واضح دون تغيير المعنى.",
            "shorten": "اختصر المقطع بنسبة 30-40% مع الحفاظ على كل المعلومات الأساسية.",
            "expand": "وسّع المقطع بشرح إضافي ضمن نفس المعنى دون إضافة حقائق جديدة.",
            "clarify": "بسّط المقطع بجمل أقصر ووضوح أكبر دون تغيير المحتوى.",
        }
        action_prompt = action_map.get(action, action_map["rewrite"])

        prompt = f"""
أنت محرر في غرفة أخبار الشروق.
المطلوب: {action_prompt}

قواعد إلزامية:
- لا تضف أي معلومة جديدة غير موجودة في المقطع أو في السياق.
- حافظ على الأسماء والأرقام والتواريخ كما هي.
- أعد النص الناتج فقط دون شروح أو تعليقات أو تنسيق إضافي.
- لا تستخدم Markdown أو code fences.

السياق (اختياري):
{(source_text or "")[:1500]}

المقطع:
{clean_input}
"""
        ai = self._get_ai_service()
        if not ai:
            return {"text": clean_input}

        raw = await ai.generate_text(prompt)
        cleaned = self._strip_side_comments(raw)
        cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
        if not cleaned or self._contains_template_noise(cleaned):
            cleaned = clean_input
        return {"text": cleaned, "action": action}

    async def headline_suggestions(self, *, source_text: str, draft_title: str) -> list[dict[str, str]]:
        prompt = f"""
        أنت محرر عناوين إخباري محترف باللغة العربية.
        أريد اقتراح 5 عناوين مختلفة للمادة التالية.

        قواعد العناوين:
        - التزم فقط بالمعلومات الموجودة في النص.
        - لا تبالغ ولا تستخدم لغة دعائية.
        - اجعل العنوان واضحًا ومباشرًا.
        - تجنب التكرار والحشو.

        أعد النتيجة على شكل JSON array يحتوي عناصر بالشكل:
        label, headline

        التصنيفات المطلوبة:
        official, breaking, seo, engaging, mobile_short

        شرح التصنيفات:
        - official: عنوان إخباري رسمي من 10 إلى 14 كلمة.
        - breaking: صياغة عاجلة تبدأ بـ "عاجل" إذا كان الخبر مناسبًا.
        - seo: عنوان غني بالكلمات المفتاحية دون تضليل.
        - engaging: عنوان جذاب دون مبالغة.
        - mobile_short: عنوان مختصر مناسب للموبايل (حتى 55 حرفًا).

        النص:
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
        أنت محرر SEO لموقع إخباري باللغة العربية.
        أريد عناصر SEO كاملة للمادة التالية.

        أعد JSON فقط بالمفاتيح:
        seo_title, meta_description, focus_keyphrase, secondary_keyphrases, keywords, tags, slug, og_title, og_description, twitter_title, twitter_description

        قواعد مهمة:
        - التزم بالمحتوى ولا تضف معلومات جديدة.
        - لا تستخدم عبارات دعائية أو مضللة.
        - seo_title بين 50 و60 حرفًا.
        - meta_description بين 140 و155 حرفًا.
        - focus_keyphrase عبارة مركزة واضحة.
        - secondary_keyphrases عددها 3.
        - keywords عددها 6 مفصولة بفواصل.
        - tags عددها 6 قصيرة.
        - slug بصيغة kebab-case.
        - اجعل og/twitter مختصرين وواضحين.
        - أعد JSON فقط دون أي شرح.

        العنوان الحالي:
        {draft_title}

        النص:
        {draft_html[:9000]}

        المصدر:
        {source_text[:4000]}
        """

        ai = self._get_ai_service()
        data = await ai.generate_json(prompt) if ai else {}

        plain_text = self.html_to_text(draft_html)
        fallback_meta = f"{draft_title}. {plain_text[:260]}".strip()

        seo_title = self._strip_side_comments(str(data.get("seo_title") or draft_title or "").strip())[:60]
        meta = self._strip_side_comments(str(data.get("meta_description") or "").strip())

        focus_keyphrase = self._strip_side_comments(str(data.get("focus_keyphrase") or "").strip())
        if not focus_keyphrase:
            focus_keyphrase = self._strip_side_comments((draft_title or "").split(" - ")[0].strip())

        seo_title = self._ensure_title_with_phrase(seo_title, focus_keyphrase, draft_title or "", min_len=40, max_len=60)
        meta = self._ensure_meta_with_phrase(meta, focus_keyphrase, fallback_meta, min_len=140, max_len=155)

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
        if focus_keyphrase and focus_keyphrase not in keywords:
            keywords = self._uniq([focus_keyphrase] + keywords, 6)
        if focus_keyphrase and focus_keyphrase not in tags:
            tags = self._uniq([focus_keyphrase] + tags, 6)

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

        first_paragraph = self._extract_first_paragraph(draft_html, plain_text)
        headings = self._extract_headings(draft_html)
        hrefs, link_texts = self._extract_links(draft_html)
        image_count, images_with_alt = self._extract_images(draft_html)

        def _is_internal(href: str) -> bool:
            clean = (href or "").strip().lower()
            if not clean:
                return False
            if clean.startswith("/"):
                return True
            if not clean.startswith("http"):
                return True
            return any(token in clean for token in ["echorouk", "echoroukonline"])

        internal_links = sum(1 for href in hrefs if _is_internal(href))
        external_links = sum(1 for href in hrefs if href and href.lower().startswith("http") and not _is_internal(href))

        word_count = len(re.findall(r"\S+", plain_text))
        sentences = [s.strip() for s in re.split(r"[.!?\u061f]+", plain_text) if s.strip()]
        paragraphs = []
        if draft_html:
            soup = BeautifulSoup(draft_html, "html.parser")
            paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all("p") if p.get_text(" ", strip=True)]
        if not paragraphs:
            paragraphs = [p.strip() for p in re.split(r"\n{2,}", plain_text) if p.strip()]

        transition_words = [
            "\u0628\u0627\u0644\u0625\u0636\u0627\u0641\u0629",
            "\u0645\u0646 \u062c\u0647\u0629 \u0623\u062e\u0631\u0649",
            "\u0644\u0630\u0644\u0643",
            "\u0643\u0645\u0627 \u0623\u0646",
            "\u0641\u064a \u0627\u0644\u0645\u0642\u0627\u0628\u0644",
            "\u0645\u0646 \u0646\u0627\u062d\u064a\u0629 \u0623\u062e\u0631\u0649",
            "\u0623\u062e\u064a\u0631\u0627\u064b",
            "\u0628\u064a\u0646\u0645\u0627",
        ]
        has_transition = any(word in plain_text for word in transition_words)

        passive_markers = [
            "\u062a\u0645",
            "\u064a\u062a\u0645",
            "\u062c\u0631\u0649",
            "\u064a\u062c\u0631\u064a",
            "\u0642\u062f \u062a\u0645",
        ]
        passive_count = sum(1 for sentence in sentences if any(marker in sentence for marker in passive_markers))
        passive_ratio = passive_count / max(1, len(sentences))

        long_sentence_count = sum(1 for sentence in sentences if len(sentence.split()) > 25)
        long_paragraph_count = sum(1 for paragraph in paragraphs if len(paragraph.split()) > 120)

        first_words = []
        for sentence in sentences:
            words = sentence.split()
            if words:
                first_words.append(words[0])
        consecutive_starts = sum(
            1 for idx in range(1, len(first_words)) if first_words[idx] == first_words[idx - 1]
        )

        keyphrase_in_title = self._contains_phrase(seo_title, focus_keyphrase)
        keyphrase_in_meta = self._contains_phrase(meta, focus_keyphrase)
        keyphrase_in_intro = self._contains_phrase(first_paragraph, focus_keyphrase)
        keyphrase_in_headings = any(self._contains_phrase(item, focus_keyphrase) for item in headings)

        keyphrase_occurrences = (
            len(re.findall(re.escape(focus_keyphrase), plain_text, flags=re.IGNORECASE))
            if focus_keyphrase
            else 0
        )
        keyphrase_density = (
            round((keyphrase_occurrences / max(1, word_count)) * 100, 2) if word_count else 0.0
        )
        keyphrase_density_ok = 0.5 <= keyphrase_density <= 2.5

        competing_links = 0
        if focus_keyphrase:
            competing_links = sum(
                1 for text in link_texts if self._contains_phrase(text, focus_keyphrase)
            )

        yoast_checks = [
            {"code": "focus_keyphrase", "status": "ok" if focus_keyphrase else "warn"},
            {"code": "keyphrase_in_title", "status": "ok" if keyphrase_in_title else "warn"},
            {"code": "keyphrase_in_intro", "status": "ok" if keyphrase_in_intro else "warn"},
            {"code": "keyphrase_in_meta", "status": "ok" if keyphrase_in_meta else "warn"},
            {"code": "keyphrase_in_headings", "status": "ok" if keyphrase_in_headings else "warn"},
            {"code": "keyphrase_density", "status": "ok" if keyphrase_density_ok else "warn"},
            {"code": "word_count", "status": "ok" if word_count >= 300 else "warn"},
            {"code": "internal_links", "status": "ok" if internal_links >= 1 else "warn"},
            {"code": "external_links", "status": "ok" if external_links >= 1 else "warn"},
            {"code": "images_alt", "status": "ok" if images_with_alt >= 1 else "warn"},
            {"code": "transition_words", "status": "ok" if has_transition else "warn"},
            {"code": "sentence_length", "status": "ok" if long_sentence_count == 0 else "warn"},
            {"code": "paragraph_length", "status": "ok" if long_paragraph_count == 0 else "warn"},
            {"code": "passive_voice", "status": "ok" if passive_ratio <= 0.2 else "warn"},
            {"code": "consecutive_starts", "status": "ok" if consecutive_starts == 0 else "warn"},
            {"code": "competing_links", "status": "ok" if competing_links <= 1 else "warn"},
            {"code": "previously_used_keyphrase", "status": "unknown"},
        ]

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
                "keyphrase_in_title": keyphrase_in_title,
                "keyphrase_in_intro": keyphrase_in_intro,
                "keyphrase_in_meta": keyphrase_in_meta,
                "keyphrase_in_headings": keyphrase_in_headings,
                "keyphrase_density": keyphrase_density,
                "keyphrase_density_ok": keyphrase_density_ok,
                "word_count": word_count,
                "word_count_ok": word_count >= 300,
                "internal_links": internal_links,
                "external_links": external_links,
                "images": image_count,
                "images_with_alt": images_with_alt,
                "transition_words_ok": has_transition,
                "passive_voice_ratio": round(passive_ratio, 2),
                "passive_voice_ok": passive_ratio <= 0.2,
                "long_sentences": long_sentence_count,
                "long_paragraphs": long_paragraph_count,
                "consecutive_starts": consecutive_starts,
                "competing_links": competing_links,
                "checks": yoast_checks,
            },
        }

    async def social_variants(self, *, source_text: str, draft_title: str, draft_html: str) -> dict[str, str]:
        prompt = f"""
        أنت محرر منصات اجتماعية لموقع إخباري.
        أريد نسخًا جاهزة للنشر وفق القنوات التالية.

        أعد JSON فقط بالمفاتيح:
        facebook, x, push, summary_120, breaking_alert

        قواعد مهمة:
        - التزم فقط بالمعلومات الموجودة في النص.
        - اجعل كل نسخة مناسبة لمنصتها.
        - لا تستخدم clickbait مضلل.
        - push بين 15 و18 كلمة.
        - summary_120 بين 100 و130 حرفًا.
        - breaking_alert استخدمه فقط إذا كان الخبر عاجلًا.
        - أعد JSON فقط دون أي شرح.

        العنوان الحالي:
        {draft_title}

        النص:
        {draft_html[:9000]}

        المصدر:
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
            risk_level = "low"
            if claim_type in {"number", "date"} or confidence >= 0.85:
                risk_level = "high"
            elif confidence >= 0.70:
                risk_level = "medium"

            claims.append(
                {
                    "id": f"clm-{idx}",
                    "text": sentence,
                    "claim_type": claim_type,
                    "risk_level": risk_level,
                    "confidence": round(confidence, 2),
                    "sensitive": claim_type in {"number", "date"} or confidence >= 0.8,
                    "blocking": confidence < 0.70,
                    "verify_hint": "تحقق من المصدر الرسمي أو وكالة موثوقة",
                    "evidence_links": [source_url] if source_url else [],
                    "unverifiable": False,
                    "unverifiable_reason": "",
                }
            )
        return claims

    async def fact_check_report(self, *, text: str, source_url: str | None = None, threshold: float = 0.70) -> dict[str, Any]:
        clean_text = self._strip_side_comments(text or "")
        template_noise = self._contains_template_noise(clean_text)
        claims = self.extract_claims(text=clean_text, source_url=source_url)
        external_summary = {
            "provider": "google_fact_check_tools",
            "queries": 0,
            "matches": 0,
            "false_claims": 0,
            "true_claims": 0,
            "enabled": False,
        }
        for claim in claims:
            has_support = bool(claim.get("evidence_links")) or (
                bool(claim.get("unverifiable")) and bool(claim.get("unverifiable_reason"))
            )
            if has_support:
                claim["blocking"] = False
                claim["supported"] = True
            claim["external_matches"] = []
            claim["external_verdict"] = "unknown"
            claim["external_match_count"] = 0

        def _risk_rank(level: str) -> int:
            return {"high": 0, "medium": 1, "low": 2}.get(level, 3)

        api_enabled = bool(fact_check_tools_service) and await fact_check_tools_service.is_enabled()
        external_summary["enabled"] = api_enabled

        queries = sorted(
            claims,
            key=lambda c: (_risk_rank(str(c.get("risk_level"))), -float(c.get("confidence") or 0.0)),
        )[:6]

        if not fact_check_tools_service or not api_enabled:
            unresolved = [c for c in claims if c.get("blocking")]
            blocking_reasons: list[str] = []
            actionable_fixes: list[str] = []
            if template_noise:
                blocking_reasons.append("النص يحتوي قوالب أو تعليقات جانبية وغير صالح للنشر")
                actionable_fixes.append("استخدم زر تحسين الصياغة لإزالة القوالب والتعليقات")
            if claims:
                blocking_reasons.append("خدمة التحقق من الادعاءات غير مفعلة، لا يمكن اعتماد التقرير دونها.")
                actionable_fixes.append("أضف مفتاح Google Fact Check من صفحة الإعدادات ثم أعد التحقق.")
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
                "external_fact_checks": external_summary,
                "blocking_reasons": blocking_reasons,
                "actionable_fixes": actionable_fixes,
                "threshold": threshold,
            }

        for claim in queries:
            query_text = str(claim.get("text") or "").strip()
            if not query_text:
                continue
            matches, search_traces = await fact_check_tools_service.search_claims_with_fallbacks(
                query_text,
                language="ar",
                page_size=4,
            )
            claim["external_search_queries"] = search_traces
            external_summary["queries"] += len(search_traces)
            if not matches:
                continue
            external_summary["matches"] += len(matches)
            verdict = fact_check_tools_service.infer_verdict(matches)
            claim["external_matches"] = matches
            claim["external_match_count"] = len(matches)
            claim["external_verdict"] = verdict
            links = [m.get("url") for m in matches if m.get("url")]
            if links:
                claim["evidence_links"] = list(dict.fromkeys((claim.get("evidence_links") or []) + links))
            if verdict == "false":
                external_summary["false_claims"] += 1
                claim["blocking"] = True
                claim["risk_level"] = "high"
            elif verdict == "true":
                external_summary["true_claims"] += 1
                claim["blocking"] = False
                claim["supported"] = True

        unresolved = [c for c in claims if c.get("blocking")]

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
            "external_fact_checks": external_summary,
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
        أنت مساعد تحريري لتقييم قرار الاعتماد النهائي.
        أعد قرارًا مختصرًا مع الأسباب والإصلاحات المطلوبة.

        أعد JSON فقط بالمفاتيح:
        decision, reasons, required_fixes, confidence

        قواعد مهمة:
        - decision يجب أن يكون approved أو reservations فقط.
        - reservations تُستخدم عند وجود ملاحظات تحريرية أو فجوات تتطلب مراجعة.
        - reasons قائمة مختصرة (حتى 4 عناصر).
        - required_fixes قائمة مختصرة (حتى 4 عناصر).
        - أعد JSON فقط دون أي شرح.

        العنوان:
        {title}

        النص:
        {body_text[:8000]}

        المصدر:
        {source_text[:2500]}

        القرار المبدئي الموصى به:
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
