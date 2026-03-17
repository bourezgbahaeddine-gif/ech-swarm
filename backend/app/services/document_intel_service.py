"""Document Intelligence service for PDF extraction and newsroom structuring."""

from __future__ import annotations

import asyncio
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unicodedata
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from app.core.config import get_settings
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
        "المادة",
        "القانون",
        "مرسوم تنفيذي",
        "قرار وزاري",
        "يحدد",
        "يتضمن",
        "يلغى",
        "يعين",
        "يعدل",
        "يتعلق",
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
_DOCUMENT_TYPE_HINTS = {
    "official_gazette": (
        "الجريدة الرسمية",
        "مرسوم",
        "قرار وزاري",
        "décret",
        "journal officiel",
        "official gazette",
    ),
    "statement": (
        "بيان",
        "تصريح",
        "أعلن",
        "اعلن",
        "communiqué",
        "communique",
        "statement",
        "press release",
    ),
    "report": (
        "تقرير",
        "إحصاء",
        "احصاء",
        "دراسة",
        "rapport",
        "report",
        "analysis",
    ),
}
_ARABIC_CLAIM_VERBS = (
    "أكد",
    "اكد",
    "أعلن",
    "اعلن",
    "قال",
    "أوضح",
    "اوضح",
    "ذكر",
    "كشف",
    "قرر",
    "صادق",
    "وقع",
    "يتضمن",
    "ينص",
    "حدد",
)
_STATISTICAL_HINTS = ("%", "نسبة", "مليون", "مليار", "دينار", "دولار", "يورو", "عدد", "إحصاء", "احصاء")
_LEGAL_HINTS = ("قانون", "مرسوم", "قرار", "المادة", "ينص", "يتضمن", "يلغى", "يعدل")
_ATTRIBUTION_HINTS = ("قال", "أوضح", "أكد", "ذكر", "صرح", "according to", "stated", "declared", "selon")


@dataclass
class _ExtractionChunk:
    text: str
    markdown: str
    pages: int | None
    parser: str
    warning: str | None = None
    error: str | None = None


class DocumentIntelService:
    def __init__(self) -> None:
        settings = get_settings()
        self.max_upload_bytes = max(10, int(settings.document_intel_max_upload_mb)) * 1024 * 1024
        self.docling_timeout_seconds = max(10, int(settings.document_intel_docling_timeout_seconds))
        self.docling_max_bytes = max(1, int(settings.document_intel_docling_max_size_mb)) * 1024 * 1024
        self.docling_skip_for_ar = bool(settings.document_intel_docling_skip_for_ar)
        self.ocr_enabled = bool(settings.document_intel_ocr_enabled)
        self.ocr_force = bool(settings.document_intel_ocr_force)
        self.ocr_timeout_seconds = max(30, int(settings.document_intel_ocr_timeout_seconds))
        self.ocr_per_page_timeout_seconds = max(5, int(settings.document_intel_ocr_per_page_timeout_seconds))
        self.ocr_max_pages = max(1, int(settings.document_intel_ocr_max_pages))
        self.ocr_dpi = max(120, int(settings.document_intel_ocr_dpi))
        self.ocr_trigger_min_chars = max(200, int(settings.document_intel_ocr_trigger_min_chars))

    async def extract_pdf(
        self,
        *,
        filename: str,
        payload: bytes,
        language_hint: str = "ar",
        max_news_items: int = 8,
        max_data_points: int = 30,
    ) -> dict:
        safe_name = self.validate_upload(filename=filename, payload=payload)

        docling_strategy = self._should_attempt_docling(
            payload=payload,
            filename=safe_name,
            language_hint=language_hint,
        )

        if not docling_strategy["enabled"]:
            docling_chunk = _ExtractionChunk(
                text="",
                markdown="",
                pages=None,
                parser=str(docling_strategy["parser"]),
                warning=str(docling_strategy["warning"]),
            )
        else:
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
            except Exception as exc:  # noqa: BLE001
                logger.warning("docling_unexpected_error", error=str(exc))
                docling_chunk = _ExtractionChunk(
                    text="",
                    markdown="",
                    pages=None,
                    parser="docling_error",
                    warning="Docling failed unexpectedly; using fallback parser.",
                    error=str(exc),
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
        paragraphs = self._split_paragraphs(normalized_text)
        if self._should_run_ocr(normalized_text, paragraphs):
            ocr_chunk = await asyncio.to_thread(self._extract_with_ocr, payload, safe_name, language_hint)
            if ocr_chunk.warning:
                warnings.append(ocr_chunk.warning)
            if ocr_chunk.text.strip():
                extraction = ocr_chunk
                normalized_text = self._normalize_text(ocr_chunk.text)
                paragraphs = self._split_paragraphs(normalized_text)
        if not normalized_text:
            warnings.append("No selectable text found in PDF. OCR pipeline is required for scanned documents.")
        detected_language = self._detect_language(normalized_text)
        headings = self._extract_headings(extraction.markdown, normalized_text)
        news_candidates = self._extract_news_candidates(
            paragraphs,
            max_news_items=max_news_items,
            detected_language=detected_language,
            language_hint=self._normalize_lang(language_hint),
        )
        document_summary = self.summarize_document(
            normalized_text,
            headings=headings,
            news_candidates=news_candidates,
        )
        document_type = self.classify_document_type(
            normalized_text,
            filename=safe_name,
            headings=headings,
        )
        claims = self.extract_claims(
            paragraphs,
            document_type=document_type,
            max_claims=max(4, min(12, max_news_items + 4)),
        )
        entities = self.extract_entities(paragraphs, max_entities=14)
        story_angles = self.generate_story_angles(
            normalized_text,
            document_type=document_type,
            news_candidates=news_candidates,
            claims=claims,
            entities=entities,
            max_angles=4,
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
            "document_summary": document_summary,
            "document_type": document_type,
            "headings": headings,
            "news_candidates": news_candidates,
            "claims": claims,
            "entities": entities,
            "story_angles": story_angles,
            "data_points": data_points,
            "warnings": warnings,
            "preview_text": normalized_text[:2500],
        }

    def validate_upload(self, *, filename: str, payload: bytes) -> str:
        safe_name = self._safe_filename(filename)
        if not payload:
            raise ValueError("Uploaded file is empty")
        if len(payload) > self.max_upload_bytes:
            raise ValueError(
                f"File exceeds {int(self.max_upload_bytes / (1024 * 1024))}MB limit"
            )
        if not safe_name.lower().endswith(".pdf"):
            raise ValueError("Only PDF files are supported in this phase")
        return safe_name

    def _should_attempt_docling(self, *, payload: bytes, filename: str, language_hint: str) -> dict[str, str | bool]:
        lang = self._normalize_lang(language_hint)
        if len(payload) > self.docling_max_bytes:
            return {
                "enabled": False,
                "parser": "docling_skipped_large_file",
                "warning": (
                    f"File is larger than {int(self.docling_max_bytes / (1024 * 1024))}MB; "
                    "skipping Docling and using fallback parser."
                ),
            }
        if self.docling_skip_for_ar and lang == "ar":
            lower_name = filename.lower()
            gazette_like = bool(re.search(r"(a20\d{4,}|journal|gazette|official)", lower_name))
            if gazette_like or len(payload) >= 2 * 1024 * 1024:
                return {
                    "enabled": False,
                    "parser": "docling_skipped_strategy",
                    "warning": "Docling skipped by strategy for large/scanned Arabic document; using OCR-first fallback.",
                }
        return {"enabled": True, "parser": "docling", "warning": ""}

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

    def _should_run_ocr(self, normalized_text: str, paragraphs: list[str]) -> bool:
        if not self.ocr_enabled:
            return False
        if self.ocr_force:
            return True
        if not normalized_text:
            return True
        if len(normalized_text) < self.ocr_trigger_min_chars:
            return True
        if len(paragraphs) < 3 and len(normalized_text) < (self.ocr_trigger_min_chars * 2):
            return True
        return False

    def _extract_with_ocr(self, payload: bytes, filename: str, language_hint: str) -> _ExtractionChunk:
        missing_tools = [tool for tool in ("pdftoppm", "tesseract") if shutil.which(tool) is None]
        if missing_tools:
            return _ExtractionChunk(
                text="",
                markdown="",
                pages=None,
                parser="ocr_missing_tools",
                warning=f"OCR skipped: missing tools ({', '.join(missing_tools)}).",
            )

        lang = self._ocr_lang(language_hint)
        end_ts = time.monotonic() + self.ocr_timeout_seconds
        try:
            with tempfile.TemporaryDirectory(prefix="doc-intel-ocr-") as temp_dir:
                temp_path = Path(temp_dir) / filename
                temp_path.write_bytes(payload)

                prefix = Path(temp_dir) / "ocr-page"
                self._run_subprocess_with_deadline(
                    [
                        "pdftoppm",
                        "-r",
                        str(self.ocr_dpi),
                        "-f",
                        "1",
                        "-l",
                        str(self.ocr_max_pages),
                        "-png",
                        str(temp_path),
                        str(prefix),
                    ],
                    end_ts=end_ts,
                )

                images = sorted(Path(temp_dir).glob("ocr-page-*.png"))
                if not images:
                    return _ExtractionChunk(
                        text="",
                        markdown="",
                        pages=None,
                        parser="ocr_no_images",
                        warning="OCR skipped: no images generated from PDF.",
                    )

                texts: list[str] = []
                processed = 0
                timeout_hit = False
                for image in images:
                    try:
                        out = self._run_subprocess_with_deadline(
                            ["tesseract", str(image), "stdout", "-l", lang, "--psm", "6"],
                            end_ts=end_ts,
                            per_call_timeout=self.ocr_per_page_timeout_seconds,
                        )
                    except TimeoutError:
                        timeout_hit = True
                        break
                    block = self._normalize_text(out)
                    if block:
                        texts.append(block)
                    processed += 1

                merged = self._normalize_text("\n\n".join(texts))
                if not merged:
                    return _ExtractionChunk(
                        text="",
                        markdown="",
                        pages=processed,
                        parser="ocr_empty",
                        warning=(
                            f"OCR returned empty text after {processed} page(s)."
                            if processed
                            else "OCR returned empty text."
                        ),
                    )
                return _ExtractionChunk(
                    text=merged,
                    markdown="",
                    pages=processed,
                    parser="ocr_tesseract_partial" if timeout_hit else "ocr_tesseract",
                    warning=(
                        f"OCR partially completed on {processed} page(s) due to timeout."
                        if timeout_hit
                        else f"OCR used on {processed} page(s)."
                    ),
                )
        except TimeoutError:
            return _ExtractionChunk(
                text="",
                markdown="",
                pages=None,
                parser="ocr_timeout",
                warning=f"OCR timed out after {self.ocr_timeout_seconds}s.",
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("ocr_extract_failed", error=str(exc))
            return _ExtractionChunk(
                text="",
                markdown="",
                pages=None,
                parser="ocr_failed",
                warning=f"OCR failed: {exc}",
                error=str(exc),
            )

    def _run_subprocess_with_deadline(
        self,
        cmd: list[str],
        *,
        end_ts: float,
        per_call_timeout: int | None = None,
    ) -> str:
        remaining = end_ts - time.monotonic()
        if remaining <= 1:
            raise TimeoutError("deadline reached")
        timeout = remaining
        if per_call_timeout is not None:
            timeout = min(timeout, float(per_call_timeout))
        timeout = max(2, int(timeout))
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError(f"{cmd[0]} timed out after {timeout}s") from exc
        if proc.returncode != 0:
            stderr = (proc.stderr or proc.stdout or "").strip()
            raise RuntimeError(f"{cmd[0]} failed: {stderr[:400]}")
        return proc.stdout or ""

    @staticmethod
    def _ocr_lang(language_hint: str) -> str:
        mapping = {
            "ar": "ara",
            "en": "eng",
            "fr": "fra",
            "auto": "ara+eng+fra",
        }
        return mapping.get((language_hint or "auto").strip().lower(), "ara+eng")

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
        if len(output) < 3 and len(text) > 400:
            merged = DocumentIntelService._merge_lines_to_blocks(text)
            if merged:
                output = merged
        return output

    @staticmethod
    def _merge_lines_to_blocks(text: str) -> list[str]:
        lines = [re.sub(r"\s+", " ", line).strip(" -•\t") for line in text.splitlines()]
        lines = [line for line in lines if line]
        blocks: list[str] = []
        buffer: list[str] = []
        size = 0
        for line in lines:
            buffer.append(line)
            size += len(line)
            if size >= 180 or line.endswith((".", "؟", "!", "؛", ":")):
                joined = " ".join(buffer).strip()
                if len(joined) >= 60:
                    blocks.append(joined)
                buffer = []
                size = 0
        if buffer:
            joined = " ".join(buffer).strip()
            if len(joined) >= 60:
                blocks.append(joined)
        return blocks[:120]

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
        if not selected:
            selected = [item for item in scored if len(item[1]) >= 80][: max(1, min(3, max_news_items))]

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

    def summarize_document(
        self,
        text: str,
        *,
        headings: list[str],
        news_candidates: list[dict],
    ) -> str:
        opening = self._split_paragraphs(text)[:3]
        summary_parts: list[str] = []
        if headings:
            summary_parts.append(f"الوثيقة تركز على: {headings[0]}.")
        if news_candidates:
            top = news_candidates[0]
            summary_parts.append(
                f"أبرز ما فيها: {top.get('headline') or 'مادة خبرية رئيسية'}."
            )
        if opening:
            first = opening[0][:260].strip()
            if first:
                summary_parts.append(first)
        if len(summary_parts) < 2 and len(opening) > 1:
            second = opening[1][:220].strip()
            if second:
                summary_parts.append(second)
        merged = " ".join(part.strip() for part in summary_parts if part and part.strip())
        merged = re.sub(r"\s+", " ", merged).strip()
        return merged[:700]

    def classify_document_type(self, text: str, *, filename: str, headings: list[str]) -> str:
        lower_name = (filename or "").lower()
        normalized_text = self._normalize_latin((text or "")[:4000]).lower()
        normalized_headings = self._normalize_latin(" ".join(headings or [])).lower()
        combined = f"{normalized_text}\n{normalized_headings}\n{lower_name}"

        for doc_type, hints in _DOCUMENT_TYPE_HINTS.items():
            for hint in hints:
                hint_norm = self._normalize_latin(hint).lower()
                if hint_norm and hint_norm in combined:
                    return doc_type

        if len(text or "") < 800 and ("بيان" in text or "statement" in combined):
            return "statement"
        if len(_NUMBER_PATTERN.findall(text or "")) >= 12:
            return "report"
        if not (text or "").strip():
            return "scanned_document"
        return "report"

    def extract_claims(self, paragraphs: list[str], *, document_type: str, max_claims: int) -> list[dict]:
        claims: list[dict] = []
        rank = 0
        for para in paragraphs:
            paragraph = re.sub(r"\s+", " ", para).strip()
            if len(paragraph) < 60:
                continue
            if not self._looks_like_claim(paragraph):
                continue
            claim_type = self._classify_claim_type(paragraph, document_type=document_type)
            risk_level = self._claim_risk_level(paragraph, claim_type=claim_type, document_type=document_type)
            confidence = self._claim_confidence(paragraph, claim_type=claim_type)
            claims.append(
                {
                    "text": paragraph[:420],
                    "type": claim_type,
                    "confidence": confidence,
                    "risk_level": risk_level,
                }
            )
            rank += 1
            if rank >= max_claims:
                break
        return claims

    def extract_entities(self, paragraphs: list[str], *, max_entities: int = 12) -> list[dict]:
        collected: list[dict] = []
        seen: set[str] = set()
        for para in paragraphs:
            for entity in self._extract_entities(para):
                key = entity.strip().lower()
                if not key or key in seen:
                    continue
                seen.add(key)
                collected.append(
                    {
                        "name": entity,
                        "type": self._entity_type(entity),
                    }
                )
                if len(collected) >= max_entities:
                    return collected
        return collected

    def generate_story_angles(
        self,
        text: str,
        *,
        document_type: str,
        news_candidates: list[dict],
        claims: list[dict],
        entities: list[dict],
        max_angles: int,
    ) -> list[dict]:
        angles: list[dict] = []
        if news_candidates:
            lead = news_candidates[0]
            angles.append(
                {
                    "title": f"ما الذي تغيّره الوثيقة حول: {lead.get('headline', 'الملف الرئيسي')}",
                    "why_it_matters": "لأن الوثيقة تحتوي على مادة قابلة للتحويل إلى خبر أو متابعة مباشرة.",
                }
            )
        if claims:
            high_risk = next((claim for claim in claims if claim["risk_level"] == "high"), None)
            if high_risk:
                angles.append(
                    {
                        "title": "ما الادعاءات التي تحتاج تحققًا قبل النشر؟",
                        "why_it_matters": "لأن بعض ما ورد في الوثيقة يحمل حساسية تحريرية أو قانونية ويحتاج تدقيقًا إضافيًا.",
                    }
                )
        if document_type == "official_gazette":
            angles.append(
                {
                    "title": "ما القرارات أو المواد التي ستؤثر عمليًا على الجمهور أو المؤسسات؟",
                    "why_it_matters": "لأن الوثائق الرسمية لا تهم بصيغتها فقط، بل بأثرها التنفيذي المباشر.",
                }
            )
        elif document_type == "statement":
            angles.append(
                {
                    "title": "ما الرسالة السياسية أو المؤسسية الأساسية في هذا البيان؟",
                    "why_it_matters": "لأن قيمة البيان التحريرية تكمن في الرسالة والجهة والهدف من الإعلان.",
                }
            )
        elif entities:
            angles.append(
                {
                    "title": f"ما دور الجهات الواردة مثل {entities[0]['name']} في هذه الوثيقة؟",
                    "why_it_matters": "لأن تتبع الأطراف الفاعلة يساعد على توسيع المادة إلى قصة أو متابعة أعمق.",
                }
            )
        return angles[:max_angles]

    def _looks_like_claim(self, paragraph: str) -> bool:
        if _DATE_PATTERN.search(paragraph) or _NUMBER_PATTERN.search(paragraph):
            return True
        if any(hint in paragraph for hint in _ARABIC_CLAIM_VERBS):
            return True
        normalized = self._normalize_latin(paragraph).lower()
        return any(token in normalized for token in ("announced", "confirmed", "stated", "selon", "rapport"))

    def _classify_claim_type(self, paragraph: str, *, document_type: str) -> str:
        normalized = self._normalize_latin(paragraph).lower()
        if any(token in paragraph for token in _LEGAL_HINTS):
            return "legal"
        if any(token in paragraph for token in _STATISTICAL_HINTS) or _NUMBER_PATTERN.search(paragraph):
            return "statistical"
        if any(token in paragraph for token in _ATTRIBUTION_HINTS) or any(token in normalized for token in ("according to", "selon", "stated", "declared")):
            return "attribution"
        if document_type == "official_gazette":
            return "legal"
        return "factual"

    def _claim_risk_level(self, paragraph: str, *, claim_type: str, document_type: str) -> str:
        if claim_type == "legal" or document_type == "official_gazette":
            return "high"
        if claim_type == "attribution":
            return "medium"
        if claim_type == "statistical":
            return "medium"
        if len(paragraph) > 240:
            return "medium"
        return "low"

    def _claim_confidence(self, paragraph: str, *, claim_type: str) -> float:
        score = 0.54
        if _NUMBER_PATTERN.search(paragraph):
            score += 0.12
        if _DATE_PATTERN.search(paragraph):
            score += 0.08
        if self._extract_entities(paragraph):
            score += 0.08
        if claim_type in {"legal", "statistical"}:
            score += 0.08
        return round(min(score, 0.94), 2)

    @staticmethod
    def _entity_type(value: str) -> str:
        lowered = value.lower()
        if any(token in lowered for token in ("وزارة", "حكومة", "government", "ministry", "ministere", "مجلس", "parliament", "رئاسة")):
            return "organization"
        if any(token in lowered for token in ("الجزائر", "france", "paris", "oran", "constantine")):
            return "location"
        return "organization"

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
