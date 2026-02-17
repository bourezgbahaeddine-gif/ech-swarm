from __future__ import annotations

import re
from typing import Iterable

from app.services.cache_service import cache_service
from app.utils.hashing import normalize_text


TOKEN_RE = re.compile(r"[\u0600-\u06FFA-Za-z\u00C0-\u024F0-9]{3,}")
STOP = {
    "الذي", "التي", "هذا", "هذه", "هناك", "then", "with", "from", "dans", "pour", "avec",
    "news", "google", "article", "video",
}


def extract_keywords(text: str | None, limit: int = 8) -> list[str]:
    raw = normalize_text(text or "")
    out: list[str] = []
    seen: set[str] = set()
    for m in TOKEN_RE.finditer(raw):
        tok = m.group(0).strip()
        if not tok or tok in STOP:
            continue
        if tok in seen:
            continue
        seen.add(tok)
        out.append(tok)
        if len(out) >= limit:
            break
    return out


async def bump_keyword_interactions(keywords: Iterable[str], weight: int = 1) -> None:
    for kw in keywords:
        norm = normalize_text(kw)
        if not norm:
            continue
        for _ in range(max(1, weight)):
            await cache_service.increment_counter(f"trend_interaction:{norm}")

