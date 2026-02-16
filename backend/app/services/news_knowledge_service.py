"""
News knowledge service:
- local SimHash fingerprinting and near-duplicate detection
- story clustering for same event coverage across sources
- lightweight relation graph (sequence/impact/contrast/related)
- weighted taxonomy scoring (rule-based, explainable)
"""

from __future__ import annotations

import hashlib
import math
import re
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Iterable

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models import (
    Article,
    ArticleEntity,
    ArticleFingerprint,
    ArticleProfile,
    ArticleRelation,
    NewsCategory,
    StoryCluster,
    StoryClusterMember,
)

logger = get_logger("news_knowledge_service")

TOKEN_RE = re.compile(r"[\u0600-\u06FFA-Za-z\u00C0-\u024F0-9]{2,}")
SPACE_RE = re.compile(r"\s+")

SEQUENCE_TERMS = {"تأجيل", "استكمال", "ردود", "متابعة", "update", "follow-up", "suite", "poursuite"}
IMPACT_TERMS = {"تأثير", "انعكاس", "أسعار", "تضخم", "impact", "effet", "prix", "inflation"}
CONTRAST_TERMS = {"نفي", "تكذيب", "ينفي", "dément", "denies", "refute", "démenti"}

DUPLICATE_SCORE_THRESHOLD = 0.84
CLUSTER_SCORE_THRESHOLD = 0.68
ENTITY_CLUSTER_MIN_SHARED = 2
ENTITY_CLUSTER_MAX_HOURS = 48

TAXONOMY_WEIGHTS: dict[NewsCategory, dict[str, float]] = {
    NewsCategory.POLITICS: {
        "رئيس": 2.0, "وزارة": 1.8, "حكومة": 1.8, "برلمان": 1.7, "دبلوماس": 1.6,
        "president": 1.7, "gouvernement": 1.7, "parlement": 1.6,
    },
    NewsCategory.ECONOMY: {
        "اقتصاد": 2.0, "طاقة": 2.2, "نفط": 2.2, "غاز": 2.2, "سوناطراك": 2.2, "بورصة": 1.9,
        "énergie": 2.2, "energie": 2.2, "pétrole": 2.1, "petrole": 2.1, "gas": 2.0, "inflation": 1.9,
    },
    NewsCategory.SPORTS: {
        "مباراة": 2.0, "هدف": 2.0, "فريق": 1.8, "دوري": 1.8, "كرة": 1.6,
        "match": 2.0, "football": 1.8, "ligue": 1.7,
    },
    NewsCategory.TECHNOLOGY: {
        "تقنية": 1.9, "تكنولوجيا": 1.9, "ذكاء": 1.8, "رقمنة": 1.7,
        "technology": 1.9, "ai": 1.8, "numérique": 1.8, "numerique": 1.8,
    },
    NewsCategory.HEALTH: {
        "صحة": 2.0, "مستشفى": 1.8, "دواء": 1.8, "وباء": 1.7,
        "santé": 2.0, "sante": 2.0, "hôpital": 1.8, "hopital": 1.8,
    },
    NewsCategory.ENVIRONMENT: {
        "بيئة": 2.0, "مناخ": 2.0, "حرائق": 1.9, "فيضانات": 1.9,
        "climat": 2.0, "environnement": 2.0, "incendies": 1.8,
    },
    NewsCategory.SOCIETY: {
        "مجتمع": 1.8, "تعليم": 1.8, "مدرسة": 1.7, "جامعة": 1.7, "نقل": 1.7,
        "société": 1.8, "societe": 1.8, "éducation": 1.8, "education": 1.8,
    },
}


def _normalize_text(text: str | None) -> str:
    if not text:
        return ""
    text = text.lower().strip()
    text = SPACE_RE.sub(" ", text)
    return text


def _tokens(text: str) -> list[str]:
    return [m.group(0).lower() for m in TOKEN_RE.finditer(text)]


def _simhash(tokens: Iterable[str], bits: int = 64) -> int:
    weights = [0] * bits
    for tok in tokens:
        h = int(hashlib.sha1(tok.encode("utf-8")).hexdigest()[:16], 16)
        for i in range(bits):
            bit = (h >> i) & 1
            weights[i] += 1 if bit else -1
    out = 0
    for i, w in enumerate(weights):
        if w >= 0:
            out |= (1 << i)
    return out


def _to_signed64(v: int) -> int:
    return v if v < (1 << 63) else v - (1 << 64)


def _to_unsigned64(v: int) -> int:
    return v if v >= 0 else v + (1 << 64)


def _hamming_ratio(a: int, b: int, bits: int = 64) -> float:
    dist = (a ^ b).bit_count()
    return 1.0 - (dist / float(bits))


def _shingles(tokens: list[str], n: int = 2, limit: int = 128) -> set[str]:
    if len(tokens) < n:
        return set(tokens[:limit])
    out: set[str] = set()
    for i in range(len(tokens) - n + 1):
        out.add(" ".join(tokens[i:i + n]))
        if len(out) >= limit:
            break
    return out


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / float(max(1, union))


def _taxonomy_scores(text: str) -> dict[NewsCategory, float]:
    scores: dict[NewsCategory, float] = defaultdict(float)
    t = _normalize_text(text)
    for category, keywords in TAXONOMY_WEIGHTS.items():
        for kw, weight in keywords.items():
            if kw in t:
                scores[category] += weight
    return dict(scores)


def _select_taxonomy(scores: dict[NewsCategory, float]) -> tuple[NewsCategory | None, float]:
    if not scores:
        return None, 0.0
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    top_cat, top_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else 0.0
    if top_score < 1.5:
        return None, 0.0
    if abs(top_score - second_score) <= 0.75:
        return None, 0.0
    confidence = min(1.0, top_score / (top_score + second_score + 1e-6))
    return top_cat, confidence


class NewsKnowledgeService:
    @staticmethod
    def _safe_cluster_label(label: str | None) -> str | None:
        if not label:
            return None
        value = _normalize_text(label)
        return value[:256]

    async def process_article(self, db: AsyncSession, article: Article) -> None:
        text = _normalize_text(
            " ".join(
                [
                    article.title_ar or article.original_title or "",
                    article.summary or "",
                    article.original_content or "",
                ]
            )
        )
        toks = _tokens(text)
        if len(toks) < 3:
            return

        article_simhash = _simhash(toks)
        article_shingles = _shingles(toks, n=2)

        await self._upsert_fingerprint(db, article.id, article_simhash, article_shingles, len(toks))
        await self._apply_taxonomy_hints(db, article, text)
        await self._cluster_and_link(db, article, article_simhash, article_shingles)

    async def _upsert_fingerprint(
        self,
        db: AsyncSession,
        article_id: int,
        simhash_value: int,
        shingles: set[str],
        token_count: int,
    ) -> None:
        result = await db.execute(select(ArticleFingerprint).where(ArticleFingerprint.article_id == article_id))
        fp = result.scalar_one_or_none()
        if fp is None:
            fp = ArticleFingerprint(article_id=article_id)
            db.add(fp)
        fp.simhash = _to_signed64(simhash_value)
        fp.shingles = sorted(list(shingles))[:128]
        fp.token_count = token_count
        fp.updated_at = datetime.utcnow()
        await db.flush()

    async def _apply_taxonomy_hints(self, db: AsyncSession, article: Article, text: str) -> None:
        scores = _taxonomy_scores(text)
        category, confidence = _select_taxonomy(scores)

        if article.category is None and category is not None:
            article.category = category

        profile_result = await db.execute(select(ArticleProfile).where(ArticleProfile.article_id == article.id))
        profile = profile_result.scalar_one_or_none()
        if profile:
            data = dict(profile.metadata_json or {})
            data["taxonomy_scores"] = {k.value: round(v, 3) for k, v in scores.items()}
            data["taxonomy_suggested"] = category.value if category else None
            data["taxonomy_confidence"] = round(confidence, 4)
            profile.metadata_json = data
            profile.updated_at = datetime.utcnow()

    async def _cluster_and_link(
        self,
        db: AsyncSession,
        article: Article,
        article_simhash: int,
        article_shingles: set[str],
    ) -> None:
        window_start = datetime.utcnow() - timedelta(days=14)
        rows = await db.execute(
            select(ArticleFingerprint, Article)
            .join(Article, Article.id == ArticleFingerprint.article_id)
            .where(
                and_(
                    ArticleFingerprint.article_id != article.id,
                    Article.crawled_at >= window_start,
                )
            )
            .order_by(Article.crawled_at.desc())
            .limit(1000)
        )
        candidates = rows.all()
        if not candidates:
            await self._ensure_single_cluster(db, article, label=article.title_ar or article.original_title)
            return

        candidate_ids = [cand_article.id for _, cand_article in candidates]
        entity_rows = await db.execute(
            select(ArticleEntity.article_id, ArticleEntity.entity).where(
                ArticleEntity.article_id.in_([article.id] + candidate_ids)
            )
        )
        entity_map: dict[int, set[str]] = defaultdict(set)
        for row in entity_rows:
            if row.entity:
                entity_map[int(row.article_id)].add(str(row.entity).lower())

        current_entities = entity_map.get(article.id, set())
        best_dup: tuple[Article, float] | None = None
        best_cluster: tuple[Article, float] | None = None
        relation_candidates: list[tuple[Article, float]] = []

        for fp, cand_article in candidates:
            simhash_score = _hamming_ratio(article_simhash, _to_unsigned64(int(fp.simhash)))
            cand_shingles = set(fp.shingles or [])
            jac = _jaccard(article_shingles, cand_shingles)
            score = 0.65 * simhash_score + 0.35 * jac

            shared_entities = len(current_entities & entity_map.get(cand_article.id, set()))
            age_hours = abs(
                (
                    (article.crawled_at or datetime.utcnow())
                    - (cand_article.crawled_at or datetime.utcnow())
                ).total_seconds()
                / 3600.0
            )
            entity_cluster_signal = (
                shared_entities >= ENTITY_CLUSTER_MIN_SHARED
                and age_hours <= ENTITY_CLUSTER_MAX_HOURS
            )

            if score >= 0.7:
                relation_candidates.append((cand_article, score))
            if score >= DUPLICATE_SCORE_THRESHOLD:
                if best_dup is None or score > best_dup[1]:
                    best_dup = (cand_article, score)
            elif score >= CLUSTER_SCORE_THRESHOLD or entity_cluster_signal:
                cluster_score = max(score, CLUSTER_SCORE_THRESHOLD) if entity_cluster_signal else score
                if best_cluster is None or cluster_score > best_cluster[1]:
                    best_cluster = (cand_article, cluster_score)

        anchor = best_dup or best_cluster
        if anchor is not None:
            anchor_article, anchor_score = anchor
            await self._attach_to_anchor_cluster(db, article, anchor_article, anchor_score)
            if best_dup is not None:
                await self._add_relation(
                    db,
                    from_article_id=article.id,
                    to_article_id=anchor_article.id,
                    relation_type="duplicate_variant",
                    score=anchor_score,
                    metadata={"reason": "simhash+jaccard"},
                )
        else:
            await self._ensure_single_cluster(db, article, label=article.title_ar or article.original_title)

        await self._infer_relations(db, article, relation_candidates[:20])

    async def _ensure_single_cluster(self, db: AsyncSession, article: Article, label: str | None) -> None:
        cluster_key = self._cluster_key(article, seed=label or str(article.id))
        cluster = await self._get_or_create_cluster(
            db,
            cluster_key,
            label=self._safe_cluster_label(label),
            category=article.category.value if article.category else None,
        )
        await self._upsert_cluster_member(db, cluster.id, article.id, score=1.0)

    async def _attach_to_anchor_cluster(
        self,
        db: AsyncSession,
        article: Article,
        anchor_article: Article,
        score: float,
    ) -> None:
        existing = await db.execute(
            select(StoryClusterMember).where(StoryClusterMember.article_id == anchor_article.id).limit(1)
        )
        anchor_member = existing.scalar_one_or_none()
        if anchor_member:
            cluster_id = anchor_member.cluster_id
        else:
            cluster_key = self._cluster_key(anchor_article, seed=anchor_article.title_ar or anchor_article.original_title or str(anchor_article.id))
            cluster = await self._get_or_create_cluster(
                db,
                cluster_key,
                label=self._safe_cluster_label(anchor_article.title_ar or anchor_article.original_title),
                category=anchor_article.category.value if anchor_article.category else None,
            )
            cluster_id = cluster.id
            await self._upsert_cluster_member(db, cluster_id, anchor_article.id, score=1.0)

        await self._upsert_cluster_member(db, cluster_id, article.id, score=score)

    async def _get_or_create_cluster(
        self,
        db: AsyncSession,
        cluster_key: str,
        label: str | None,
        category: str | None,
    ) -> StoryCluster:
        res = await db.execute(select(StoryCluster).where(StoryCluster.cluster_key == cluster_key))
        cluster = res.scalar_one_or_none()
        if cluster is None:
            cluster = StoryCluster(cluster_key=cluster_key, label=label, category=category, geography="DZ")
            db.add(cluster)
            await db.flush()
        else:
            if not cluster.label and label:
                cluster.label = label
            if not cluster.category and category:
                cluster.category = category
            cluster.updated_at = datetime.utcnow()
        return cluster

    async def _upsert_cluster_member(self, db: AsyncSession, cluster_id: int, article_id: int, score: float) -> None:
        res = await db.execute(
            select(StoryClusterMember).where(
                and_(
                    StoryClusterMember.cluster_id == cluster_id,
                    StoryClusterMember.article_id == article_id,
                )
            )
        )
        member = res.scalar_one_or_none()
        if member is None:
            db.add(StoryClusterMember(cluster_id=cluster_id, article_id=article_id, score=score))
        else:
            member.score = max(member.score, score)

    async def _infer_relations(self, db: AsyncSession, article: Article, candidates: list[tuple[Article, float]]) -> None:
        if not candidates:
            return

        current_entities = await self._article_entities(db, article.id)
        current_text = _normalize_text(f"{article.title_ar or article.original_title or ''} {article.summary or ''}")
        current_terms = set(_tokens(current_text))

        for cand, sim_score in candidates:
            if cand.id == article.id:
                continue
            cand_entities = await self._article_entities(db, cand.id)
            shared_entities = current_entities & cand_entities
            if not shared_entities and sim_score < 0.80:
                continue

            cand_text = _normalize_text(f"{cand.title_ar or cand.original_title or ''} {cand.summary or ''}")
            cand_terms = set(_tokens(cand_text))
            relation_type = "related"
            relation_score = sim_score

            if shared_entities and (current_terms & SEQUENCE_TERMS or cand_terms & SEQUENCE_TERMS):
                relation_type = "sequence"
                relation_score = min(1.0, sim_score + 0.08)
            elif shared_entities and (current_terms & IMPACT_TERMS):
                relation_type = "impact"
                relation_score = min(1.0, sim_score + 0.06)
            elif (current_terms & CONTRAST_TERMS) ^ (cand_terms & CONTRAST_TERMS):
                relation_type = "contrast"
                relation_score = min(1.0, sim_score + 0.05)

            await self._add_relation(
                db,
                from_article_id=article.id,
                to_article_id=cand.id,
                relation_type=relation_type,
                score=relation_score,
                metadata={"shared_entities": sorted(list(shared_entities))[:10]},
            )

    async def _article_entities(self, db: AsyncSession, article_id: int) -> set[str]:
        rows = await db.execute(select(ArticleEntity.entity).where(ArticleEntity.article_id == article_id))
        return {str(v).lower() for v in rows.scalars().all() if v}

    async def _add_relation(
        self,
        db: AsyncSession,
        *,
        from_article_id: int,
        to_article_id: int,
        relation_type: str,
        score: float,
        metadata: dict | None = None,
    ) -> None:
        if from_article_id == to_article_id:
            return
        res = await db.execute(
            select(ArticleRelation).where(
                and_(
                    ArticleRelation.from_article_id == from_article_id,
                    ArticleRelation.to_article_id == to_article_id,
                    ArticleRelation.relation_type == relation_type,
                )
            )
        )
        rel = res.scalar_one_or_none()
        if rel is None:
            db.add(
                ArticleRelation(
                    from_article_id=from_article_id,
                    to_article_id=to_article_id,
                    relation_type=relation_type,
                    score=score,
                    metadata_json=metadata or {},
                )
            )
        else:
            rel.score = max(rel.score, score)
            if metadata:
                data = dict(rel.metadata_json or {})
                data.update(metadata)
                rel.metadata_json = data

    def _cluster_key(self, article: Article, seed: str) -> str:
        bucket = (article.crawled_at or datetime.utcnow()).strftime("%Y%m%d")
        category = article.category.value if article.category else "general"
        digest = hashlib.sha1(f"{seed}|{category}|{bucket}".encode("utf-8")).hexdigest()[:24]
        return f"evt-{bucket}-{digest}"


news_knowledge_service = NewsKnowledgeService()
