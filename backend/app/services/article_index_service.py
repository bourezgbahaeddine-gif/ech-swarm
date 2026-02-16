"""
Article indexing service:
- builds normalized profile
- extracts topics/entities
- chunks article text
- stores vectors in pgvector
"""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlparse, urlunparse

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models import (
    Article,
    ArticleChunk,
    ArticleEntity,
    ArticleProfile,
    ArticleTopic,
    ArticleVector,
)

logger = get_logger("article_index_service")


ARABIC_RE = re.compile(r"[\u0600-\u06FF]")
LATIN_WORD_RE = re.compile(r"\b[A-Z][a-zA-Z\-]{2,}\b")
ARABIC_WORD_RE = re.compile(r"[\u0621-\u064A]{3,}")


@dataclass
class NormalizedArticle:
    language: str
    title: str
    summary: str
    content: str
    canonical_url: str
    search_text: str


def _canonicalize_url(url: str | None) -> str:
    if not url:
        return ""
    try:
        parsed = urlparse(url.strip())
        clean = parsed._replace(query="", fragment="")
        return urlunparse(clean)
    except Exception:
        return url


def _detect_language(text: str) -> str:
    if ARABIC_RE.search(text or ""):
        return "ar"
    # Very simple fallback; newsroom works with ar/fr/en primarily.
    if any(ch in (text or "").lower() for ch in ["é", "è", "à", "ç", "ù", "ê", "ô", "î"]):
        return "fr"
    return "en"


def _normalize_text(text: str | None) -> str:
    if not text:
        return ""
    t = re.sub(r"\s+", " ", text).strip()
    return t


def _split_chunks(text: str, chunk_size: int = 700) -> list[str]:
    if not text:
        return []
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
    chunks: list[str] = []
    current = ""
    for p in paragraphs:
        if not current:
            current = p
            continue
        if len(current) + len(p) + 1 <= chunk_size:
            current = f"{current}\n{p}"
        else:
            chunks.append(current)
            current = p
    if current:
        chunks.append(current)
    return chunks


def _extract_topics(article: Article, normalized: NormalizedArticle) -> list[tuple[str, float, str]]:
    topics: list[tuple[str, float, str]] = []
    if article.category:
        topics.append((article.category.value, 0.95, "category"))
    for kw in (article.keywords or [])[:12]:
        if isinstance(kw, str) and kw.strip():
            topics.append((kw.strip().lower(), 0.72, "keywords"))
    if not topics:
        title_tokens = [w.lower() for w in re.findall(r"\w+", normalized.title) if len(w) >= 4][:8]
        topics.extend((w, 0.55, "title") for w in title_tokens)
    # de-dup
    seen = set()
    deduped = []
    for topic, conf, source in topics:
        k = topic.strip().lower()
        if not k or k in seen:
            continue
        seen.add(k)
        deduped.append((k, conf, source))
    return deduped[:20]


def _extract_entities(normalized: NormalizedArticle) -> list[tuple[str, str, float, str]]:
    entities: list[tuple[str, str, float, str]] = []
    for m in LATIN_WORD_RE.findall(normalized.title + " " + normalized.summary):
        entities.append((m, "person_or_org", 0.65, "rule"))
    for m in ARABIC_WORD_RE.findall(normalized.title + " " + normalized.summary):
        if len(m) >= 4:
            entities.append((m, "arabic_term", 0.55, "rule"))
    seen = set()
    out = []
    for entity, etype, conf, source in entities:
        key = (entity.lower(), etype)
        if key in seen:
            continue
        seen.add(key)
        out.append((entity, etype, conf, source))
    return out[:30]


def _hash_embedding(text: str, dim: int = 256) -> list[float]:
    # Deterministic lightweight embedding (fallback, no external API).
    base = hashlib.sha256((text or "").encode("utf-8")).digest()
    values = []
    seed = base
    while len(values) < dim:
        seed = hashlib.sha256(seed).digest()
        for b in seed:
            values.append((b / 255.0) * 2.0 - 1.0)
            if len(values) >= dim:
                break
    norm = math.sqrt(sum(v * v for v in values)) or 1.0
    return [v / norm for v in values]


def _checksum(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def _normalize_article(article: Article) -> NormalizedArticle:
    title = _normalize_text(article.title_ar or article.original_title)
    summary = _normalize_text(article.summary or "")
    content = _normalize_text(article.body_html or article.original_content or summary or title)
    search_text = _normalize_text(" ".join([title, summary, content, article.source_name or ""]))
    language = _detect_language(" ".join([title, summary, content]))
    return NormalizedArticle(
        language=language,
        title=title,
        summary=summary,
        content=content,
        canonical_url=_canonicalize_url(article.original_url),
        search_text=search_text,
    )


def _archive_code(article_id: int) -> str:
    return f"ART-{datetime.utcnow():%Y%m%d}-{article_id:08d}"


class ArticleIndexService:
    async def upsert_article(self, db: AsyncSession, article: Article) -> None:
        normalized = _normalize_article(article)

        existing_profile = await db.execute(
            select(ArticleProfile).where(ArticleProfile.article_id == article.id)
        )
        profile = existing_profile.scalar_one_or_none()
        if profile is None:
            profile = ArticleProfile(
                article_id=article.id,
                archive_code=_archive_code(article.id),
            )
            db.add(profile)

        profile.language = normalized.language
        profile.normalized_title = normalized.title
        profile.normalized_summary = normalized.summary
        profile.normalized_content = normalized.content
        profile.canonical_url = normalized.canonical_url
        profile.source_name = article.source_name
        profile.category = article.category.value if article.category else None
        profile.editorial_status = article.status.value if article.status else None
        profile.search_text = normalized.search_text
        profile.metadata_json = {
            "importance_score": article.importance_score,
            "urgency": article.urgency.value if article.urgency else None,
            "is_breaking": article.is_breaking,
            "published_at": article.published_at.isoformat() if article.published_at else None,
        }
        profile.updated_at = datetime.utcnow()

        await db.flush()

        # Reset generated index records for deterministic rebuild.
        await db.execute(delete(ArticleTopic).where(ArticleTopic.article_id == article.id))
        await db.execute(delete(ArticleEntity).where(ArticleEntity.article_id == article.id))
        await db.execute(delete(ArticleVector).where(ArticleVector.article_id == article.id))
        await db.execute(delete(ArticleChunk).where(ArticleChunk.article_id == article.id))

        for topic, conf, source in _extract_topics(article, normalized):
            db.add(ArticleTopic(article_id=article.id, topic=topic, confidence=conf, source=source))

        for entity, etype, conf, source in _extract_entities(normalized):
            db.add(
                ArticleEntity(
                    article_id=article.id,
                    entity=entity,
                    entity_type=etype,
                    confidence=conf,
                    source=source,
                )
            )

        # Title + summary vectors
        title_hash = _checksum(normalized.title)
        summary_hash = _checksum(normalized.summary or normalized.content[:500])
        db.add(
            ArticleVector(
                article_id=article.id,
                chunk_id=None,
                vector_type="title",
                model="hash-v1",
                dim=256,
                embedding=_hash_embedding(normalized.title),
                content_hash=title_hash,
            )
        )
        db.add(
            ArticleVector(
                article_id=article.id,
                chunk_id=None,
                vector_type="summary",
                model="hash-v1",
                dim=256,
                embedding=_hash_embedding(normalized.summary or normalized.content[:500]),
                content_hash=summary_hash,
            )
        )

        # Chunk vectors
        for idx, chunk_text in enumerate(_split_chunks(normalized.content), start=1):
            chunk = ArticleChunk(
                article_id=article.id,
                chunk_index=idx,
                language=normalized.language,
                content=chunk_text,
                content_length=len(chunk_text),
            )
            db.add(chunk)
            await db.flush()
            db.add(
                ArticleVector(
                    article_id=article.id,
                    chunk_id=chunk.id,
                    vector_type="chunk",
                    model="hash-v1",
                    dim=256,
                    embedding=_hash_embedding(chunk_text),
                    content_hash=_checksum(chunk_text),
                )
            )

        logger.info(
            "article_index_upserted",
            article_id=article.id,
            language=normalized.language,
            chunks=len(_split_chunks(normalized.content)),
        )


article_index_service = ArticleIndexService()
