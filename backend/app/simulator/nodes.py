"""Audience simulator graph nodes."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, ValidationError
from tenacity import AsyncRetrying, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.core.logging import get_logger
from app.simulator.profiles import SIMULATOR_DIR, load_policy_profile
from app.simulator.state import PersonaReaction, SimulationAdvice, SimulationBreakdown, SimulationResult, SimulationState

logger = get_logger("simulator.nodes")
settings = get_settings()

CLICKBAIT_TERMS = ["خطير", "لن تصدق", "صادم", "فضيحة", "كارثة", "عاجل جدا", "حصريا جدا", "shocking"]
LEGAL_RISK_TERMS = ["اتهم", "تورط", "خيانة", "فساد", "اختلاس", "متهم", "فضيحة"]
VALUES_RISK_TERMS = ["مسيء", "خادش", "غير أخلاقي", "تجاوز القيم"]
POLARIZATION_TERMS = ["انقسام", "صراع", "هجوم", "تخوين", "استفزاز"]


class LlmReaction(BaseModel):
    persona_id: str
    comment: str
    sentiment: str
    risk_signal: float = Field(ge=0, le=1)
    virality_signal: float = Field(ge=0, le=1)


class LlmAdvice(BaseModel):
    summary: str
    improvements: list[str] = Field(default_factory=list)
    alternative_headlines: list[str] = Field(default_factory=list)


class LlmOutput(BaseModel):
    reactions: list[LlmReaction] = Field(default_factory=list)
    breakdown: SimulationBreakdown = Field(default_factory=SimulationBreakdown)
    advice: LlmAdvice = Field(default_factory=LlmAdvice)


class SimulationGraphNodes:
    def __init__(self, emit_event):
        self.emit_event = emit_event
        self._prompt_template = self._load_prompt()

    @staticmethod
    def _load_prompt() -> str:
        path = SIMULATOR_DIR / "prompts" / "simulator_system.txt"
        with path.open("r", encoding="utf-8") as fh:
            return fh.read()

    async def load_policy_profile(self, state: dict[str, Any]) -> dict[str, Any]:
        st = SimulationState.model_validate(state)
        profile = load_policy_profile(st.profile_id)
        await self.emit_event("load_policy_profile", "state_update", {"profile_id": profile["id"], "personas": len(profile["personas"])})
        return {
            "profile": profile,
            "personas": profile["personas"],
            "policy_rules": profile["policy_rules"],
        }

    async def sanitize_input(self, state: dict[str, Any]) -> dict[str, Any]:
        st = SimulationState.model_validate(state)
        headline = self._sanitize_text(st.headline, max_len=280)
        excerpt = self._sanitize_text(st.body_excerpt, max_len=2200)

        context = {
            "headline_len": len(headline),
            "excerpt_len": len(excerpt),
            "has_numbers": bool(re.search(r"\d", f"{headline} {excerpt}")),
            "has_quote": '"' in headline or "“" in headline or "”" in headline,
        }
        await self.emit_event("sanitize_input", "state_update", context)
        return {"sanitized_headline": headline, "sanitized_excerpt": excerpt, "sanitized_context": context}

    async def run_persona_simulation(self, state: dict[str, Any]) -> dict[str, Any]:
        st = SimulationState.model_validate(state)
        llm_output = await self._llm_simulation(st)
        reactions: list[PersonaReaction] = []
        if llm_output:
            for rx in llm_output.reactions:
                persona = self._resolve_persona(st.personas, rx.persona_id)
                reactions.append(
                    PersonaReaction(
                        persona_id=rx.persona_id,
                        persona_label=persona.get("label", rx.persona_id),
                        comment=self._sanitize_text(rx.comment, max_len=320),
                        sentiment=self._normalize_sentiment(rx.sentiment),
                        risk_signal=max(0.0, min(1.0, rx.risk_signal)),
                        virality_signal=max(0.0, min(1.0, rx.virality_signal)),
                    )
                )
            breakdown = llm_output.breakdown
            advice = SimulationAdvice(
                summary=self._sanitize_text(llm_output.advice.summary, max_len=280),
                improvements=[self._sanitize_text(x, max_len=180) for x in llm_output.advice.improvements[:6] if x.strip()],
                alternative_headlines=[self._sanitize_text(x, max_len=120) for x in llm_output.advice.alternative_headlines[:3] if x.strip()],
            )
            llm_failed = False
        else:
            reactions, breakdown, advice = self._fallback_simulation(st)
            llm_failed = True

        await self.emit_event(
            "run_persona_simulation",
            "state_update",
            {"reactions": len(reactions), "llm_failed": llm_failed},
        )
        return {
            "reactions": [r.model_dump() for r in reactions],
            "metrics": {"llm_failed": llm_failed},
            "result": {"breakdown": breakdown.model_dump()},
            "advice": advice.model_dump(),
        }

    async def compute_scores(self, state: dict[str, Any]) -> dict[str, Any]:
        st = SimulationState.model_validate(state)
        breakdown = st.result.breakdown
        risk_weights = (st.profile.get("weights") or {}).get("risk") or {}
        virality_weights = (st.profile.get("weights") or {}).get("virality") or {}

        risk_component = self._weighted_sum(
            breakdown.risk,
            risk_weights,
            default={"clickbait": 0.2, "legal": 0.3, "values": 0.2, "polarization": 0.15, "misinfo": 0.15},
        )
        virality_component = self._weighted_sum(
            breakdown.virality,
            virality_weights,
            default={"emotion": 0.25, "clarity": 0.25, "novelty": 0.2, "meme": 0.15, "simplicity": 0.15},
        )

        risk_score = round(1.0 + 9.0 * risk_component, 2)
        virality_score = round(1.0 + 9.0 * virality_component, 2)
        confidence = self._compute_confidence(st, risk_component, virality_component)
        red_flags = {
            "clickbait": round(breakdown.risk.get("clickbait", 0.0), 3),
            "legal": round(breakdown.risk.get("legal", 0.0), 3),
            "values": round(breakdown.risk.get("values", 0.0), 3),
            "misinfo": round(breakdown.risk.get("misinfo", 0.0), 3),
        }
        policy_level = self._policy_level(risk_score, red_flags)

        result = SimulationResult(
            risk_score=risk_score,
            virality_score=virality_score,
            confidence_score=confidence,
            breakdown=breakdown,
            red_flags=red_flags,
            policy_level=policy_level,
        )
        await self.emit_event(
            "compute_scores",
            "state_update",
            {"risk_score": risk_score, "virality_score": virality_score, "policy_level": policy_level},
        )
        return {"result": result.model_dump()}

    async def generate_editor_advice(self, state: dict[str, Any]) -> dict[str, Any]:
        st = SimulationState.model_validate(state)
        advice = st.advice
        if not advice.improvements:
            advice.improvements = self._build_default_improvements(st)
        if len(advice.alternative_headlines) < 3:
            advice.alternative_headlines = self._build_alternative_headlines(st, existing=advice.alternative_headlines)

        summary = advice.summary or self._build_summary(st)
        advice.summary = self._sanitize_text(summary, max_len=280)

        await self.emit_event("generate_editor_advice", "state_update", {"improvements": len(advice.improvements)})
        return {"advice": advice.model_dump()}

    async def persist_and_return(self, state: dict[str, Any]) -> dict[str, Any]:
        st = SimulationState.model_validate(state)
        report = {
            "run_id": st.run_id,
            "headline": st.sanitized_headline,
            "platform": st.platform,
            "mode": st.mode,
            "risk_score": st.result.risk_score,
            "virality_score": st.result.virality_score,
            "confidence_score": st.result.confidence_score,
            "policy_level": st.result.policy_level,
            "breakdown": st.result.breakdown.model_dump(),
            "red_flags": st.result.red_flags,
            "reactions": [r.model_dump() for r in st.reactions],
            "advice": st.advice.model_dump(),
            "created_at": st.created_at.isoformat(),
        }
        await self.emit_event("persist_and_return", "state_update", {"ready": True})
        return {"report": report}

    async def _llm_simulation(self, st: SimulationState) -> LlmOutput | None:
        try:
            import google.generativeai as gemini

            if not settings.gemini_api_key:
                return None

            gemini.configure(api_key=settings.gemini_api_key)
            model_name = settings.gemini_model_pro if st.mode == "deep" else settings.gemini_model_flash
            model = gemini.GenerativeModel(model_name)
            prompt = (
                self._prompt_template
                .replace("{{headline}}", st.sanitized_headline)
                .replace("{{excerpt}}", st.sanitized_excerpt or "N/A")
                .replace("{{platform}}", st.platform)
                .replace("{{brand_voice}}", json.dumps((st.profile.get("brand_voice") or {}), ensure_ascii=False))
                .replace("{{policy}}", json.dumps((st.policy_rules or {}), ensure_ascii=False))
            )

            response_text = ""
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(3),
                wait=wait_exponential(multiplier=1, min=1, max=8),
                reraise=True,
            ):
                with attempt:
                    response = model.generate_content(
                        prompt,
                        generation_config={
                            "temperature": 0.25,
                            "response_mime_type": "application/json",
                        },
                    )
                    response_text = (response.text or "").strip()

            parsed = self._parse_json_response(response_text)
            return LlmOutput.model_validate(parsed)
        except (ValidationError, json.JSONDecodeError) as exc:
            logger.warning("simulator_llm_parse_failed", error=str(exc))
            return None
        except Exception as exc:  # noqa: BLE001
            logger.warning("simulator_llm_failed", error=str(exc))
            return None

    def _parse_json_response(self, raw_text: str) -> dict[str, Any]:
        text = (raw_text or "").strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            text = text.rsplit("```", 1)[0]
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            text = text[start : end + 1]
        return json.loads(text)

    def _fallback_simulation(self, st: SimulationState) -> tuple[list[PersonaReaction], SimulationBreakdown, SimulationAdvice]:
        headline = st.sanitized_headline
        excerpt = st.sanitized_excerpt
        blob = f"{headline} {excerpt}".lower()

        clickbait = self._term_ratio(blob, CLICKBAIT_TERMS)
        legal = self._term_ratio(blob, LEGAL_RISK_TERMS)
        values = self._term_ratio(blob, VALUES_RISK_TERMS)
        polarization = self._term_ratio(blob, POLARIZATION_TERMS)
        misinfo = 0.65 if ("مصادر" not in blob and "بيان" not in blob and "وفق" not in blob) else 0.25

        breakdown = SimulationBreakdown(
            risk={
                "clickbait": clickbait,
                "legal": legal,
                "values": values,
                "polarization": polarization,
                "misinfo": misinfo,
            },
            virality={
                "emotion": min(1.0, 0.2 + clickbait + polarization * 0.3),
                "clarity": 0.75 if 20 <= len(headline) <= 90 else 0.45,
                "novelty": 0.55,
                "meme": min(1.0, clickbait + 0.2),
                "simplicity": 0.8 if len(headline.split()) <= 14 else 0.55,
            },
        )

        reactions = [
            PersonaReaction(
                persona_id="skeptic",
                persona_label="المواطن الناقد",
                comment="العنوان يحتاج سند أوضح للمصدر حتى يكون مقنعًا.",
                sentiment="Negative" if misinfo > 0.5 else "Neutral",
                risk_signal=min(1.0, max(0.2, legal + misinfo * 0.6)),
                virality_signal=0.35,
            ),
            PersonaReaction(
                persona_id="memer",
                persona_label="الشاب الساخر",
                comment="العنوان قابل للتداول، لكن الأفضل يكون أوضح وما يكونش مبالغ فيه.",
                sentiment="Funny",
                risk_signal=min(1.0, clickbait * 0.6 + 0.2),
                virality_signal=min(1.0, 0.45 + clickbait * 0.5),
            ),
            PersonaReaction(
                persona_id="traditionalist",
                persona_label="الحارس القيمي",
                comment="اللغة تحتاج مزيدًا من الرصانة وتجنب أي تعبير قد يُفهم كتعميم.",
                sentiment="Negative" if values > 0.4 else "Neutral",
                risk_signal=min(1.0, values + polarization * 0.3 + 0.2),
                virality_signal=0.3,
            ),
        ]
        advice = SimulationAdvice(
            summary="تقييم تقريبي (Fallback) بسبب تعذر التحليل العميق بالنموذج.",
            improvements=self._build_default_improvements(st),
            alternative_headlines=self._build_alternative_headlines(st),
        )
        return reactions, breakdown, advice

    @staticmethod
    def _sanitize_text(value: str, max_len: int) -> str:
        text = re.sub(r"<[^>]+>", " ", value or "")
        text = re.sub(r"\s+", " ", text).strip()
        return text[:max_len]

    @staticmethod
    def _resolve_persona(personas: list[dict[str, Any]], persona_id: str) -> dict[str, Any]:
        for persona in personas:
            if persona.get("id") == persona_id:
                return persona
        return {"id": persona_id, "label": persona_id}

    @staticmethod
    def _normalize_sentiment(sentiment: str) -> str:
        allowed = {"negative": "Negative", "neutral": "Neutral", "positive": "Positive", "funny": "Funny"}
        key = (sentiment or "").strip().lower()
        return allowed.get(key, "Neutral")

    @staticmethod
    def _term_ratio(text: str, terms: list[str]) -> float:
        hits = sum(1 for term in terms if term.lower() in text)
        return min(1.0, round(hits / 3.0, 4))

    @staticmethod
    def _weighted_sum(values: dict[str, float], weights: dict[str, float], default: dict[str, float]) -> float:
        target_weights = weights or default
        norm = sum(max(0.0, float(v)) for v in target_weights.values()) or 1.0
        result = 0.0
        for key, weight in target_weights.items():
            result += float(values.get(key, 0.0)) * (max(0.0, float(weight)) / norm)
        return max(0.0, min(1.0, result))

    @staticmethod
    def _policy_level(risk_score: float, red_flags: dict[str, float]) -> str:
        if risk_score >= 8.0 or red_flags.get("legal", 0) >= 0.7:
            return "HIGH_RISK"
        if risk_score >= 5.0:
            return "REVIEW_RECOMMENDED"
        return "LOW_RISK"

    @staticmethod
    def _compute_confidence(st: SimulationState, risk_component: float, virality_component: float) -> float:
        length_factor = 1.0 if len(st.sanitized_headline) >= 20 else 0.6
        excerpt_factor = 1.0 if len(st.sanitized_excerpt) >= 80 else 0.65
        llm_factor = 0.6 if st.metrics.get("llm_failed") else 1.0
        spread = 1.0 - abs(risk_component - virality_component) * 0.5
        score = (length_factor * 0.25 + excerpt_factor * 0.25 + llm_factor * 0.3 + spread * 0.2) * 100
        return round(max(0.0, min(100.0, score)), 2)

    def _build_default_improvements(self, st: SimulationState) -> list[str]:
        breakdown = st.result.breakdown
        fixes: list[str] = []
        if breakdown.risk.get("clickbait", 0.0) > 0.45:
            fixes.append("خفّف العبارات الانفعالية في العنوان واستبدلها بتعبير خبري مباشر.")
        if breakdown.risk.get("legal", 0.0) > 0.45:
            fixes.append("أضف صيغة إسناد واضحة للمعلومة القانونية مثل: وفق بيان رسمي أو مصدر قضائي.")
        if breakdown.risk.get("misinfo", 0.0) > 0.45:
            fixes.append("أدرج دليلًا أو مصدرًا موثقًا داخل المتن لتقليل مخاطر التضليل.")
        if breakdown.virality.get("clarity", 0.0) < 0.5:
            fixes.append("اجعل العنوان أوضح بإبراز الفاعل والحدث والنتيجة في جملة واحدة.")
        if not fixes:
            fixes.append("العنوان جيد عمومًا؛ يمكن تحسينه بإضافة رقم أو معلومة دقيقة لرفع الوضوح.")
        return fixes[:5]

    def _build_alternative_headlines(self, st: SimulationState, existing: list[str] | None = None) -> list[str]:
        base = st.sanitized_headline or st.headline
        options = [x.strip() for x in (existing or []) if x.strip()]
        if len(options) >= 3:
            return options[:3]
        candidates = [
            f"{base} - تفاصيل مؤكدة ومصادر واضحة",
            f"{base} | ما الذي تغيّر وما أثره؟",
            f"{base}: قراءة سريعة للمعطيات الرسمية",
        ]
        for candidate in candidates:
            if candidate not in options:
                options.append(candidate)
            if len(options) >= 3:
                break
        return options[:3]

    def _build_summary(self, st: SimulationState) -> str:
        return (
            f"تقدير محاكي الجمهور: مخاطر {st.result.risk_score}/10، قابلية انتشار {st.result.virality_score}/10. "
            f"التصنيف: {st.result.policy_level}."
        )
