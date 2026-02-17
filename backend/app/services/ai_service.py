"""
Echorouk AI Swarm — AI Service
================================
Unified interface for AI model calls (Gemini Flash/Pro, Groq).
Tiered Processing: Python → Flash → Groq → Pro (cost optimization).
"""

import json
import re
import time
from typing import Optional
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.core.logging import get_logger
from app.schemas import AIAnalysisResult
from app.services.settings_service import settings_service

logger = get_logger("ai_service")
settings = get_settings()


class AIService:
    """Unified AI service with tiered model selection."""

    def __init__(self):
        self._gemini_client = None
        self._groq_client = None

    @staticmethod
    def _resolve_gemini_model(model_name: str, use_pro_default: bool = False) -> str:
        """Map retired Gemini 1.5 model names to supported 2.x defaults."""
        fallback = "gemini-2.5-pro" if use_pro_default else "gemini-2.5-flash"
        if not model_name:
            return fallback
        if model_name.startswith("gemini-1.5"):
            return fallback
        return model_name

    @staticmethod
    def _parse_json_response(raw_text: str) -> dict:
        text = (raw_text or "").strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            text = text.rsplit("```", 1)[0]
        # Some models prepend prose before JSON; keep the first JSON object.
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            text = match.group(0)
        return json.loads(text)

    async def _get_gemini(self):
        """Lazy-load Gemini client."""
        api_key = await settings_service.get_value("GEMINI_API_KEY", settings.gemini_api_key)
        if self._gemini_client is None and api_key:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            self._gemini_client = genai
        return self._gemini_client

    async def _get_groq(self):
        """Lazy-load Groq client."""
        api_key = await settings_service.get_value("GROQ_API_KEY", settings.groq_api_key)
        if self._groq_client is None and api_key:
            from groq import Groq
            self._groq_client = Groq(api_key=api_key)
        return self._groq_client

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30))
    async def analyze_news(self, text: str, source: str = "") -> AIAnalysisResult:
        """
        Analyze a news article using Gemini Flash.
        Single API call for multiple tasks (cost optimization).
        """
        gemini = await self._get_gemini()
        if not gemini:
            logger.warning("gemini_not_configured", msg="Gemini API key not set, returning default")
            return AIAnalysisResult()

        system_prompt = """You are an elite news analyst for an Algerian newsroom.
Input: A raw news text (Arabic, French, or English).
Task: Process the text and output strictly a JSON object.

Steps:
1. Translate: If not in Arabic, summarize/translate the core meaning to Arabic.
2. Classify: Assign a category from: politics, economy, sports, technology, local_algeria, international, culture, society, health, environment.
3. Score: Rate importance (1-10) based on relevance to Algerian public interest.
4. Extract: List key entities (People, Organizations, Places).
5. Detect: Is this a "Breaking News"? (true/false).
6. Keywords: Extract 3-5 SEO keywords in Arabic.

Output Schema (JSON only, no markdown):
{
  "title_ar": "Headline in Arabic (max 15 words)",
  "summary": "2-sentence concise summary in Arabic",
  "category": "category_string",
  "importance_score": number_1_to_10,
  "is_breaking": boolean,
  "entities": ["entity1", "entity2"],
  "keywords": ["keyword1", "keyword2"],
  "sentiment": "positive/neutral/negative"
}"""

        try:
            start = time.time()
            model = gemini.GenerativeModel(self._resolve_gemini_model(settings.gemini_model_flash, use_pro_default=False))
            response = model.generate_content(
                f"{system_prompt}\n\nSource: {source}\nText:\n{text[:8000]}"
            )

            # Parse JSON from response
            result_text = response.text.strip()
            # Remove markdown code blocks if present
            if result_text.startswith("```"):
                result_text = result_text.split("\n", 1)[1]
                result_text = result_text.rsplit("```", 1)[0]

            data = json.loads(result_text)
            elapsed = int((time.time() - start) * 1000)

            logger.info("ai_analysis_complete", model="flash", elapsed_ms=elapsed)
            return AIAnalysisResult(**data)

        except json.JSONDecodeError as e:
            logger.error("ai_json_parse_error", error=str(e))
            return AIAnalysisResult()
        except Exception as e:
            logger.error("ai_analysis_error", error=str(e))
            raise

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30))
    async def rewrite_article(self, content: str, category: str = "", style: str = "echorouk") -> dict:
        """
        Rewrite an article in Echorouk style using Groq (fast) or Gemini Flash.
        """
        prompt = f"""Role: You are a Senior Editor at Echorouk, Algeria's leading newspaper.
Task: Rewrite this news content into a professional Arabic newsroom draft.

Guidelines:
1. Use the Inverted Pyramid style (most important first).
2. Tone: Professional, objective, suitable for digital news.
3. No side comments, no explanation, no markdown, no code fences.
4. Strictly avoid WordPress/Gutenberg artifacts like <!-- wp:... -->.
5. body_html must be clean semantic HTML only.
6. body_html must contain exactly one <h1> at the top, then multiple <p> and optional <h2>.
7. Include at least one internal link to Echorouk (href starts with /news or /).
8. Use at least two Arabic transition words between paragraphs (مثل: لذلك، بالمقابل، إضافة إلى ذلك).
9. Keep body around 220-420 words.
10. Include SEO-friendly title and meta description.

Category: {category}

Output Format (JSON only):
{{
  "headline": "String (Arabic, clear, max 15 words)",
  "body_html": "String (Clean HTML only: one h1 + paragraphs + optional h2 + at least one internal link)",
  "seo_title": "String (30-65 chars)",
  "seo_description": "String (80-170 chars)",
  "tags": ["tag1", "tag2"]
}}

Content to rewrite:
{content[:6000]}"""

        groq = await self._get_groq()
        if groq:
            try:
                response = groq.chat.completions.create(
                    model="llama-3.1-70b-versatile",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.35,
                    max_tokens=4000,
                )
                result_text = response.choices[0].message.content.strip()
                return self._parse_json_response(result_text)
            except Exception as e:
                logger.warning("groq_rewrite_failed", error=str(e), msg="Falling back to Gemini")

        # Fallback to Gemini Flash
        gemini = await self._get_gemini()
        if gemini:
            model = gemini.GenerativeModel(self._resolve_gemini_model(settings.gemini_model_flash, use_pro_default=False))
            response = model.generate_content(prompt)
            result_text = response.text.strip()
            return self._parse_json_response(result_text)

        return {"headline": "", "body_html": content, "seo_title": "", "seo_description": "", "tags": []}

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(min=5, max=60))
    async def deep_analysis(self, content: str, question: str) -> str:
        """
        Deep analysis using Gemini Pro for investigative journalism.
        Only used for high-priority or sensitive content.
        """
        gemini = await self._get_gemini()
        if not gemini:
            return "Gemini Pro not configured."

        system_prompt = """Role: You are a Forensic Auditor and Senior Investigative Journalist.
Objective: Analyze the provided documents to find facts, contradictions, and hidden connections.

Rules:
1. Zero Hallucination: Never invent a fact. If information is missing, state "Not found in documents."
2. Citation: Every claim must reference specific parts of the text.
3. Skepticism: Highlight potential conflicts of interest or vague language.
4. Output: Structured Markdown report in Arabic."""

        try:
            model = gemini.GenerativeModel(self._resolve_gemini_model(settings.gemini_model_pro, use_pro_default=True))
            response = model.generate_content(
                f"{system_prompt}\n\nQuestion: {question}\n\nContent:\n{content[:30000]}"
            )
            return response.text
        except Exception as e:
            logger.error("deep_analysis_error", error=str(e))
            return f"تعذر إجراء التحليل المعمّق: {str(e)}"

    async def generate_radio_script(self, articles: list[dict]) -> str:
        """Generate a radio news script from a list of articles."""
        gemini = await self._get_gemini()
        if not gemini:
            return ""

        articles_text = "\n\n".join([
            f"--- الخبر {i+1} ---\nالعنوان: {a.get('title', '')}\nالملخص: {a.get('summary', '')}"
            for i, a in enumerate(articles[:5])
        ])

        prompt = f"""Role: You are a professional Radio News Scriptwriter.
Task: Rewrite these news articles into a cohesive 2-minute news briefing in Arabic.

Rules:
1. Format: Start with "أهلاً بكم في موجز الشروق", then the news, end with "كان هذا موجز اليوم".
2. Style: Professional Arabic (Fusha), short sentences, active voice.
3. Numbers: Round complex numbers.
4. Transitions: Use smooth transitions ("وفي الشأن الرياضي...", "وإلى الاقتصاد...").

Articles:
{articles_text}"""

        try:
            model = gemini.GenerativeModel(self._resolve_gemini_model(settings.gemini_model_flash, use_pro_default=False))
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            logger.error("radio_script_error", error=str(e))
            return ""

    async def generate_text(self, prompt: str) -> str:
        """Generate text using Gemini Flash (generic helper)."""
        gemini = await self._get_gemini()
        if not gemini:
            return ""
        try:
            model = gemini.GenerativeModel(self._resolve_gemini_model(settings.gemini_model_flash, use_pro_default=False))
            response = model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            logger.error("generate_text_error", error=str(e))
            return ""

    async def generate_json(self, prompt: str) -> dict:
        """Generate structured JSON using Gemini and parse safely."""
        gemini = await self._get_gemini()
        if not gemini:
            return {}
        try:
            import json

            model = gemini.GenerativeModel(self._resolve_gemini_model(settings.gemini_model_flash, use_pro_default=False))
            response = model.generate_content(prompt)
            text = response.text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1]
                text = text.rsplit("```", 1)[0]
            return json.loads(text)
        except Exception as e:
            logger.error("generate_json_error", error=str(e))
            return {}

    async def analyze_image_url(self, image_url: str, prompt: str) -> str:
        """Analyze image via Gemini Vision using an image URL."""
        gemini = await self._get_gemini()
        if not gemini:
            return ""
        try:
            import httpx

            async with httpx.AsyncClient() as client:
                resp = await client.get(image_url, timeout=15)
                resp.raise_for_status()
                image_bytes = resp.content

            model = gemini.GenerativeModel(self._resolve_gemini_model(settings.gemini_model_flash, use_pro_default=False))
            response = model.generate_content([prompt, image_bytes])
            return response.text.strip()
        except Exception as e:
            logger.error("vision_error", error=str(e))
            return ""


# Singleton
ai_service = AIService()
