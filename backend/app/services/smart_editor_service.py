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

TRANSITIONS_AR = {
    "لكن",
    "بالمقابل",
    "إضافة إلى ذلك",
    "في المقابل",
    "من جهة أخرى",
    "لذلك",
    "وبحسب",
}

CLAIM_TRIGGER_WORDS_AR = {
    "قال",
    "أعلن",
    "صرح",
    "أكد",
    "كشف",
    "ذكر",
    "نقل",
}


@dataclass
class DiffResult:
    diff: str
    added: int
    removed: int


class SmartEditorService:
    @staticmethod
    def _get_ai_service():
        try:
            from app.services.ai_service import ai_service  # lazy import to avoid hard dependency at import-time

            return ai_service
        except Exception:
            return None

    def sanitize_html(self, value: str) -> str:
        cleaned = bleach.clean(
            value or "",
            tags=ALLOWED_TAGS,
            attributes=ALLOWED_ATTRS,
            protocols=["http", "https", "mailto"],
            strip=True,
        )
        # Drop javascript-like href values that may slip through malformed markup.
        cleaned = re.sub(r'href\s*=\s*["\']\s*javascript:[^"\']*["\']', 'href="#"', cleaned, flags=re.IGNORECASE)
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
You are an Arabic newsroom assistant for Echorouk.
Return strict JSON only with keys:
title, body_html, note

Hard rules:
- Keep facts exactly as provided in source context.
- Do not add new entities, numbers, dates, or quotes.
- Use neutral journalistic tone.
- Output clean HTML only in body_html (h1,p,h2,ul,li,a,strong,em).

Mode: {mode}
Instruction: {instruction or "none"}

Source context:
{source_text[:7000]}

Current title:
{draft_title}

Current body:
{draft_html[:10000]}
"""
        ai = self._get_ai_service()
        data = await ai.generate_json(prompt) if ai else {}
        title = str(data.get("title") or draft_title or "").strip()
        body_html = str(data.get("body_html") or draft_html or "").strip()
        note = str(data.get("note") or f"rewrite_mode:{mode}").strip()

        if not body_html:
            body_html = draft_html
        sanitized = self.sanitize_html(body_html)
        diff = self.build_diff(draft_html, sanitized)

        return {
            "title": title,
            "body_html": sanitized,
            "note": note,
            "diff": diff.diff,
            "diff_stats": {"added": diff.added, "removed": diff.removed},
            "generated_at": datetime.utcnow().isoformat(),
        }

    async def headline_suggestions(self, *, source_text: str, draft_title: str) -> list[dict[str, str]]:
        prompt = f"""
Generate exactly 5 Arabic newsroom headlines as strict JSON array.
Each item must contain: label, headline.
Required labels in order:
official, breaking, seo, engaging, mobile_short.
No markdown.
No extra keys.

Context:
{source_text[:5000]}

Current title:
{draft_title}
"""
        ai = self._get_ai_service()
        data = await ai.generate_json(prompt) if ai else {}
        if isinstance(data, list) and len(data) >= 5:
            out: list[dict[str, str]] = []
            for item in data[:5]:
                out.append(
                    {
                        "label": str(item.get("label") or "").strip(),
                        "headline": str(item.get("headline") or "").strip(),
                    }
                )
            if all(x["headline"] for x in out):
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
Return strict JSON with keys:
seo_title, meta_description, keywords, tags

Rules:
- Arabic newsroom style.
- seo_title <= 60 chars.
- meta_description <= 155 chars.
- keywords exactly 5 items.
- tags exactly 5 items.

Title:
{draft_title}

Body:
{draft_html[:9000]}

Context:
{source_text[:4000]}
"""
        ai = self._get_ai_service()
        data = await ai.generate_json(prompt) if ai else {}
        seo_title = str(data.get("seo_title") or draft_title or "").strip()[:60]
        meta = str(data.get("meta_description") or "").strip()[:155]

        keywords = data.get("keywords") or []
        tags = data.get("tags") or []
        if not isinstance(keywords, list):
            keywords = []
        if not isinstance(tags, list):
            tags = []
        keywords = [str(x).strip() for x in keywords if str(x).strip()][:5]
        tags = [str(x).strip() for x in tags if str(x).strip()][:5]

        if not keywords:
            tokens = re.findall(r"[\u0600-\u06FFA-Za-z]{4,}", self.html_to_text(draft_html))
            keywords = list(dict.fromkeys(tokens))[:5]
        if not tags:
            tags = keywords[:5]

        return {
            "seo_title": seo_title,
            "meta_description": meta,
            "keywords": keywords,
            "tags": tags,
        }

    async def social_variants(self, *, source_text: str, draft_title: str, draft_html: str) -> dict[str, str]:
        prompt = f"""
Return strict JSON with keys:
facebook, x, push, summary_120, breaking_alert

Constraints:
- Arabic.
- factual only.
- push must be 15-18 words.
- summary_120 around 120 words.

Title:
{draft_title}

Body:
{draft_html[:9000]}

Context:
{source_text[:3000]}
"""
        ai = self._get_ai_service()
        data = await ai.generate_json(prompt) if ai else {}
        out: dict[str, str] = {}
        for key in ["facebook", "x", "push", "summary_120", "breaking_alert"]:
            out[key] = str(data.get(key) or "").strip()
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

            blocking = confidence < 0.70
            claims.append(
                {
                    "id": f"clm-{idx}",
                    "text": sentence,
                    "claim_type": claim_type,
                    "confidence": round(confidence, 2),
                    "blocking": blocking,
                    "verify_hint": "official_statement_or_reliable_wire",
                    "evidence_links": [source_url] if source_url else [],
                }
            )
        return claims

    def fact_check_report(self, *, text: str, source_url: str | None = None, threshold: float = 0.70) -> dict[str, Any]:
        claims = self.extract_claims(text=text, source_url=source_url)
        unresolved = [c for c in claims if c["confidence"] < threshold]
        passed = len(unresolved) == 0
        return {
            "stage": "FACT_CHECK_PASSED" if passed else "FACT_CHECK_BLOCKED",
            "passed": passed,
            "score": max(0, 100 - len(unresolved) * 20),
            "claims": claims,
            "blocking_reasons": ["Unverified claims found"] if unresolved else [],
            "actionable_fixes": ["Verify low-confidence claims before publish"] if unresolved else [],
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
        if any(x in lead for x in ["في", "ب", "اليوم", "أمس"]):
            lead_score += 25
        if len(lead.split()) >= 12:
            lead_score += 25
        if title:
            lead_score += 25
        inverted_pyramid = lead_score

        duplicates = 0
        seen: set[str] = set()
        for s in sentences:
            key = re.sub(r"\s+", " ", s).strip()
            if key in seen:
                duplicates += 1
            seen.add(key)
        redundancy = max(0, 100 - duplicates * 20)

        length_score = 100
        if len(words) < 140:
            length_score = 60
        elif len(words) > 700:
            length_score = 70

        neutral_penalty = 0
        lowered = text.lower()
        for w in OPINION_WORDS_AR:
            if w in lowered:
                neutral_penalty += 12
        tone_neutrality = max(0, 100 - neutral_penalty)

        source_citations = len(re.findall(r"(قال|أعلن|بحسب|وفق|ذكرت|رويترز|الوزارة)", text))
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
            fixes.append("Split long sentences and simplify wording.")
        if structure < 80:
            fixes.append("Ensure one H1 and at least one H2 section.")
        if inverted_pyramid < 70:
            fixes.append("Strengthen lead paragraph with who/what/when/where.")
        if source_presence < 60:
            fixes.append("Add explicit source attribution.")
        if tone_neutrality < 85:
            fixes.append("Remove opinionated adjectives and keep neutral tone.")

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
            "blocking_reasons": [] if passed else ["Quality score below publish threshold"],
            "actionable_fixes": fixes,
            "source_excerpt": source_text[:280],
        }


smart_editor_service = SmartEditorService()
