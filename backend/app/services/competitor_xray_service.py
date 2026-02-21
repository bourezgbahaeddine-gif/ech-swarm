"""Competitor X-Ray service.

Detects competitor-exclusive angles and proposes better counter-coverage ideas.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta
from hashlib import sha1
from typing import Any

import feedparser
from rapidfuzz import fuzz
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session
from app.core.logging import get_logger
from app.models import (
    Article,
    CompetitorXrayEvent,
    CompetitorXrayItem,
    CompetitorXrayRun,
    CompetitorXraySource,
)
from app.models.user import User
from app.services.ai_service import ai_service

logger = get_logger("competitor_xray.service")


DEFAULT_COMPETITOR_SOURCES = [
    {"name": "Ennahar", "feed_url": "https://www.ennaharonline.com/feed/", "domain": "ennaharonline.com", "language": "ar", "weight": 1.2},
    {"name": "El Bilad", "feed_url": "https://www.elbilad.net/feed", "domain": "elbilad.net", "language": "ar", "weight": 1.1},
    {"name": "TSA", "feed_url": "https://www.tsa-algerie.com/feed/", "domain": "tsa-algerie.com", "language": "fr", "weight": 1.0},
]


class CompetitorXrayService:
    def __init__(self) -> None:
        self._running_tasks: dict[str, asyncio.Task] = {}

    @staticmethod
    def _json_safe(value: Any) -> Any:
        return json.loads(json.dumps(value, ensure_ascii=False, default=str))

    @staticmethod
    def _run_id(seed: str) -> str:
        suffix = abs(hash((seed, datetime.utcnow().isoformat()))) % 10_000_000
        return f"XRY-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{suffix:07d}"

    @staticmethod
    def _idempotency_key(limit_per_source: int, hours_window: int, actor_id: int | None) -> str:
        raw = f"{limit_per_source}|{hours_window}|{actor_id or 0}"
        return sha1(raw.encode("utf-8")).hexdigest()

    async def seed_default_sources(self, db: AsyncSession) -> dict:
        created = 0
        updated = 0
        for row in DEFAULT_COMPETITOR_SOURCES:
            existing_row = await db.execute(
                select(CompetitorXraySource).where(CompetitorXraySource.feed_url == row["feed_url"])
            )
            existing = existing_row.scalar_one_or_none()
            if existing:
                existing.name = row["name"]
                existing.domain = row["domain"]
                existing.language = row["language"]
                existing.weight = row["weight"]
                existing.enabled = True
                updated += 1
            else:
                db.add(CompetitorXraySource(**row, enabled=True))
                created += 1
        await db.commit()
        return {"created": created, "updated": updated, "total_defaults": len(DEFAULT_COMPETITOR_SOURCES)}

    async def list_sources(self, db: AsyncSession, enabled_only: bool = False) -> list[CompetitorXraySource]:
        query = select(CompetitorXraySource).order_by(CompetitorXraySource.weight.desc(), CompetitorXraySource.name.asc())
        if enabled_only:
            query = query.where(CompetitorXraySource.enabled.is_(True))
        rows = await db.execute(query)
        return rows.scalars().all()

    async def create_source(
        self,
        db: AsyncSession,
        *,
        name: str,
        feed_url: str,
        domain: str,
        language: str,
        weight: float,
        enabled: bool,
    ) -> CompetitorXraySource:
        source = CompetitorXraySource(
            name=name.strip(),
            feed_url=feed_url.strip(),
            domain=domain.strip().lower(),
            language=language.strip().lower(),
            weight=float(weight),
            enabled=enabled,
        )
        db.add(source)
        await db.commit()
        await db.refresh(source)
        return source

    async def update_source(
        self,
        db: AsyncSession,
        source_id: int,
        *,
        name: str | None = None,
        language: str | None = None,
        weight: float | None = None,
        enabled: bool | None = None,
    ) -> CompetitorXraySource | None:
        row = await db.execute(select(CompetitorXraySource).where(CompetitorXraySource.id == source_id))
        source = row.scalar_one_or_none()
        if not source:
            return None
        if name is not None:
            source.name = name.strip()
        if language is not None:
            source.language = language.strip().lower()
        if weight is not None:
            source.weight = float(weight)
        if enabled is not None:
            source.enabled = enabled
        await db.commit()
        await db.refresh(source)
        return source

    async def create_run(
        self,
        db: AsyncSession,
        *,
        limit_per_source: int,
        hours_window: int,
        actor: User | None,
        idempotency_key: str | None = None,
    ) -> CompetitorXrayRun:
        idem = idempotency_key or self._idempotency_key(limit_per_source, hours_window, actor.id if actor else None)
        existing_row = await db.execute(
            select(CompetitorXrayRun)
            .where(CompetitorXrayRun.idempotency_key == idem)
            .where(CompetitorXrayRun.created_at >= datetime.utcnow() - timedelta(minutes=5))
            .order_by(CompetitorXrayRun.created_at.desc())
            .limit(1)
        )
        existing = existing_row.scalar_one_or_none()
        if existing and existing.status in {"queued", "running", "completed"}:
            return existing

        run = CompetitorXrayRun(
            run_id=self._run_id(str(limit_per_source)),
            status="queued",
            idempotency_key=idem,
            created_by_user_id=actor.id if actor else None,
            created_by_username=actor.username if actor else "system",
        )
        db.add(run)
        await db.commit()
        await db.refresh(run)
        return run

    async def start_run_task(self, run_id: str, *, limit_per_source: int, hours_window: int) -> None:
        if run_id in self._running_tasks and not self._running_tasks[run_id].done():
            return
        task = asyncio.create_task(self.execute_run(run_id, limit_per_source=limit_per_source, hours_window=hours_window))
        self._running_tasks[run_id] = task

    async def execute_run(self, run_id: str, *, limit_per_source: int, hours_window: int) -> None:
        async with async_session() as db:
            run_row = await db.execute(select(CompetitorXrayRun).where(CompetitorXrayRun.run_id == run_id))
            run = run_row.scalar_one_or_none()
            if not run:
                return

            run.status = "running"
            run.error = None
            await db.commit()
            await self._emit_event(db, run_id, "runner", "started", {"status": "running"})

            try:
                sources = await self.list_sources(db, enabled_only=True)
                if not sources:
                    seed = await self.seed_default_sources(db)
                    await self._emit_event(db, run_id, "load_sources", "state_update", seed)
                    sources = await self.list_sources(db, enabled_only=True)
                await self._emit_event(db, run_id, "load_sources", "finished", {"sources": len(sources)})

                feed_items = await self._collect_feeds(sources, limit_per_source=limit_per_source)
                await self._emit_event(db, run_id, "collect_competitors", "state_update", {"items": len(feed_items)})

                recent_articles = await self._load_recent_articles(db, hours_window=hours_window)
                await self._emit_event(db, run_id, "load_our_coverage", "state_update", {"articles": len(recent_articles)})

                gaps = []
                for item in feed_items:
                    matched = self._find_covered_match(item["title"], recent_articles)
                    if matched:
                        continue
                    angle = await self._generate_counter_angle(item)
                    priority = self._priority_score(item, source_weight=item["source_weight"])
                    gaps.append({**item, "angle": angle, "priority": priority})

                gaps.sort(key=lambda g: g["priority"], reverse=True)
                top_gaps = gaps[:100]

                for gap in top_gaps:
                    db.add(
                        CompetitorXrayItem(
                            run_id=run_id,
                            source_id=gap["source_id"],
                            competitor_title=gap["title"],
                            competitor_url=gap["url"],
                            competitor_summary=gap.get("summary"),
                            published_at=gap.get("published_at"),
                            priority_score=gap["priority"],
                            status="new",
                            angle_title=gap["angle"].get("angle_title"),
                            angle_rationale=gap["angle"].get("angle_rationale"),
                            angle_questions_json=gap["angle"].get("angle_questions") or [],
                            starter_sources_json=gap["angle"].get("starter_sources") or [],
                        )
                    )

                run.total_scanned = len(feed_items)
                run.total_gaps = len(top_gaps)
                run.status = "completed"
                run.finished_at = datetime.utcnow()
                run.error = None
                await db.commit()

                await self._emit_event(
                    db,
                    run_id,
                    "detect_gaps",
                    "finished",
                    {"scanned": len(feed_items), "gaps": len(top_gaps)},
                )
                await self._emit_event(db, run_id, "runner", "finished", {"status": "completed"})
            except Exception as exc:  # noqa: BLE001
                logger.error("competitor_xray_run_failed", run_id=run_id, error=str(exc))
                await db.rollback()
                failed_row = await db.execute(select(CompetitorXrayRun).where(CompetitorXrayRun.run_id == run_id))
                failed = failed_row.scalar_one_or_none()
                if failed:
                    failed.status = "failed"
                    failed.finished_at = datetime.utcnow()
                    failed.error = str(exc)[:2000]
                    await db.commit()
                await self._emit_event(db, run_id, "runner", "failed", {"status": "failed", "error": str(exc)})

    async def _collect_feeds(self, sources: list[CompetitorXraySource], limit_per_source: int) -> list[dict]:
        def _read_feed(url: str):
            return feedparser.parse(url)

        out: list[dict] = []
        for source in sources:
            parsed = await asyncio.to_thread(_read_feed, source.feed_url)
            entries = parsed.entries[:limit_per_source]
            for entry in entries:
                title = (entry.get("title") or "").strip()
                if not title:
                    continue
                link = (entry.get("link") or "").strip()
                if not link:
                    continue
                summary = (entry.get("summary") or entry.get("description") or "").strip()
                published = self._to_datetime(entry.get("published_parsed"))
                out.append(
                    {
                        "source_id": source.id,
                        "source_name": source.name,
                        "source_domain": source.domain,
                        "source_weight": float(source.weight or 1.0),
                        "title": title,
                        "url": link,
                        "summary": summary[:2000],
                        "published_at": published,
                    }
                )
        return self._dedupe_feed_items(out)

    @staticmethod
    def _to_datetime(struct_time_val) -> datetime | None:
        if not struct_time_val:
            return None
        try:
            return datetime(*struct_time_val[:6])
        except Exception:
            return None

    @staticmethod
    def _dedupe_feed_items(items: list[dict]) -> list[dict]:
        seen_urls = set()
        out = []
        for item in items:
            url = item["url"].split("#")[0].strip().lower()
            if url in seen_urls:
                continue
            seen_urls.add(url)
            out.append(item)
        return out

    async def _load_recent_articles(self, db: AsyncSession, *, hours_window: int) -> list[dict]:
        since = datetime.utcnow() - timedelta(hours=hours_window)
        rows = await db.execute(
            select(Article.id, Article.original_title, Article.title_ar, Article.created_at)
            .where(Article.created_at >= since)
            .order_by(Article.created_at.desc())
            .limit(3000)
        )
        return [
            {
                "id": r.id,
                "title": (r.title_ar or r.original_title or "").strip(),
            }
            for r in rows.all()
            if (r.title_ar or r.original_title)
        ]

    @staticmethod
    def _find_covered_match(competitor_title: str, recent_articles: list[dict]) -> dict | None:
        base = competitor_title.strip().lower()
        if not base:
            return None
        best = None
        best_score = 0.0
        for item in recent_articles:
            score = fuzz.token_set_ratio(base, (item["title"] or "").lower())
            if score > best_score:
                best_score = score
                best = item
        if best and best_score >= 80:
            return best
        return None

    async def _generate_counter_angle(self, item: dict) -> dict:
        prompt = (
            "أنت محرر تخطيط تغطية في غرفة أخبار الشروق.\n"
            "المطلوب: لا تكرر الخبر كما هو. اقترح زاوية تفوق (Counter-angle) مختصرة وعملية.\n"
            "أعد JSON فقط بالمفاتيح:\n"
            '{"angle_title":"", "angle_rationale":"", "angle_questions":[""], "starter_sources":[""]}\n\n'
            f"عنوان المنافس: {item['title']}\n"
            f"ملخص المنافس: {item.get('summary', '')}\n"
            "المخرج يجب أن يكون عملياً ويخدم الصحفي فوراً."
        )
        try:
            data = await ai_service.generate_json(prompt)
            if isinstance(data, dict) and data.get("angle_title"):
                return {
                    "angle_title": str(data.get("angle_title", "")).strip()[:500],
                    "angle_rationale": str(data.get("angle_rationale", "")).strip()[:2000],
                    "angle_questions": self._to_str_list(data.get("angle_questions"), max_items=5),
                    "starter_sources": self._to_str_list(data.get("starter_sources"), max_items=5),
                }
        except Exception:  # noqa: BLE001
            pass
        return self._fallback_angle(item)

    @staticmethod
    def _to_str_list(values: Any, max_items: int = 5) -> list[str]:
        if not isinstance(values, list):
            return []
        out = []
        for v in values:
            s = str(v).strip()
            if s:
                out.append(s[:400])
            if len(out) >= max_items:
                break
        return out

    @staticmethod
    def _fallback_angle(item: dict) -> dict:
        title = item.get("title", "")
        domain = item.get("source_domain", "المنافس")
        return {
            "angle_title": f"ما الأثر المحلي في الجزائر لخبر: {title[:90]}؟",
            "angle_rationale": f"المنافس ({domain}) عرض الحدث بشكل عام. زاوية الشروق المقترحة: ترجمة الحدث إلى أثر مباشر على القارئ الجزائري مع أرقام وسياق رسمي.",
            "angle_questions": [
                "من الجهة الجزائرية المعنية مباشرة بهذا الحدث؟",
                "ما الأثر خلال 24 ساعة على المواطن/السوق المحلي؟",
                "ما الفجوة بين الإعلان والتطبيق الفعلي؟",
            ],
            "starter_sources": [
                "بيانات رسمية جزائرية حديثة",
                "تصريحات خبراء محليين",
                "أرشيف الشروق المرتبط بالموضوع",
            ],
        }

    @staticmethod
    def _priority_score(item: dict, *, source_weight: float) -> float:
        score = 0.0
        title = (item.get("title") or "").strip()
        summary = (item.get("summary") or "").strip()
        now = datetime.utcnow()
        published = item.get("published_at")
        if isinstance(published, datetime):
            age_h = max(0.0, (now - published).total_seconds() / 3600.0)
            freshness = max(0.0, 1.0 - min(age_h / 24.0, 1.0))
            score += freshness * 4.0
        else:
            score += 1.5
        score += min(len(title) / 120.0, 1.0) * 1.2
        score += min(len(summary) / 400.0, 1.0) * 0.8
        if any(k in title for k in ["عاجل", "بيان", "قرار", "الجزائر", "تبون", "الحكومة"]):
            score += 1.4
        score += max(0.1, source_weight) * 1.6
        return round(min(score, 10.0), 2)

    async def get_run_status(self, db: AsyncSession, run_id: str) -> CompetitorXrayRun | None:
        row = await db.execute(select(CompetitorXrayRun).where(CompetitorXrayRun.run_id == run_id))
        return row.scalar_one_or_none()

    async def get_items_latest(
        self,
        db: AsyncSession,
        *,
        limit: int = 30,
        status_filter: str | None = None,
        query: str | None = None,
    ) -> list[CompetitorXrayItem]:
        sql = select(CompetitorXrayItem).order_by(CompetitorXrayItem.priority_score.desc(), CompetitorXrayItem.created_at.desc()).limit(limit)
        if status_filter:
            sql = sql.where(CompetitorXrayItem.status == status_filter)
        rows = await db.execute(sql)
        items = rows.scalars().all()
        if query and query.strip():
            q = query.strip().lower()
            items = [i for i in items if q in (i.competitor_title or "").lower() or q in (i.angle_title or "").lower()]
        return items

    async def mark_item_status(self, db: AsyncSession, item_id: int, status_value: str) -> CompetitorXrayItem | None:
        row = await db.execute(select(CompetitorXrayItem).where(CompetitorXrayItem.id == item_id))
        item = row.scalar_one_or_none()
        if not item:
            return None
        item.status = status_value
        await db.commit()
        await db.refresh(item)
        return item

    async def build_brief(self, db: AsyncSession, item_id: int, tone: str = "newsroom") -> dict | None:
        row = await db.execute(select(CompetitorXrayItem).where(CompetitorXrayItem.id == item_id))
        item = row.scalar_one_or_none()
        if not item:
            return None
        prompt = (
            "أنشئ brief تحريريًا قصيرًا للصحفي من زاوية منافسين.\n"
            "أعد JSON فقط بالمفاتيح:\n"
            '{"title":"", "counter_angle":"", "why_it_wins":"", "newsroom_plan":[""], "starter_sources":[""]}\n\n'
            f"tone: {tone}\n"
            f"competitor_title: {item.competitor_title}\n"
            f"competitor_summary: {item.competitor_summary or ''}\n"
            f"suggested_angle: {item.angle_title or ''}\n"
            f"angle_rationale: {item.angle_rationale or ''}\n"
        )
        try:
            data = await ai_service.generate_json(prompt)
            if isinstance(data, dict) and data.get("title"):
                return {
                    "item_id": item.id,
                    "title": str(data.get("title", "")).strip()[:300],
                    "counter_angle": str(data.get("counter_angle", "")).strip()[:1200],
                    "why_it_wins": str(data.get("why_it_wins", "")).strip()[:1200],
                    "newsroom_plan": self._to_str_list(data.get("newsroom_plan"), max_items=7),
                    "starter_sources": self._to_str_list(data.get("starter_sources"), max_items=7),
                }
        except Exception:
            pass
        return {
            "item_id": item.id,
            "title": item.angle_title or "Brief تغطية منافسين",
            "counter_angle": item.angle_rationale or "",
            "why_it_wins": "تجنّب التكرار وابدأ من أثر محلي أو معلومة موثقة لم يبرزها المنافس.",
            "newsroom_plan": item.angle_questions_json or ["حدد 3 أسئلة تحقيق مباشرة", "استخرج تصريحين رسميين", "أضف سياقًا رقميًا مختصرًا"],
            "starter_sources": item.starter_sources_json or ["أرشيف الشروق", "بيانات رسمية", "خبير مختص"],
        }

    async def get_events_since(self, db: AsyncSession, *, run_id: str, last_id: int = 0, limit: int = 100) -> list[CompetitorXrayEvent]:
        rows = await db.execute(
            select(CompetitorXrayEvent)
            .where(CompetitorXrayEvent.run_id == run_id, CompetitorXrayEvent.id > last_id)
            .order_by(CompetitorXrayEvent.id.asc())
            .limit(limit)
        )
        return rows.scalars().all()

    async def _emit_event(self, db: AsyncSession, run_id: str, node: str, event_type: str, payload: dict) -> None:
        db.add(
            CompetitorXrayEvent(
                run_id=run_id,
                node=node,
                event_type=event_type,
                payload_json=self._json_safe(payload or {}),
            )
        )
        await db.commit()

    async def trigger_scheduled_run(self, *, limit_per_source: int = 6, hours_window: int = 48) -> str | None:
        async with async_session() as db:
            run = await self.create_run(
                db,
                limit_per_source=limit_per_source,
                hours_window=hours_window,
                actor=None,
                idempotency_key=f"scheduled-{datetime.utcnow().strftime('%Y%m%d%H')}",
            )
            await self.start_run_task(run.run_id, limit_per_source=limit_per_source, hours_window=hours_window)
            return run.run_id


competitor_xray_service = CompetitorXrayService()
