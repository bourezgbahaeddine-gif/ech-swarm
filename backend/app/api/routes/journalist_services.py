"""
Echorouk AI Swarm — Journalist Services
=======================================
Editor/Fact-check/SEO/Multimedia tools for journalists.
"""

import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.ai_service import ai_service

router = APIRouter(prefix="/services", tags=["Journalist Services"])

CONSTITUTION_BASE = (
    "التزم بدستور الشروق التحريري: دقة، توازن، حياد، وضوح، عدم الإثارة، "
    "صياغة مهنية قابلة للنشر، ومنع الحشو أو التعليقات خارج النص المطلوب."
)


def _sanitize_ai_text(text: str) -> str:
    if not text:
        return ""
    cleaned = text.strip()
    cleaned = cleaned.replace("```", "")
    cleaned = re.sub(r"(?im)^\s*(note|notes|explanation|comment)\s*:.*$", "", cleaned)
    cleaned = re.sub(r"(?im)^\s*(ملاحظة|شرح|تعليق)\s*:.*$", "", cleaned)
    cleaned = re.sub(r"(?im)^\s*(حسنًا|حسنا|يمكنني|آمل).*$", "", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned


def _target_language(payload: dict) -> str:
    lang = (payload.get("language") or "ar").lower().strip()
    if lang not in {"ar", "fr", "en"}:
        return "ar"
    return lang


def _lang_name(lang: str) -> str:
    return {"ar": "العربية الفصحى", "fr": "الفرنسية", "en": "الإنجليزية"}[lang]


@router.post("/editor/tonality")
async def editor_tonality(payload: dict):
    text = payload.get("text", "")
    lang = _target_language(payload)
    if not text:
        raise HTTPException(400, "Missing text")
    prompt = (
        f"{CONSTITUTION_BASE}\n"
        f"أعد صياغة النص التالي بلغة {_lang_name(lang)} بنبرة مهنية غير مثيرة.\n"
        "أعط 3 بدائل قصيرة صالحة للنشر فقط، بدون شرح إضافي أو عناوين تقنية."
        f"\n\nText:\n{text}"
    )
    result = await ai_service.generate_text(prompt)
    return {"result": _sanitize_ai_text(result)}


@router.post("/editor/inverted-pyramid")
async def editor_inverted_pyramid(payload: dict):
    text = payload.get("text", "")
    lang = _target_language(payload)
    if not text:
        raise HTTPException(400, "Missing text")
    prompt = (
        f"{CONSTITUTION_BASE}\n"
        f"أعد كتابة الخبر التالي بلغة {_lang_name(lang)} وفق أسلوب الهرم المقلوب.\n"
        "ابدأ بفقرة تمهيدية تجيب من/ماذا/أين/متى/لماذا/كيف، ثم التفاصيل حسب الأهمية.\n"
        "أعد النص النهائي فقط."
        f"\n\nText:\n{text}"
    )
    result = await ai_service.generate_text(prompt)
    return {"result": _sanitize_ai_text(result)}


@router.post("/editor/proofread")
async def editor_proofread(payload: dict):
    text = payload.get("text", "")
    lang = _target_language(payload)
    if not text:
        raise HTTPException(400, "Missing text")
    prompt = (
        f"{CONSTITUTION_BASE}\n"
        f"دقق النص التالي بلغة {_lang_name(lang)}.\n"
        "صحح الأخطاء الإملائية والنحوية وعلامات الترقيم فقط دون تغيير المعنى.\n"
        "أعد النص المصحح فقط."
        f"\n\nText:\n{text}"
    )
    result = await ai_service.generate_text(prompt)
    return {"result": _sanitize_ai_text(result)}


@router.post("/editor/social-summary")
async def editor_social_summary(payload: dict):
    text = payload.get("text", "")
    platform = payload.get("platform", "general")
    lang = _target_language(payload)
    if not text:
        raise HTTPException(400, "Missing text")
    prompt = (
        f"{CONSTITUTION_BASE}\n"
        f"لخّص الخبر التالي بلغة {_lang_name(lang)} لمنصة {platform} دون تهويل أو clickbait.\n"
        "أعط بديلين قصيرين (1-2 جملة) جاهزين للنشر."
        f"\n\nText:\n{text}"
    )
    result = await ai_service.generate_text(prompt)
    return {"result": _sanitize_ai_text(result)}


@router.post("/factcheck/vision")
async def factcheck_vision(payload: dict):
    image_url = payload.get("image_url")
    question = payload.get("question", "تحقق من صحة الصورة وسياقها وما إذا كانت معدلة أو خارج السياق.")
    if not image_url:
        raise HTTPException(400, "Missing image_url")
    result = await ai_service.analyze_image_url(image_url, question)
    return {"result": _sanitize_ai_text(result)}


@router.post("/factcheck/consistency")
async def factcheck_consistency(payload: dict):
    text = payload.get("text", "")
    reference = payload.get("reference", "")
    lang = _target_language(payload)
    if not text:
        raise HTTPException(400, "Missing text")
    prompt = (
        f"{CONSTITUTION_BASE}\n"
        f"تحقق من اتساق النص التالي بلغة {_lang_name(lang)} واكتشف التناقضات أو الأخطاء المحتملة.\n"
        "إذا وُجد مرجع فقارن معه بدقة، ثم اقترح تصحيحات قصيرة قابلة للنشر.\n\n"
        f"Reference:\n{reference}\n\nText:\n{text}"
    )
    result = await ai_service.generate_text(prompt)
    return {"result": _sanitize_ai_text(result)}


@router.post("/factcheck/extract")
async def factcheck_extract(payload: dict):
    text = payload.get("text", "")
    lang = _target_language(payload)
    if not text:
        raise HTTPException(400, "Missing text")
    prompt = (
        f"{CONSTITUTION_BASE}\n"
        f"استخرج أهم النقاط من النص التالي بلغة {_lang_name(lang)}.\n"
        "أعد نقاطًا مرتبة + خلاصة تنفيذية من 3 جمل."
        f"\n\nText:\n{text}"
    )
    result = await ai_service.generate_text(prompt)
    return {"result": _sanitize_ai_text(result)}


@router.post("/seo/keywords")
async def seo_keywords(payload: dict):
    text = payload.get("text", "")
    lang = _target_language(payload)
    if not text:
        raise HTTPException(400, "Missing text")
    prompt = (
        f"{CONSTITUTION_BASE}\n"
        f"ولّد 10 كلمات مفتاحية SEO طويلة الذيل بلغة {_lang_name(lang)} مرتبطة بالخبر التالي.\n"
        "أعدها كسطر واحد مفصول بفواصل."
        f"\n\nText:\n{text}"
    )
    result = await ai_service.generate_text(prompt)
    return {"result": _sanitize_ai_text(result)}


@router.post("/seo/internal-links")
async def seo_internal_links(payload: dict):
    text = payload.get("text", "")
    archive_titles = payload.get("archive_titles", [])
    lang = _target_language(payload)
    if not text:
        raise HTTPException(400, "Missing text")
    prompt = (
        f"{CONSTITUTION_BASE}\n"
        f"اقترح 5 روابط داخلية مناسبة من الأرشيف بلغة {_lang_name(lang)}.\n"
        "أعد عناوين المقالات فقط.\n\n"
        f"News:\n{text}\n\nArchive Titles:\n{archive_titles}"
    )
    result = await ai_service.generate_text(prompt)
    return {"result": _sanitize_ai_text(result)}


@router.post("/seo/metadata")
async def seo_metadata(payload: dict):
    text = payload.get("text", "")
    lang = _target_language(payload)
    if not text:
        raise HTTPException(400, "Missing text")
    prompt = (
        f"{CONSTITUTION_BASE}\n"
        f"اكتب بيانات SEO بلغة {_lang_name(lang)} لهذا الخبر:\n"
        "1) SEO Title (<=60)\n"
        "2) Meta Description (<=160)\n"
        "3) Slug (latin kebab-case).\n"
        "أعد فقط JSON بالمفاتيح: seo_title, meta_description, slug.\n\n"
        f"Text:\n{text}"
    )
    result = await ai_service.generate_text(prompt)
    return {"result": _sanitize_ai_text(result)}


@router.post("/multimedia/video-script")
async def multimedia_video_script(payload: dict):
    text = payload.get("text", "")
    lang = _target_language(payload)
    if not text:
        raise HTTPException(400, "Missing text")
    prompt = (
        f"{CONSTITUTION_BASE}\n"
        f"أنشئ سكريبت فيديو قصير (60-90 ثانية) بلغة {_lang_name(lang)} من هذا الخبر.\n"
        "ضمّن المشاهد المقترحة والنص الظاهر على الشاشة."
        f"\n\nText:\n{text}"
    )
    result = await ai_service.generate_text(prompt)
    return {"result": _sanitize_ai_text(result)}


@router.post("/multimedia/sentiment")
async def multimedia_sentiment(payload: dict):
    text = payload.get("text", "")
    lang = _target_language(payload)
    if not text:
        raise HTTPException(400, "Missing text")
    prompt = (
        f"{CONSTITUTION_BASE}\n"
        f"حلّل الانطباع العام للنص التالي بلغة {_lang_name(lang)}.\n"
        "أعد تقريرًا مختصرًا: الاتجاه العام + أهم الموضوعات."
        f"\n\nText:\n{text}"
    )
    result = await ai_service.generate_text(prompt)
    return {"result": _sanitize_ai_text(result)}


@router.post("/multimedia/translate")
async def multimedia_translate(payload: dict):
    text = payload.get("text", "")
    source_lang = payload.get("source_lang", "auto")
    lang = _target_language(payload)
    if not text:
        raise HTTPException(400, "Missing text")
    prompt = (
        f"{CONSTITUTION_BASE}\n"
        f"ترجم النص التالي من {source_lang} إلى {_lang_name(lang)} مع الحفاظ الكامل على المعنى والسياق الصحفي.\n"
        "أعد النص النهائي فقط دون ملاحظات.\n\n"
        f"Text:\n{text}"
    )
    result = await ai_service.generate_text(prompt)
    return {"result": _sanitize_ai_text(result)}


@router.post("/multimedia/image-prompt")
async def multimedia_image_prompt(payload: dict, db: AsyncSession = Depends(get_db)):
    text = payload.get("text", "")
    style = payload.get("style", "cinematic")
    model = (payload.get("model") or "nanobanana2").strip().lower()
    lang = _target_language(payload)
    article_id = payload.get("article_id")
    created_by = payload.get("created_by")
    if not text:
        raise HTTPException(400, "Missing text")

    prompt = f"""
{CONSTITUTION_BASE}
أنت مهندس برومبتات بصري في غرفة أخبار الشروق.
النموذج المستهدف: {model}
ابنِ 3 برومبتات احترافية لصورة خبرية باللغة {_lang_name(lang)} جاهزة لنموذج NanoBanana 2.

إخراج إلزامي:
- أعِد فقط 3 برومبتات مرقمة (1، 2، 3).
- ممنوع الشرح أو التعليقات الجانبية.
- كل برومبت يجب أن يتضمن:
  [SCENE] الموضوع بصياغة تصويرية دقيقة،
  [STYLE] النمط البصري الصحفي،
  [CAMERA] العدسة/زاوية التصوير،
  [LIGHTING] الإضاءة،
  [COMPOSITION] التكوين،
  [BRAND COLORS] (برتقالي الشروق #F37021 + أسود #0A0A0A + أبيض #FFFFFF)،
  [NEGATIVE] ما يجب منعه (لا شعارات مشوهة، لا نص داخل الصورة، لا تشويه وجوه، لا تهويل، لا دماء صادمة)،
  [ASPECT] نسبة الأبعاد.
- الصورة يجب أن تكون صحفية واقعية بدون تهويل أو تضليل.

نص الخبر:
{text}

النمط المطلوب:
{style}
"""
    result = _sanitize_ai_text(await ai_service.generate_text(prompt))
    if result:
        from app.models.constitution import ImagePrompt
        db.add(ImagePrompt(
            article_id=article_id,
            prompt_text=result,
            style=style,
            created_by=created_by,
        ))
        await db.commit()
    return {"result": result}


@router.post("/multimedia/infographic/analyze")
async def infographic_analyze(payload: dict, db: AsyncSession = Depends(get_db)):
    text = payload.get("text", "")
    lang = _target_language(payload)
    article_id = payload.get("article_id")
    created_by = payload.get("created_by")
    if not text:
        raise HTTPException(400, "Missing text")

    prompt = f"""
{CONSTITUTION_BASE}
حلّل الخبر التالي وأخرج بيانات منظمة لإنفوغرافيا باللغة {_lang_name(lang)}.
أعد JSON فقط بهذا المخطط:
{{
  "title": "عنوان قصير",
  "items": [{{"id": "1", "label": "اسم البند", "value": "القيمة"}}],
  "type": "timeline|ranking|comparison|numbers|map|steps|profile|stats|quote|impact",
  "theme": "dark|light|orange|mono",
  "aspect_ratio": "1:1|4:5|16:9|9:16"
}}

لا تضف أي شرح خارج JSON.

النص:
{text}
"""
    data = await ai_service.generate_json(prompt)
    if data:
        from app.models.constitution import InfographicData
        import json
        db.add(InfographicData(
            article_id=article_id,
            data_json=json.dumps(data, ensure_ascii=False),
            created_by=created_by,
        ))
        await db.commit()
    return {"data": data}


@router.post("/multimedia/infographic/prompt")
async def infographic_prompt(payload: dict, db: AsyncSession = Depends(get_db)):
    data = payload.get("data", {})
    model = (payload.get("model") or "nanobanana2").strip().lower()
    lang = _target_language(payload)
    article_id = payload.get("article_id")
    created_by = payload.get("created_by")
    if not data:
        raise HTTPException(400, "Missing data")
    prompt = f"""
{CONSTITUTION_BASE}
أنت مهندس برومبت بصري في غرفة أخبار الشروق.
النموذج المستهدف: {model}
ابنِ برومبت إنفوغرافيا نهائي باللغة {_lang_name(lang)} اعتمادًا على البيانات التالية:
{data}

متطلبات البرومبت:
- أسلوب بصري صحفي واضح.
- تخطيط منظم سهل القراءة.
- خطوط عربية مناسبة.
- تحديد لوحة الألوان ونسبة الأبعاد.
- وصف العناصر الأساسية بدقة (عناوين، أرقام، ترتيب بصري).
- صياغة متوافقة مع NanoBanana 2 عبر أقسام:
  [LAYOUT], [HIERARCHY], [ICONOGRAPHY], [TEXT-SAFE-ZONE], [NEGATIVE], [ASPECT].
- بدون أي شرح جانبي؛ أعِد البرومبت النهائي فقط.
"""
    result = _sanitize_ai_text(await ai_service.generate_text(prompt))
    if result:
        from app.models.constitution import InfographicData
        import json
        db.add(InfographicData(
            article_id=article_id,
            data_json=json.dumps(data, ensure_ascii=False),
            prompt_text=result,
            created_by=created_by,
        ))
        await db.commit()
    return {"result": result}


@router.post("/multimedia/infographic/render")
async def infographic_render(payload: dict):
    prompt = payload.get("prompt", "")
    if not prompt:
        raise HTTPException(400, "Missing prompt")
    return {"image_url": "", "prompt": prompt}
