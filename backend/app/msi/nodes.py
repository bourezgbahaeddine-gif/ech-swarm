"""MSI graph nodes."""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from datetime import datetime
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import aiohttp
import feedparser
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models import Article, MsiBaseline
from app.msi.profiles import load_profile
from app.msi.state import MSIAnalyzedItem, MSIAggregates, MSICollectedItem, MSIComputed, MSIState
from app.services.ai_service import ai_service

logger = get_logger("msi.nodes")
settings = get_settings()

NEGATIVE_TERMS = {
    "أزمة",
    "احتجاج",
    "تصعيد",
    "تحقيق",
    "اتهام",
    "فساد",
    "توتر",
    "إدانة",
    "غضب",
    "انهيار",
    "crisis",
    "protest",
    "escalation",
    "investigation",
    "accusation",
    "tension",
    "scandal",
}
HIGH_INTENSITY_TERMS = {
    "عاجل",
    "فوراً",
    "خطير",
    "طارئ",
    "إنذار",
    "هجوم",
    "إضراب",
    "انفجار",
    "urgent",
    "alert",
    "attack",
    "strike",
    "explosion",
    "emergency",
}
TOPIC_TOKENS = {
    "سياسة": ["رئاسة", "حكومة", "وزير", "parliament", "gouvernement"],
    "أمن": ["جيش", "دفاع", "شرطة", "security", "armée"],
    "اقتصاد": ["اقتصاد", "بنك", "طاقة", "inflation", "oil", "gas"],
    "مجتمع": ["تعليم", "صحة", "جامعة", "school", "health"],
}


class MsiGraphNodes:
    def __init__(self, db: AsyncSession, emit_event):
        self.db = db
        self.emit_event = emit_event

    async def load_profile(self, state: dict[str, Any]) -> dict[str, Any]:
        st = MSIState.model_validate(state)
        profile = load_profile(st.profile_id)
        baseline_row = await self.db.execute(
            select(MsiBaseline).where(
                MsiBaseline.profile_id == st.profile_id,
                MsiBaseline.entity == st.entity,
            )
        )
        baseline = baseline_row.scalar_one_or_none()
        baseline_payload = {
            "pressure_history": baseline.pressure_history if baseline else [],
            "last_topic_dist": baseline.last_topic_dist if baseline else {},
            "baseline_window_days": baseline.baseline_window_days if baseline else settings.msi_default_baseline_days,
        }
        await self.emit_event("load_profile", "state_update", {"profile": profile.get("id"), "baseline": bool(baseline)})
        return {"profile": profile, "baseline": baseline_payload}

    async def build_queries(self, state: dict[str, Any]) -> dict[str, Any]:
        st = MSIState.model_validate(state)
        aliases = [st.entity]
        profile_aliases = (((st.profile or {}).get("entities") or {}).get("aliases") or [])
        aliases.extend([a for a in profile_aliases if isinstance(a, str)])
        aliases = [a.strip() for a in aliases if a and a.strip()]

        dedup: list[str] = []
        for a in aliases:
            if a not in dedup:
                dedup.append(a)

        queries = [f'"{a}"' for a in dedup[:8]]
        await self.emit_event("build_queries", "state_update", {"queries_count": len(queries)})
        return {"queries": queries}

    async def collect_articles(self, state: dict[str, Any]) -> dict[str, Any]:
        st = MSIState.model_validate(state)
        feeds = (((st.profile or {}).get("default_sources") or {}).get("rss_feeds") or [])
        if not feeds:
            feeds = [settings.published_monitor_feed_url]

        collected: list[MSICollectedItem] = []
        limit = max(10, settings.msi_default_report_limit * 3)

        for feed_url in feeds:
            collected.extend(await self._collect_from_rss(feed_url, st.queries, st.period_start, st.period_end))

        if ((st.profile or {}).get("default_sources") or {}).get("gdelt", True):
            try:
                gdelt_items = await self._collect_from_gdelt(st.queries, st.period_start, st.period_end)
                collected.extend(gdelt_items)
            except Exception as exc:  # noqa: BLE001
                await self.emit_event("collect_articles", "state_update", {"gdelt_error": str(exc)[:180]})

        if len(collected) < 8:
            collected.extend(await self._collect_from_db(st.entity, st.period_start, st.period_end))

        if len(collected) > limit:
            collected = collected[:limit]

        await self.emit_event("collect_articles", "state_update", {"items": len(collected)})
        return {"collected_items": [item.model_dump() for item in collected]}

    async def dedupe_and_normalize(self, state: dict[str, Any]) -> dict[str, Any]:
        st = MSIState.model_validate(state)
        unique: list[MSICollectedItem] = []
        seen: set[str] = set()

        for item in st.collected_items:
            normalized_url = self._normalize_url(item.url)
            normalized_title = self._normalize_text(item.title)
            signature = f"{normalized_url}|{normalized_title}"
            if signature in seen:
                continue
            seen.add(signature)
            item.url = normalized_url or item.url
            item.title = item.title.strip()
            item.domain = self._domain(item.url)
            unique.append(item)

        await self.emit_event(
            "dedupe_and_normalize",
            "state_update",
            {"before": len(st.collected_items), "after": len(unique), "duplicates": max(0, len(st.collected_items) - len(unique))},
        )
        return {"collected_items": [item.model_dump() for item in unique]}

    async def analyze_items(self, state: dict[str, Any]) -> dict[str, Any]:
        st = MSIState.model_validate(state)
        analyzed: list[MSIAnalyzedItem] = []
        max_llm = 8

        for idx, item in enumerate(st.collected_items):
            base_tone, base_intensity, base_topics = self._heuristic_analysis(item)
            llm_failed = False
            llm_topics: list[str] = []
            tone = base_tone
            intensity = base_intensity

            if idx < max_llm:
                llm_result = await self._llm_tone_intensity(item)
                if llm_result:
                    tone = llm_result.get("tone", tone)
                    intensity = llm_result.get("intensity", intensity)
                    llm_topics = llm_result.get("topics", []) or []
                else:
                    llm_failed = True

            topics = [*base_topics, *[t for t in llm_topics if isinstance(t, str)]]
            topics = [t.strip() for t in topics if t and t.strip()]
            topics = list(dict.fromkeys(topics))[:6]

            novelty = self._compute_novelty(item, st.baseline)
            propagation = self._source_weight(item.domain or "", st.profile)

            analyzed.append(
                MSIAnalyzedItem(
                    **item.model_dump(),
                    tone=float(max(-1.0, min(1.0, tone))),
                    intensity=float(max(0.0, min(1.0, intensity))),
                    novelty=float(max(0.0, min(1.0, novelty))),
                    propagation=float(max(0.0, min(1.0, propagation))),
                    topics=topics,
                    is_negative=(tone < -0.15),
                    llm_failed=llm_failed,
                    source_weight=float(max(0.1, min(1.0, propagation))),
                )
            )

        await self.emit_event("analyze_items", "state_update", {"items": len(analyzed)})
        return {"analyzed_items": [item.model_dump() for item in analyzed]}

    async def aggregate_metrics(self, state: dict[str, Any]) -> dict[str, Any]:
        st = MSIState.model_validate(state)
        items = st.analyzed_items
        if not items:
            aggregates = MSIAggregates(total_items=0)
            await self.emit_event("aggregate_metrics", "state_update", aggregates.model_dump())
            return {"aggregates": aggregates.model_dump()}

        weighted_pressures: list[float] = []
        shock_hits = 0
        novelty_values: list[float] = []
        topic_counter: Counter[str] = Counter()

        for item in items:
            pressure = max(0.0, (-item.tone * 0.7) + (item.intensity * 0.3))
            weighted_pressures.append(pressure * item.source_weight)
            novelty_values.append(item.novelty)
            if item.intensity >= 0.8:
                shock_hits += 1
            for topic in item.topics:
                topic_counter[topic] += 1

        total_topics = sum(topic_counter.values()) or 1
        topic_dist = {k: v / total_topics for k, v in topic_counter.items()}
        prev_topic = (st.baseline or {}).get("last_topic_dist") or {}
        volatility = self._js_divergence(topic_dist, prev_topic)

        pressure = sum(weighted_pressures) / max(1, len(weighted_pressures))
        shock = shock_hits / max(1, len(items))
        novelty = sum(novelty_values) / max(1, len(novelty_values))

        top_negative = sorted(
            [
                {
                    "title": item.title,
                    "url": item.url,
                    "source": item.source,
                    "tone": item.tone,
                    "intensity": item.intensity,
                    "score": round((max(0.0, -item.tone) * 0.6 + item.intensity * 0.4) * 100, 2),
                }
                for item in items
                if item.is_negative or item.intensity > 0.65
            ],
            key=lambda x: x["score"],
            reverse=True,
        )[:10]

        aggregates = MSIAggregates(
            total_items=len(items),
            pressure=round(float(max(0.0, min(1.0, pressure))), 4),
            shock=round(float(max(0.0, min(1.0, shock))), 4),
            novelty=round(float(max(0.0, min(1.0, novelty))), 4),
            topic_volatility=round(float(max(0.0, min(1.0, volatility))), 4),
            topic_distribution=topic_dist,
            top_negative_items=top_negative,
        )
        await self.emit_event("aggregate_metrics", "state_update", aggregates.model_dump())
        return {"aggregates": aggregates.model_dump()}

    async def compute_msi(self, state: dict[str, Any]) -> dict[str, Any]:
        st = MSIState.model_validate(state)
        weights = ((st.profile or {}).get("weights") or {})
        alpha = float(weights.get("alpha", 0.4))
        beta = float(weights.get("beta", 0.25))
        gamma = float(weights.get("gamma", 0.2))
        delta = float(weights.get("delta", 0.15))

        instab = (
            alpha * st.aggregates.pressure
            + beta * st.aggregates.shock
            + gamma * st.aggregates.topic_volatility
            + delta * st.aggregates.novelty
        )
        instab = max(0.0, min(1.0, instab))
        msi = round(100.0 * (1.0 - instab), 2)
        level = self._msi_level(msi)

        computed = MSIComputed(
            msi=msi,
            level=level,
            instability=round(instab, 4),
            components={
                "pressure": st.aggregates.pressure,
                "shock": st.aggregates.shock,
                "topic_volatility": st.aggregates.topic_volatility,
                "novelty": st.aggregates.novelty,
                "alpha": alpha,
                "beta": beta,
                "gamma": gamma,
                "delta": delta,
            },
        )

        baseline_window_days = int(((st.profile or {}).get("baseline") or {}).get("window_days", settings.msi_default_baseline_days))
        history = [float(v) for v in ((st.baseline or {}).get("pressure_history") or []) if isinstance(v, (int, float))]
        history.append(st.aggregates.pressure)
        max_history = max(30, baseline_window_days)
        history = history[-max_history:]

        baseline_update = {
            "pressure_history": history,
            "last_topic_dist": st.aggregates.topic_distribution,
            "baseline_window_days": baseline_window_days,
            "last_updated": datetime.utcnow().isoformat(),
        }

        await self.emit_event("compute_msi", "state_update", {"msi": msi, "level": level})
        return {"computed": computed.model_dump(), "baseline": baseline_update}

    async def generate_report(self, state: dict[str, Any]) -> dict[str, Any]:
        st = MSIState.model_validate(state)

        drivers = [
            {"name": "الضغط الإعلامي", "value": round(st.aggregates.pressure * 100, 2)},
            {"name": "الصدمة الخبرية", "value": round(st.aggregates.shock * 100, 2)},
            {"name": "تقلب الموضوعات", "value": round(st.aggregates.topic_volatility * 100, 2)},
            {"name": "الجِدّة", "value": round(st.aggregates.novelty * 100, 2)},
        ]
        drivers = sorted(drivers, key=lambda d: d["value"], reverse=True)

        explanation = (
            f"مؤشر MSI للكيان {st.entity} في نمط {st.mode} بلغ {st.computed.msi}/100 ({st.computed.level}). "
            f"أكثر العوامل تأثيرًا: {drivers[0]['name']} ثم {drivers[1]['name']}"
            if len(drivers) >= 2
            else f"مؤشر MSI للكيان {st.entity} بلغ {st.computed.msi}/100."
        )

        report = {
            "run_id": st.run_id,
            "profile_id": st.profile_id,
            "entity": st.entity,
            "mode": st.mode,
            "period_start": st.period_start.isoformat(),
            "period_end": st.period_end.isoformat(),
            "msi": st.computed.msi,
            "level": st.computed.level,
            "drivers": drivers,
            "top_negative_items": st.aggregates.top_negative_items[:10],
            "topic_shift": {
                "current": st.aggregates.topic_distribution,
                "baseline": (st.baseline or {}).get("last_topic_dist", {}),
            },
            "explanation": explanation,
            "components": st.computed.components,
        }
        await self.emit_event("generate_report", "state_update", {"has_report": True})
        return {"report": report}

    async def _collect_from_rss(self, feed_url: str, queries: list[str], period_start: datetime, period_end: datetime) -> list[MSICollectedItem]:
        if not feed_url:
            return []

        try:
            async with aiohttp.ClientSession(headers={"User-Agent": "EchoroukMSI/1.0"}) as session:
                async with session.get(feed_url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status != 200:
                        return []
                    content = await resp.text()
        except Exception:
            return []

        parsed = feedparser.parse(content)
        out: list[MSICollectedItem] = []
        lowered_queries = [q.replace('"', "").lower() for q in queries]

        for entry in parsed.entries[:120]:
            title = (entry.get("title") or "").strip()
            summary = self._strip_html(entry.get("summary") or entry.get("description") or "")
            hay = f"{title} {summary}".lower()

            if lowered_queries and not any(q in hay for q in lowered_queries):
                continue

            dt = self._parse_dt(entry.get("published") or entry.get("updated"))
            if dt and (dt < period_start or dt > period_end):
                continue

            url = (entry.get("link") or "").strip()
            out.append(
                MSICollectedItem(
                    title=title,
                    url=url,
                    source=self._domain(url),
                    published_at=dt,
                    summary=summary,
                    content=summary,
                    language=self._detect_language(hay),
                    domain=self._domain(url),
                )
            )
        return out

    async def _collect_from_gdelt(self, queries: list[str], period_start: datetime, period_end: datetime) -> list[MSICollectedItem]:
        if not queries:
            return []
        try:
            from gdeltdoc import GdeltDoc  # type: ignore
        except Exception:
            return []

        query = " OR ".join(queries[:5])
        gd = GdeltDoc()
        rows = gd.article_search(query=query, startdatetime=period_start, enddatetime=period_end, maxrecords=50)
        out: list[MSICollectedItem] = []
        for row in rows or []:
            url = str(row.get("url") or "").strip()
            title = str(row.get("title") or "").strip()
            if not url or not title:
                continue
            out.append(
                MSICollectedItem(
                    title=title,
                    url=url,
                    source=self._domain(url),
                    published_at=self._parse_dt(row.get("seendate") or row.get("date")),
                    summary=str(row.get("snippet") or "").strip(),
                    content=str(row.get("snippet") or "").strip(),
                    language=self._detect_language(title),
                    domain=self._domain(url),
                )
            )
        return out

    async def _collect_from_db(self, entity: str, period_start: datetime, period_end: datetime) -> list[MSICollectedItem]:
        pattern = f"%{entity.strip()}%"
        rows = await self.db.execute(
            select(Article)
            .where(
                Article.created_at >= period_start,
                Article.created_at <= period_end,
                Article.original_title.ilike(pattern),
            )
            .order_by(Article.created_at.desc())
            .limit(50)
        )
        out: list[MSICollectedItem] = []
        for article in rows.scalars().all():
            out.append(
                MSICollectedItem(
                    title=(article.title_ar or article.original_title or "").strip(),
                    url=(article.original_url or "").strip(),
                    source=article.source_name,
                    published_at=article.published_at or article.created_at,
                    summary=article.summary,
                    content=article.summary or article.original_content,
                    language=self._detect_language((article.title_ar or article.original_title or "")),
                    domain=self._domain(article.original_url or ""),
                )
            )
        return out

    async def _llm_tone_intensity(self, item: MSICollectedItem) -> dict[str, Any] | None:
        gemini = await ai_service._get_gemini()  # noqa: SLF001
        if not gemini:
            return None

        prompt = (
            "You are a media signal classifier. Return JSON only with keys: tone, intensity, topics. "
            "tone must be between -1 and 1. intensity between 0 and 1. topics array max 5 short labels.\n"
            f"Title: {item.title}\n"
            f"Summary: {(item.summary or '')[:600]}\n"
            "Output strictly JSON, no markdown, no prose."
        )

        try:
            model = gemini.GenerativeModel(settings.gemini_model_flash)
            response = model.generate_content(prompt)
            text = (response.text or "").strip()
            data = json.loads(text)
            if not isinstance(data, dict):
                return None
            return {
                "tone": float(data.get("tone", 0.0)),
                "intensity": float(data.get("intensity", 0.2)),
                "topics": data.get("topics", []) if isinstance(data.get("topics", []), list) else [],
            }
        except Exception:
            return None

    def _heuristic_analysis(self, item: MSICollectedItem) -> tuple[float, float, list[str]]:
        text = f"{item.title} {(item.summary or '')}".lower()
        neg_hits = sum(1 for term in NEGATIVE_TERMS if term in text)
        intense_hits = sum(1 for term in HIGH_INTENSITY_TERMS if term in text)

        tone = -min(1.0, neg_hits * 0.2)
        intensity = min(1.0, 0.2 + intense_hits * 0.15 + neg_hits * 0.08)

        topics: list[str] = []
        for topic, tokens in TOPIC_TOKENS.items():
            if any(tok.lower() in text for tok in tokens):
                topics.append(topic)
        if not topics:
            topics.append("عام")
        return tone, intensity, topics

    def _compute_novelty(self, item: MSICollectedItem, baseline: dict[str, Any]) -> float:
        history = [float(v) for v in (baseline or {}).get("pressure_history", []) if isinstance(v, (int, float))]
        if not history:
            return 0.35
        avg_pressure = sum(history) / max(1, len(history))
        current_hint = 0.2 + (0.15 if any(t in (item.title or "") for t in ["جديد", "لأول مرة", "urgent", "breaking"]) else 0.0)
        return max(0.0, min(1.0, current_hint + abs(avg_pressure - 0.4) * 0.2))

    def _source_weight(self, domain: str, profile: dict[str, Any]) -> float:
        source_tiers = (profile or {}).get("source_tiers") or {}
        source_weights = (profile or {}).get("source_weights") or {}
        d = (domain or "").lower()

        if any(d.endswith(x.lower()) for x in source_tiers.get("tier_1_domains", [])):
            return float(source_weights.get("tier_1", 1.0))
        if any(d.endswith(x.lower()) for x in source_tiers.get("tier_2_domains", [])):
            return float(source_weights.get("tier_2", 0.8))
        return float(source_weights.get("tier_3", 0.6))

    @staticmethod
    def _normalize_text(value: str) -> str:
        return re.sub(r"\s+", " ", (value or "").strip().lower())

    @staticmethod
    def _normalize_url(url: str) -> str:
        raw = (url or "").strip()
        if not raw:
            return ""
        try:
            parsed = urlparse(raw)
            filtered_query = [
                (k, v)
                for k, v in parse_qsl(parsed.query, keep_blank_values=False)
                if not k.lower().startswith("utm_") and k.lower() not in {"fbclid", "gclid", "oc", "hl", "gl", "ceid"}
            ]
            normalized = parsed._replace(
                scheme=(parsed.scheme or "https").lower(),
                netloc=parsed.netloc.lower(),
                query=urlencode(filtered_query, doseq=True),
                fragment="",
            )
            return urlunparse(normalized).rstrip("/")
        except Exception:
            return raw.lower().rstrip("/")

    @staticmethod
    def _domain(url: str) -> str:
        try:
            return (urlparse(url).netloc or "").lower()
        except Exception:
            return ""

    @staticmethod
    def _strip_html(value: str) -> str:
        return re.sub(r"<[^>]+>", " ", value or "").strip()

    @staticmethod
    def _parse_dt(value: Any) -> datetime | None:
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        text = str(value).strip()
        for fmt in (
            "%a, %d %b %Y %H:%M:%S %z",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%Y%m%d%H%M%S",
        ):
            try:
                return datetime.strptime(text, fmt).replace(tzinfo=None)
            except Exception:
                continue
        return None

    @staticmethod
    def _detect_language(text: str) -> str:
        if re.search(r"[\u0600-\u06FF]", text or ""):
            return "ar"
        if re.search(r"\b(le|la|les|des|pour|avec)\b", text or "", flags=re.I):
            return "fr"
        return "en"

    @staticmethod
    def _js_divergence(current: dict[str, float], baseline: dict[str, float]) -> float:
        if not current and not baseline:
            return 0.0

        keys = set(current.keys()) | set(baseline.keys())
        if not keys:
            return 0.0

        def _norm(d: dict[str, float]) -> dict[str, float]:
            total = sum(max(v, 0.0) for v in d.values())
            if total <= 0:
                return {k: 0.0 for k in keys}
            return {k: max(d.get(k, 0.0), 0.0) / total for k in keys}

        p = _norm(current)
        q = _norm(baseline)
        m = {k: (p[k] + q[k]) / 2 for k in keys}

        def _kl(a: dict[str, float], b: dict[str, float]) -> float:
            s = 0.0
            for k in keys:
                if a[k] > 0 and b[k] > 0:
                    s += a[k] * math.log(a[k] / b[k], 2)
            return s

        jsd = (_kl(p, m) + _kl(q, m)) / 2
        return float(max(0.0, min(1.0, jsd)))

    @staticmethod
    def _msi_level(msi: float) -> str:
        if msi >= 75:
            return "GREEN"
        if msi >= 60:
            return "YELLOW"
        if msi >= 40:
            return "ORANGE"
        return "RED"
