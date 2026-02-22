"""
Echorouk Editorial OS — Hashing & Deduplication Utilities
=======================================================
Idempotency Principle: Processing the same input twice
must result in a single record. (Rule #3)
"""

import hashlib
import re
import unicodedata
from rapidfuzz import fuzz


def normalize_text(text: str) -> str:
    """Normalize text for comparison: lowercase, remove diacritics, strip noise words."""
    if not text:
        return ""

    # Remove Arabic diacritics (tashkeel)
    text = re.sub(r'[\u0610-\u061A\u064B-\u065F\u06D6-\u06DC\u06DF-\u06E8\u06EA-\u06ED]', '', text)

    # Lowercase
    text = text.lower().strip()

    # Remove common noise words
    noise_words = ["عاجل", "breaking", "urgent", "حصري", "خاص", "بالفيديو", "بالصور"]
    for word in noise_words:
        text = text.replace(word, "")

    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text).strip()

    # Remove special characters but keep Arabic and Latin letters
    text = re.sub(r'[^\w\s]', '', text)

    return text


def generate_unique_hash(source: str, url: str, title: str) -> str:
    """
    Generate a deterministic unique hash for deduplication.
    Uses: sha1(source + url + normalized_title)
    This is better than relying on GUID alone.
    """
    normalized_title = normalize_text(title)
    raw = f"{source}|{url}|{normalized_title}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def generate_content_hash(content: str) -> str:
    """MD5 hash of content for exact-match deduplication."""
    if not content:
        return ""
    return hashlib.md5(content.encode("utf-8")).hexdigest()


def is_duplicate_title(new_title: str, existing_titles: list[str], threshold: float = 0.70) -> bool:
    """
    Fuzzy title comparison using Levenshtein distance.
    Returns True if the new title matches any existing title above the threshold.
    """
    normalized_new = normalize_text(new_title)
    if not normalized_new:
        return False

    for existing in existing_titles:
        normalized_existing = normalize_text(existing)
        if not normalized_existing:
            continue

        # Use token_sort_ratio for better matching of reworded titles
        similarity = fuzz.token_sort_ratio(normalized_new, normalized_existing) / 100.0

        if similarity >= threshold:
            return True

    return False


def generate_trace_id() -> str:
    """Generate a unique trace ID for observability."""
    import uuid
    return uuid.uuid4().hex[:16]
