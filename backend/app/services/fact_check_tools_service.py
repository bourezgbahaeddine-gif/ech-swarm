from __future__ import annotations

from typing import Any, Callable, Awaitable

import re

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.settings_service import settings_service


logger = get_logger("services.fact_check_tools")
settings = get_settings()

NEGATIVE_RATINGS = {
    "false",
    "incorrect",
    "pants on fire",
    "bogus",
    "fake",
    "misleading",
    "wrong",
    "كاذب",
    "خاطئ",
    "غير صحيح",
    "مضلل",
    "زائف",
    "مفبرك",
    "خطأ",
}

POSITIVE_RATINGS = {
    "true",
    "correct",
    "accurate",
    "mostly true",
    "confirmed",
    "صحيح",
    "صحيحة",
    "دقيق",
    "موثوق",
    "حقيقي",
}


class FactCheckToolsService:
    async def _get_api_key(self) -> str:
        key = await settings_service.get_value(
            "GOOGLE_FACT_CHECK_API_KEY",
            settings.google_fact_check_api_key or "",
        )
        return (key or "").strip()

    async def is_enabled(self) -> bool:
        return bool(await self._get_api_key())

    @staticmethod
    def _clean_text(value: Any) -> str:
        return str(value or "").strip()

    @classmethod
    def _infer_verdict(cls, rating: str) -> str:
        low = cls._clean_text(rating).lower()
        if not low:
            return "unknown"
        if any(token in low for token in NEGATIVE_RATINGS):
            return "false"
        if any(token in low for token in POSITIVE_RATINGS):
            return "true"
        if "mixed" in low or "partly" in low or "جزئ" in low or "مختلط" in low:
            return "mixed"
        return "unknown"

    @classmethod
    def _simplify_query(cls, query: str, *, max_tokens: int = 8) -> str:
        text = cls._clean_text(query)
        if not text:
            return ""
        cleaned = re.sub(r"[^\w\u0600-\u06FF\s-]", " ", text, flags=re.UNICODE)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        tokens = cleaned.split()
        ar_stop = {
            "من",
            "في",
            "على",
            "إلى",
            "عن",
            "هذا",
            "هذه",
            "ذلك",
            "تلك",
            "قد",
            "تم",
            "حيث",
            "كما",
            "مع",
            "أو",
            "و",
            "أن",
            "إن",
            "ثم",
            "أعلنت",
            "قال",
            "أكد",
        }
        filtered = [t for t in tokens if t not in ar_stop and len(t) > 2]
        if not filtered:
            filtered = tokens
        return " ".join(filtered[:max_tokens])

    @classmethod
    def _normalize_claims(cls, payload: dict[str, Any]) -> list[dict[str, Any]]:
        claims = payload.get("claims") if isinstance(payload, dict) else None
        if not isinstance(claims, list):
            return []

        seen_urls: set[str] = set()
        matches: list[dict[str, Any]] = []
        for claim in claims:
            if not isinstance(claim, dict):
                continue
            claim_text = cls._clean_text(claim.get("text"))
            claimant = cls._clean_text(claim.get("claimant"))
            claim_date = cls._clean_text(claim.get("claimDate"))
            for review in claim.get("claimReview") or []:
                if not isinstance(review, dict):
                    continue
                url = cls._clean_text(review.get("url"))
                if url and url in seen_urls:
                    continue
                if url:
                    seen_urls.add(url)
                publisher = review.get("publisher") or {}
                matches.append(
                    {
                        "claim": claim_text,
                        "claimant": claimant,
                        "claim_date": claim_date,
                        "publisher": cls._clean_text(publisher.get("name")),
                        "publisher_site": cls._clean_text(publisher.get("site")),
                        "title": cls._clean_text(review.get("title")),
                        "url": url,
                        "rating": cls._clean_text(review.get("textualRating")),
                        "review_date": cls._clean_text(review.get("reviewDate")),
                        "language_code": cls._clean_text(review.get("languageCode")),
                    }
                )
        return matches

    async def search_claims(self, query: str, *, language: str = "ar", page_size: int = 4) -> list[dict[str, Any]]:
        api_key = await self._get_api_key()
        query = self._clean_text(query)
        if not api_key or not query:
            return []

        url = "https://factchecktools.googleapis.com/v1alpha1/claims:search"
        params = {
            "query": query,
            "pageSize": max(1, min(page_size, 6)),
            "languageCode": language or "ar",
            "key": api_key,
        }
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(url, params=params)
                if resp.status_code != 200:
                    logger.warning("fact_check_tools_failed", status=resp.status_code)
                    return []
                payload = resp.json()
        except Exception as exc:
            logger.warning("fact_check_tools_error", error=str(exc))
            return []

        return self._normalize_claims(payload)

    async def search_claims_with_fallbacks(
        self,
        query: str,
        *,
        language: str = "ar",
        page_size: int = 4,
        translate_fn: Callable[[str], Awaitable[str]] | None = None,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        base_query = self._clean_text(query)
        if not base_query:
            return [], []

        attempts: list[tuple[str, str]] = []
        seen: set[tuple[str, str]] = set()

        def add_attempt(q: str, lang: str) -> None:
            q = self._clean_text(q)
            key = (q, lang)
            if not q or key in seen:
                return
            seen.add(key)
            attempts.append(key)

        add_attempt(base_query, language or "ar")
        simplified = self._simplify_query(base_query)
        if simplified and simplified != base_query:
            add_attempt(simplified, language or "ar")

        if (language or "ar") != "en":
            translated = ""
            if translate_fn:
                try:
                    translated = self._clean_text(await translate_fn(base_query))
                except Exception:
                    translated = ""
            translated = translated or base_query
            add_attempt(translated, "en")
            simplified_en = self._simplify_query(translated)
            if simplified_en and simplified_en != translated:
                add_attempt(simplified_en, "en")

        results: list[dict[str, Any]] = []
        traces: list[dict[str, Any]] = []
        seen_urls: set[str] = set()

        for q, lang in attempts:
            matches = await self.search_claims(q, language=lang, page_size=page_size)
            traces.append({"query": q, "language": lang, "matches": len(matches)})
            for match in matches:
                url = self._clean_text(match.get("url")) or self._clean_text(match.get("title")) or self._clean_text(match.get("claim"))
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                results.append(match)

        return results, traces

    def summarize_matches(self, matches: list[dict[str, Any]]) -> dict[str, Any]:
        verdicts = {"true": 0, "false": 0, "mixed": 0, "unknown": 0}
        for match in matches:
            verdict = self._infer_verdict(match.get("rating") or "")
            verdicts[verdict] = verdicts.get(verdict, 0) + 1
        return {
            "total": len(matches),
            "verdicts": verdicts,
            "primary_verdict": "false" if verdicts.get("false") else "true" if verdicts.get("true") else "mixed" if verdicts.get("mixed") else "unknown",
        }

    def infer_verdict(self, matches: list[dict[str, Any]]) -> str:
        summary = self.summarize_matches(matches)
        return summary.get("primary_verdict") or "unknown"


fact_check_tools_service = FactCheckToolsService()
