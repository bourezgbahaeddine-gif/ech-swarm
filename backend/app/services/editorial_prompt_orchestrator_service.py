from __future__ import annotations

import re
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Article, ArticleQualityReport, EditorialDraft
from app.services.smart_editor_service import smart_editor_service


TASK_KEYS = {
    "first_draft",
    "verify_claims",
    "proofread",
    "quality_review",
    "headline_pack",
    "social_pack",
    "publish_gate",
}


async def _latest_stage_report(
    db: AsyncSession,
    *,
    article_id: int,
    stage: str,
) -> ArticleQualityReport | None:
    row = await db.execute(
        select(ArticleQualityReport)
        .where(
            ArticleQualityReport.article_id == article_id,
            ArticleQualityReport.stage == stage,
        )
        .order_by(desc(ArticleQualityReport.created_at), desc(ArticleQualityReport.id))
        .limit(1)
    )
    return row.scalar_one_or_none()


def _summarize_source_facts(source_text: str, limit: int = 4) -> list[str]:
    sentences = [
        re.sub(r"\s+", " ", part).strip(" -\u061f.,:;\n\t")
        for part in re.split(r"[.!?\n]+", source_text or "")
    ]
    facts: list[str] = []
    for sentence in sentences:
        if not sentence or len(sentence) < 18:
            continue
        facts.append(sentence)
        if len(facts) >= limit:
            break
    return facts


def _infer_angle(article: Article) -> str:
    urgency = str(getattr(article.urgency, "value", article.urgency or "")).lower()
    if getattr(article, "is_breaking", False) or urgency == "breaking":
        return "خبر عاجل"
    category = str(getattr(article.category, "value", article.category or "")).lower()
    if category in {"economy", "technology", "health"}:
        return "تفسير"
    return "متابعة"


def _infer_audience(article: Article) -> str:
    category = str(getattr(article.category, "value", article.category or "")).lower()
    if category in {"local_algeria", "society", "environment"}:
        return "محلي"
    if category in {"politics", "international"}:
        return "سياسي"
    if category == "economy":
        return "اقتصادي"
    return "عام"


def _infer_style(article: Article) -> str:
    urgency = str(getattr(article.urgency, "value", article.urgency or "")).lower()
    return "مباشر" if urgency == "breaking" or getattr(article, "is_breaking", False) else "مهني"


def _infer_rewrite_mode(article: Article, word_count: int) -> str:
    urgency = str(getattr(article.urgency, "value", article.urgency or "")).lower()
    if getattr(article, "is_breaking", False) or urgency == "breaking":
        return "breaking"
    if word_count >= 450:
        return "analysis"
    if word_count <= 120:
        return "simple"
    return "formal"


def _build_prompt_preview(
    *,
    task_key: str,
    article: Article,
    latest: EditorialDraft,
    source_text: str,
    body_text: str,
    title: str,
) -> tuple[str, list[dict[str, str]]]:
    facts = _summarize_source_facts(source_text)
    facts_block = "\n".join(f"- {fact}" for fact in facts) if facts else "- لا توجد وقائع كافية بعد."
    angle = _infer_angle(article)
    audience = _infer_audience(article)
    style = _infer_style(article)
    word_count = len(re.findall(r"\S+", body_text or ""))
    length_hint = "قصير 120-180 كلمة" if word_count < 180 else "متوسط 250-400"

    fields = [
        {"label": "الموضوع", "value": title or (article.title_ar or article.original_title or "بدون عنوان")},
        {"label": "زاوية التناول", "value": angle},
        {"label": "الجمهور", "value": audience},
        {"label": "الأسلوب", "value": style},
    ]

    if task_key == "first_draft":
        fields.append({"label": "الوقائع المؤكدة", "value": f"{len(facts)} نقاط"})
        return (
            (
                "أنت مساعد تحريري داخل غرفة أخبار.\n"
                "أريد مسودة أولية قابلة للتحرير لمادة صحفية اعتمادًا على المعطيات التالية فقط.\n\n"
                f"الموضوع:\n{title or article.original_title or 'بدون عنوان'}\n\n"
                f"الوقائع المؤكدة:\n{facts_block}\n\n"
                f"زاوية التناول:\n{angle}\n\n"
                f"الجمهور المستهدف:\n{audience}\n\n"
                f"الأسلوب المطلوب:\n{style}\n\n"
                f"الطول المطلوب:\n{length_hint}\n\n"
                "قيود مهمة:\n"
                "- لا تضف أي معلومة غير موجودة في المعطيات\n"
                "- لا تخمّن\n"
                "- لا تستخدم لغة دعائية\n"
                "- ابدأ بأقوى معلومة خبرية\n"
            ),
            fields,
        )
    if task_key == "verify_claims":
        return (
            (
                "استخرج من النص جميع الادعاءات التي تحتاج تحققًا.\n"
                "صنفها إلى: أرقام، أسماء، تواريخ، اقتباسات، علاقات سببية، أوصاف قد تكون مبالغًا فيها.\n\n"
                f"النص:\n{body_text[:2500] or source_text[:2500]}"
            ),
            fields + [{"label": "حجم النص", "value": f"{word_count} كلمة تقريبًا"}],
        )
    if task_key == "proofread":
        return (
            (
                "حسّن النص التالي لغويًا وأسلوبيا دون تغيير أي حقيقة.\n"
                "المطلوب:\n- تصحيح اللغة\n- تحسين السلاسة\n- إزالة التكرار\n"
                "- الحفاظ على المعنى والوقائع كما هي\n- عدم إضافة معلومات جديدة\n\n"
                f"النص:\n{body_text[:2500]}"
            ),
            fields + [{"label": "النسخة الحالية", "value": f"v{latest.version}"}],
        )
    if task_key == "quality_review":
        return (
            (
                "قيّم هذه المادة قبل الإرسال للاعتماد التحريري.\n"
                "افحص فقط: الاتساق، الوضوح، الادعاءات التي تحتاج تحققًا، الثغرات المعلوماتية، الجاهزية العامة للنشر.\n\n"
                f"النص:\n{body_text[:2500]}"
            ),
            fields + [{"label": "الهدف", "value": "جاهزية الاعتماد"}],
        )
    if task_key == "headline_pack":
        return (
            (
                "اقترح 10 عناوين لهذه المادة.\n"
                "القيود:\n- لا تبالغ\n- لا تغير الوقائع\n- اجعل العنوان واضحًا من القراءة الأولى\n"
                "- قدم 3 عناوين قصيرة و3 متوسطة و4 أقوى من ناحية الجذب دون فقدان المهنية.\n\n"
                f"ملخص المادة:\n{body_text[:1800] or source_text[:1800]}"
            ),
            fields + [{"label": "العنوان الحالي", "value": title or "غير محدد"}],
        )
    if task_key == "social_pack":
        return (
            (
                "حوّل هذه المادة إلى منشور رقمي مناسب للمنصات الاجتماعية.\n"
                "الهدف: إخبار + جذب اهتمام دون clickbait مضلل.\n"
                "أعطني نسخة أساسية ونسخة أقصر ونسخة أقوى من ناحية الجذب.\n\n"
                f"المادة:\n{body_text[:1800]}"
            ),
            fields + [{"label": "القناة المقصودة", "value": "Compose / Social"}],
        )
    return (
        (
            "قيّم هذه المادة قبل الإرسال للاعتماد التحريري.\n"
            "حدد نقاط القوة والضعف والمخاطر التحريرية وما الذي يجب إصلاحه قبل الاعتماد.\n\n"
            f"النص:\n{body_text[:2500]}"
        ),
        fields + [{"label": "الهدف", "value": "بوابة النشر"}],
    )


def _task_metadata(task_key: str) -> dict[str, Any]:
    mapping: dict[str, dict[str, Any]] = {
        "first_draft": {
            "task_label": "ابدأ المسودة الأولى تلقائيًا",
            "template_key": "scribe_first_draft",
            "template_title": "قالب Scribe للمسودة الأولى",
            "playbook_href": "/prompt-playbook#scribe",
            "operation": "rewrite",
            "auto_apply_default": True,
            "run_mode": "background_task",
        },
        "verify_claims": {
            "task_label": "تحقق من الادعاءات أولًا",
            "template_key": "quality_claims_check",
            "template_title": "قالب التحقق من الادعاءات",
            "playbook_href": "/prompt-playbook#quality-gates",
            "operation": "claims",
            "auto_apply_default": False,
            "run_mode": "background_task",
        },
        "proofread": {
            "task_label": "شغّل التدقيق اللغوي",
            "template_key": "smart_editor_proofread",
            "template_title": "قالب التدقيق اللغوي والأسلوبي",
            "playbook_href": "/prompt-playbook#smart-editor-improve",
            "operation": "proofread",
            "auto_apply_default": False,
            "run_mode": "background_task",
        },
        "quality_review": {
            "task_label": "افحص جودة المادة الآن",
            "template_key": "quality_editorial_review",
            "template_title": "قالب فحص الجاهزية والجودة",
            "playbook_href": "/prompt-playbook#quality-gates",
            "operation": "quality",
            "auto_apply_default": False,
            "run_mode": "background_task",
        },
        "headline_pack": {
            "task_label": "ولّد عناوين مناسبة للحالة الحالية",
            "template_key": "smart_editor_headlines",
            "template_title": "قالب اقتراح العناوين",
            "playbook_href": "/prompt-playbook#smart-editor-headlines",
            "operation": "headlines",
            "auto_apply_default": False,
            "run_mode": "background_task",
        },
        "social_pack": {
            "task_label": "حضّر النسخ الرقمية تلقائيًا",
            "template_key": "digital_compose_post",
            "template_title": "قالب Compose للديجيتال",
            "playbook_href": "/prompt-playbook#digital-compose",
            "operation": "social",
            "auto_apply_default": False,
            "run_mode": "background_task",
        },
        "publish_gate": {
            "task_label": "افحص الجاهزية النهائية",
            "template_key": "quality_publish_gate",
            "template_title": "قالب بوابة النشر",
            "playbook_href": "/prompt-playbook#quality-gates",
            "operation": "publish_gate",
            "auto_apply_default": False,
            "run_mode": "direct_check",
        },
    }
    return mapping[task_key]


async def suggest_workspace_task(
    db: AsyncSession,
    *,
    latest: EditorialDraft,
    article: Article,
    forced_task_key: str | None = None,
) -> dict[str, Any]:
    task_key = (forced_task_key or "").strip()
    title = (latest.title or article.title_ar or article.original_title or "").strip()
    body_text = smart_editor_service.html_to_text(latest.body or "")
    source_text = "\n".join([article.original_title or "", article.summary or "", article.original_content or ""]).strip()
    word_count = len(re.findall(r"\S+", body_text or ""))

    fact_report = await _latest_stage_report(db, article_id=article.id, stage="FACT_CHECK")
    quality_report = await _latest_stage_report(db, article_id=article.id, stage="QUALITY_SCORE")
    social_report = await _latest_stage_report(db, article_id=article.id, stage="SOCIAL_VARIANTS")

    title_weak = len(title) < 18 or title.startswith("مسودة") or title.startswith("عنوان")
    proofread_applied = "proofread" in str(latest.note or "").lower()

    rationale: list[str] = []
    if not task_key:
        if word_count < 140:
            task_key = "first_draft"
            rationale = [
                "المتن الحالي قصير ولا يزال بحاجة إلى نقطة انطلاق أوضح.",
                "أفضل خطوة الآن هي ملء قالب المسودة الأولى تلقائيًا بدل فتح أدوات متعددة.",
            ]
        elif not fact_report or not bool(fact_report.passed):
            task_key = "verify_claims"
            rationale = [
                "لا يوجد تحقق مكتمل من الادعاءات أو توجد ادعاءات ما زالت تعيق الجاهزية.",
                "من الأفضل معالجة الإسناد قبل الدخول في تحسينات شكلية إضافية.",
            ]
        elif not proofread_applied:
            task_key = "proofread"
            rationale = [
                "النسخة أصبحت كافية تحريريًا لكن لم تُمرَّر بعد على التدقيق اللغوي.",
                "تثبيت اللغة أولًا سيجعل العناوين والجودة أكثر دقة بعد ذلك.",
            ]
        elif not quality_report or not bool(quality_report.passed) or float(quality_report.score or 0) < 75:
            task_key = "quality_review"
            rationale = [
                "درجة الجودة غير موجودة أو ما زالت أقل من الحد المريح للاعتماد.",
                "فحص الجودة الآن سيعطيك أقصر طريق لمعرفة ما الذي يجب إصلاحه قبل الإرسال.",
            ]
        elif title_weak:
            task_key = "headline_pack"
            rationale = [
                "العنوان الحالي ما زال عامًا أو ضعيفًا مقارنة بنضج المتن.",
                "توليد حزمة عناوين الآن أكثر قيمة من إعادة كتابة النص كاملًا.",
            ]
        elif not social_report:
            task_key = "social_pack"
            rationale = [
                "المادة تبدو مستقرة تحريريًا لكن النسخ الرقمية غير جاهزة بعد.",
                "إعداد نسخ Compose الآن يختصر وقت التسليم إلى الديجيتال.",
            ]
        else:
            task_key = "publish_gate"
            rationale = [
                "أغلب مراحل التحرير الأساسية موجودة بالفعل.",
                "أفضل خطوة الآن هي التأكد من الجاهزية النهائية قبل الإرسال للاعتماد.",
            ]
    else:
        if task_key not in TASK_KEYS:
            raise ValueError(f"unknown_task_key:{task_key}")
        rationale = ["تم اختيار هذه المهمة يدويًا بدل الاقتراح التلقائي الحالي."]

    metadata = _task_metadata(task_key)
    prompt_preview, auto_filled_fields = _build_prompt_preview(
        task_key=task_key,
        article=article,
        latest=latest,
        source_text=source_text,
        body_text=body_text,
        title=title,
    )

    operation_payload: dict[str, Any] = {}
    if task_key == "first_draft":
        operation_payload = {
            "mode": _infer_rewrite_mode(article, word_count),
            "instruction": "ابدأ بمسودة أولى نظيفة وقابلة للتحرير دون إضافة حقائق غير موجودة.",
        }
    elif task_key == "headline_pack":
        operation_payload = {"count": 8}

    return {
        "work_id": latest.work_id,
        "article_id": article.id,
        "task_key": task_key,
        "task_label": metadata["task_label"],
        "template_key": metadata["template_key"],
        "template_title": metadata["template_title"],
        "playbook_href": metadata["playbook_href"],
        "reason": rationale[0] if rationale else "",
        "rationale": rationale,
        "auto_filled_fields": auto_filled_fields,
        "prompt_preview": prompt_preview,
        "operation": metadata["operation"],
        "operation_payload": operation_payload,
        "auto_apply_default": metadata["auto_apply_default"],
        "run_mode": metadata["run_mode"],
        "word_count": word_count,
    }
