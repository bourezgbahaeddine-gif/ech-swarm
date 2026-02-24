"""Document Intelligence service for PDF extraction and newsroom structuring."""

from __future__ import annotations

import asyncio
import json
import re
import subprocess
import sys
import tempfile
import unicodedata
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from app.core.logging import get_logger

logger = get_logger("document_intel.service")

_NEWS_KEYWORDS_BY_LANG = {
    "ar": (
        "اعلن",
        "أكد",
        "اكد",
        "صرح",
        "قررت",
        "قرر",
        "كشف",
        "وقع",
        "اجتماع",
        "مرسوم",
        "الجريدة الرسمية",
        "وزارة",
        "الحكومة",
        "رئاسة",
        "البرلمان",
        "مجلس",
        "بيان",
        "تقرير",
    ),
    "en": (
        "press release",
        "announced",
        "confirmed",
        "stated",
        "said",
        "meeting",
        "agreement",
        "launch",
        "scheduled",
        "official",
        "government",
        "minister",
        "president",
        "report",
        "decision",
    ),
    "fr": (
        "communique",
        "a annonce",
        "a confirme",
        "a declare",
        "reunion",
        "accord",
        "officiel",
        "gouvernement",
        "ministere",
        "president",
        "rapport",
        "decision",
        "publication",
    ),
}

_ENTITY_PATTERNS = (
    r"(وزارة\s+[^\n،,.]{2,40})",
    r"(رئاسة\s+[^\n،,.]{2,40})",
    r"(البرلمان\s+[^\n،,.]{2,40})",
    r"(مجلس\s+[^\n،,.]{2,40})",
    r"(الحكومة\s+[^\n،,.]{2,40})",
    r"(Ministry\s+of\s+[^\n,.;]{2,50})",
    r"(Government\s+of\s+[^\n,.;]{2,50})",
    r"(President\s+of\s+[^\n,.;]{2,50})",
    r"(Association\s+of\s+[^\n,.;]{2,50})",
    r"(Minist[eè]re\s+(?:de|du|des)\s+[^\n,.;]{2,50})",
    r"(Gouvernement\s+(?:de|du|des)\s+[^\n,.;]{2,50})",
    r"(Pr[eé]sident\s+(?:de|du|des)\s+[^\n,.;]{2,50})",
)

_NUMBER_PATTERN = re.compile(r"\d[\d,.\u0660-\u0669]*%?")
_DATE_PATTERN = re.compile(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b")


@dataclass
class _ExtractionChunk:
    text: str
    markdown: str
    pages: int | None
    parser: str
    warning: str | None = None
    error: str | None = None


class DocumentIntelService:
    max_upload_bytes = 45 * 1024 * 1024  # 45MB
    docling_timeout_seconds = 45

    async def extract_pdf(
        self,
        *,
        filename: str,
        payload: bytes,
        language_hint: str = "ar",
        max_news_items: int = 8,
        max_data_points: int = 30,
    ) -> dict:
        safe_name = self._safe_filename(filename)
        if not payload:
            raise ValueError("Uploaded file is empty")
        if len(payload) > self.max_upload_bytes:
            raise ValueError("File exceeds 45MB limit")
        if not safe_name.lower().endswith(".pdf"):
            raise ValueError("Only PDF files are supported in this phase")

        try:
            docling_chunk = await asyncio.wait_for(
                asyncio.to_thread(self._extract_with_docling, payload, safe_name),
                timeout=self.docling_timeout_seconds,
            )
        except asyncio.TimeoutError:
            docling_chunk = _ExtractionChunk(
                text="",
                markdown="",
                pages=None,
                parser="docling_timeout",
                warning=f"Docling timed out after {self.docling_timeout_seconds}s; using fallback parser.",
            )
        warnings: list[str] = []
        if docling_chunk.warning:
            warnings.append(docling_chunk.warning)

        extraction = docling_chunk
        if not extraction.text.strip():
            pypdf_chunk = await asyncio.to_thread(self._extract_with_pypdf, payload)
            if pypdf_chunk.warning:
                warnings.append(pypdf_chunk.warning)
            extraction = pypdf_chunk

        normalized_text = self._normalize_text(extraction.text)
        if not normalized_text:
            warnings.append("No selectable text found in PDF. OCR pipeline is required for scanned documents.")
        detected_language = self._detect_language(normalized_text)
        headings = self._extract_headings(extraction.markdown, normalized_text)
        paragraphs = self._split_paragraphs(normalized_text)
        news_candidates = self._extract_news_candidates(
            paragraphs,
            max_news_items=max_news_items,
            detected_language=detected_language,
            language_hint=self._normalize_lang(language_hint),
        )
        data_points = self._extract_data_points(paragraphs, max_data_points=max_data_points)

        return {
            "filename": safe_name,
            "parser_used": extraction.parser,
            "language_hint": self._normalize_lang(language_hint),
            "detected_language": detected_language,
            "stats": {
                "pages": extraction.pages,
                "characters": len(normalized_text),
                "paragraphs": len(paragraphs),
                "headings": len(headings),
            },
            "headings": headings,
            "news_candidates": news_candidates,
            "data_points": data_points,
            "warnings": warnings,
            "preview_text": normalized_text[:2500],
        }

    def _extract_with_docling(self, payload: bytes, filename: str) -> _ExtractionChunk:
        try:
            from docling.document_converter import DocumentConverter
        except Exception as exc:
            # Some environments fail importing docling in-process (e.g. numpy loader issues).
            # Retry extraction in a clean subprocess before falling back to pypdf.
            subprocess_result = self._extract_with_docling_subprocess(payload, filename)
            if subprocess_result.text.strip():
                return subprocess_result
            return _ExtractionChunk(
                text="",
                markdown="",
                pages=None,
                parser="docling_unavailable",
                warning=f"Docling unavailable in-process ({type(exc).__name__}); using fallback parser.",
                error=str(exc),
            )

        try:
            with tempfile.TemporaryDirectory(prefix="doc-intel-") as temp_dir:
                temp_path = Path(temp_dir) / filename
                temp_path.write_bytes(payload)
                converter = DocumentConverter()
                result = converter.convert(str(temp_path))

                document_obj = getattr(result, "document", result)
                markdown = ""
                text = ""
                pages: int | None = None

                if hasattr(document_obj, "export_to_markdown"):
                    markdown = str(document_obj.export_to_markdown() or "")
                elif hasattr(result, "export_to_markdown"):
                    markdown = str(result.export_to_markdown() or "")

                if hasattr(document_obj, "export_to_text"):
                    text = str(document_obj.export_to_text() or "")
                elif hasattr(result, "text"):
                    text = str(getattr(result, "text", "") or "")

                if not text and markdown:
                    text = self._markdown_to_text(markdown)
                if not text:
                    text = str(document_obj) if document_obj is not None else ""

                pages_attr = getattr(document_obj, "pages", None)
                if isinstance(pages_attr, list):
                    pages = len(pages_attr)
                elif hasattr(document_obj, "page_count"):
                    raw = getattr(document_obj, "page_count")
                    pages = int(raw) if raw is not None else None

                return _ExtractionChunk(
                    text=text,
                    markdown=markdown,
                    pages=pages,
                    parser="docling",
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("docling_parse_failed", error=str(exc))
            subprocess_result = self._extract_with_docling_subprocess(payload, filename)
            if subprocess_result.text.strip():
                return subprocess_result
            return _ExtractionChunk(
                text="",
                markdown="",
                pages=None,
                parser="docling_failed",
                warning=f"Docling parse failed: {exc}",
                error=str(exc),
            )

    def _extract_with_docling_subprocess(self, payload: bytes, filename: str) -> _ExtractionChunk:
        script = r"""
import json
import sys
from docling.document_converter import DocumentConverter

path = sys.argv[1]
converter = DocumentConverter()
result = converter.convert(path)
document_obj = getattr(result, "document", result)
markdown = ""
text = ""
pages = None

if hasattr(document_obj, "export_to_markdown"):
    markdown = str(document_obj.export_to_markdown() or "")
elif hasattr(result, "export_to_markdown"):
    markdown = str(result.export_to_markdown() or "")

if hasattr(document_obj, "export_to_text"):
    text = str(document_obj.export_to_text() or "")
elif hasattr(result, "text"):
    text = str(getattr(result, "text", "") or "")

if isinstance(getattr(document_obj, "pages", None), list):
    pages = len(getattr(document_obj, "pages"))
elif hasattr(document_obj, "page_count"):
    raw_pages = getattr(document_obj, "page_count")
    pages = int(raw_pages) if raw_pages is not None else None

print(json.dumps({"text": text, "markdown": markdown, "pages": pages}, ensure_ascii=False))
"""
        try:
            with tempfile.TemporaryDirectory(prefix="doc-intel-sub-") as temp_dir:
                temp_path = Path(temp_dir) / filename
                temp_path.write_bytes(payload)
                proc = subprocess.run(
                    [sys.executable, "-c", script, str(temp_path)],
                    capture_output=True,
                    text=True,
                    timeout=self.docling_timeout_seconds,
                    check=False,
                )
                if proc.returncode != 0:
                    logger.warning(
                        "docling_subprocess_failed",
                        returncode=proc.returncode,
                        stderr=(proc.stderr or "")[:1000],
                    )
                    return _ExtractionChunk(
                        text="",
                        markdown="",
                        pages=None,
                        parser="docling_subprocess_failed",
                        warning="Docling subprocess failed; using fallback parser.",
                        error=(proc.stderr or "")[:1000],
                    )

                raw = (proc.stdout or "").strip()
                if not raw:
                    return _ExtractionChunk(
                        text="",
                        markdown="",
                        pages=None,
                        parser="docling_subprocess_empty",
                        warning="Docling subprocess produced empty output; using fallback parser.",
                    )
                data = json.loads(raw)
                text = str(data.get("text") or "")
                markdown = str(data.get("markdown") or "")
                pages = data.get("pages")
                return _ExtractionChunk(
                    text=text or self._markdown_to_text(markdown),
                    markdown=markdown,
                    pages=int(pages) if isinstance(pages, int) else None,
                    parser="docling_subprocess",
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("docling_subprocess_exception", error=str(exc))
            return _ExtractionChunk(
                text="",
                markdown="",
                pages=None,
                parser="docling_subprocess_exception",
                warning="Docling subprocess exception; using fallback parser.",
                error=str(exc),
            )

    def _extract_with_pypdf(self, payload: bytes) -> _ExtractionChunk:
        try:
            from pypdf import PdfReader
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError("pypdf is not installed. Add pypdf to backend requirements.") from exc

        try:
            reader = PdfReader(BytesIO(payload))
            pages = len(reader.pages)
            page_text: list[str] = []
            for page in reader.pages:
                raw = page.extract_text() or ""
                page_text.append(raw.strip())
            text = "\n\n".join(chunk for chunk in page_text if chunk)
            return _ExtractionChunk(
                text=text,
                markdown="",
                pages=pages,
                parser="pypdf",
            )
        except Exception as exc:  # noqa: BLE001
            raise ValueError("Invalid or unreadable PDF file") from exc

    @staticmethod
    def _normalize_text(text: str) -> str:
        value = (text or "").replace("\x00", " ")
        value = value.replace("\r\n", "\n").replace("\r", "\n")
        value = re.sub(r"[ \t\f\v]+", " ", value)
        value = re.sub(r"\n{3,}", "\n\n", value)
        return value.strip()

    @staticmethod
    def _split_paragraphs(text: str) -> list[str]:
        if not text:
            return []
        chunks = re.split(r"\n{2,}", text)
        output: list[str] = []
        for chunk in chunks:
            cleaned = chunk.strip(" -•\n\t")
            cleaned = re.sub(r"\s+", " ", cleaned).strip()
            if len(cleaned) < 40:
                continue
            output.append(cleaned)
        return output

    def _extract_headings(self, markdown: str, text: str) -> list[str]:
        headings: list[str] = []
        for line in (markdown or "").splitlines():
            if line.startswith("#"):
                title = re.sub(r"^#+\s*", "", line).strip()
                if 3 <= len(title) <= 120:
                    headings.append(title)
        if headings:
            return self._uniq(headings, 12)

        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if len(stripped) > 120:
                continue
            if any(ch in stripped for ch in ".!?:؛،"):
                continue
            headings.append(stripped)
        return self._uniq(headings, 12)

    def _extract_news_candidates(
        self,
        paragraphs: list[str],
        *,
        max_news_items: int,
        detected_language: str,
        language_hint: str,
    ) -> list[dict]:
        effective_lang = self._resolve_language(detected_language, language_hint)
        scored: list[tuple[float, str, str]] = []
        for para in paragraphs:
            para_lang = effective_lang
            if effective_lang in {"mixed", "unknown"}:
                para_lang = self._detect_language(para)
            score = self._score_news_paragraph(para, para_lang)
            scored.append((score, para, para_lang))

        scored.sort(key=lambda item: item[0], reverse=True)
        selected = [item for item in scored if item[0] >= 1.6]
        if not selected:
            selected = [item for item in scored if item[0] >= 1.0][:max(2, min(4, max_news_items))]

        items: list[dict] = []
        dedupe: set[str] = set()
        rank = 1
        for score, para, para_lang in selected:
            headline = self._headline_from_paragraph(para)
            headline_key = headline.strip().lower()
            if headline_key in dedupe:
                continue
            dedupe.add(headline_key)
            summary = para[:320]
            entities = self._extract_entities(para)
            items.append(
                {
                    "rank": rank,
                    "headline": headline,
                    "summary": summary,
                    "evidence": para[:700],
                    "confidence": round(min(0.96, 0.35 + score * 0.14), 2),
                    "entities": entities,
                }
            )
            rank += 1
            if len(items) >= max_news_items:
                break
        return items

    def _score_news_paragraph(self, paragraph: str, lang: str) -> float:
        score = 0.0
        normalized = self._normalize_for_lang(paragraph, lang)
        keywords = _NEWS_KEYWORDS_BY_LANG.get(lang, _NEWS_KEYWORDS_BY_LANG["en"])

        for keyword in keywords:
            if self._contains_keyword(normalized, keyword, lang):
                score += 0.65

        if _NUMBER_PATTERN.search(paragraph):
            score += 0.55
        if _DATE_PATTERN.search(paragraph):
            score += 0.75
        if self._extract_entities(paragraph):
            score += 0.55
        if '"' in paragraph or "“" in paragraph or "”" in paragraph or "«" in paragraph:
            score += 0.2

        length = len(paragraph)
        if 80 <= length <= 700:
            score += 0.35
        elif length < 55:
            score -= 0.45
        elif length > 1200:
            score -= 0.3

        if paragraph.strip().isupper() and length < 140:
            score -= 0.4

        return score

    def _extract_data_points(self, paragraphs: list[str], *, max_data_points: int) -> list[dict]:
        items: list[dict] = []
        rank = 1
        for para in paragraphs:
            values = _NUMBER_PATTERN.findall(para)
            if not values:
                continue

            category = "numeric"
            if "%" in para:
                category = "percentage"
            elif any(token in para for token in ("دينار", "دولار", "يورو", "DA", "USD", "EUR")):
                category = "money"
            elif _DATE_PATTERN.search(para):
                category = "date"

            items.append(
                {
                    "rank": rank,
                    "category": category,
                    "value_tokens": values[:8],
                    "context": para[:360],
                }
            )
            rank += 1
            if len(items) >= max_data_points:
                break
        return items

    @staticmethod
    def _headline_from_paragraph(paragraph: str) -> str:
        sentence = re.split(r"[.!؟\n]", paragraph, maxsplit=1)[0].strip()
        sentence = re.sub(r"\s+", " ", sentence)
        if len(sentence) <= 110:
            return sentence
        return f"{sentence[:107].rstrip()}..."

    @staticmethod
    def _extract_entities(paragraph: str) -> list[str]:
        entities: list[str] = []
        for pattern in _ENTITY_PATTERNS:
            for match in re.findall(pattern, paragraph):
                value = re.sub(r"\s+", " ", match).strip()
                if 3 <= len(value) <= 60:
                    entities.append(value)
        return DocumentIntelService._uniq(entities, 8)

    @staticmethod
    def _normalize_lang(value: str | None) -> str:
        candidate = (value or "ar").strip().lower()
        if candidate in {"ar", "en", "fr", "auto"}:
            return candidate
        return "ar"

    @staticmethod
    def _detect_language(text: str) -> str:
        if not text:
            return "unknown"
        sample = text[:2000]
        arabic_chars = len(re.findall(r"[\u0600-\u06FF]", sample))
        latin_chars = len(re.findall(r"[A-Za-z]", sample))
        if arabic_chars > latin_chars * 1.1:
            return "ar"
        if latin_chars > arabic_chars * 1.1:
            sample_norm = DocumentIntelService._normalize_latin(sample).lower()
            french_markers = (
                " le ",
                " la ",
                " les ",
                " des ",
                " avec ",
                " pour ",
                " nous ",
                " est ",
                " communique ",
                " gouvernement ",
                " ministere ",
            )
            marker_hits = sum(1 for marker in french_markers if marker in f" {sample_norm} ")
            if marker_hits >= 2 or bool(re.search(r"[àâçéèêëîïôûùüÿœæ]", sample.lower())):
                return "fr"
            return "en"
        return "mixed"

    @staticmethod
    def _markdown_to_text(markdown: str) -> str:
        value = re.sub(r"^#+\s*", "", markdown, flags=re.MULTILINE)
        value = re.sub(r"[`*_>-]", " ", value)
        value = re.sub(r"\[(.*?)\]\((.*?)\)", r"\1", value)
        return value

    @staticmethod
    def _normalize_ar(value: str) -> str:
        text = value.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
        text = text.replace("ة", "ه").replace("ى", "ي")
        return re.sub(r"[\u064b-\u065f\u0670]", "", text)

    @staticmethod
    def _normalize_latin(value: str) -> str:
        text = unicodedata.normalize("NFKD", value or "")
        return "".join(ch for ch in text if not unicodedata.combining(ch))

    def _normalize_for_lang(self, value: str, lang: str) -> str:
        if lang == "ar":
            return self._normalize_ar((value or "").lower())
        return self._normalize_latin((value or "").lower())

    def _contains_keyword(self, normalized_text: str, keyword: str, lang: str) -> bool:
        if lang == "ar":
            return self._normalize_ar(keyword) in normalized_text
        keyword_norm = self._normalize_latin(keyword.lower()).strip()
        if not keyword_norm:
            return False
        if " " in keyword_norm:
            return keyword_norm in normalized_text
        return bool(re.search(rf"\b{re.escape(keyword_norm)}\b", normalized_text))

    @staticmethod
    def _resolve_language(detected_language: str, language_hint: str) -> str:
        if detected_language in {"ar", "en", "fr"}:
            return detected_language
        if language_hint in {"ar", "en", "fr"}:
            return language_hint
        return "mixed"

    @staticmethod
    def _safe_filename(filename: str) -> str:
        raw = (filename or "document.pdf").strip()
        raw = raw.replace("\\", "_").replace("/", "_")
        raw = re.sub(r"\s+", "_", raw)
        raw = re.sub(r"[^A-Za-z0-9._-]", "", raw)
        return (raw[:140] or "document.pdf")

    @staticmethod
    def _uniq(values: list[str], limit: int) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for item in values:
            key = item.strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(item.strip())
            if len(out) >= limit:
                break
        return out


document_intel_service = DocumentIntelService()
