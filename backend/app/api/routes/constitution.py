"""
Echorouk Editorial OS - Constitution Routes.
Expose latest constitution and user acknowledgements.
"""

from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.auth import get_current_user
from app.core.database import get_db
from app.models.constitution import ConstitutionAck, ConstitutionMeta
from app.models.user import User
from app.schemas import ConstitutionAckRequest, ConstitutionAckResponse, ConstitutionMetaResponse

router = APIRouter(prefix="/constitution", tags=["Constitution"])

CONSTITUTION_TIPS = [
    "ابدأ المقدمة بإجابة مباشرة: ماذا حدث؟ أين؟ متى؟ ومن الجهة المعنية؟",
    "لا تعتمد أي معلومة بلا مصدر واضح أو تصريح منسوب.",
    "استخدم جمل قصيرة وواضحة وتجنب اللغة الإنشائية.",
    "قبل الاعتماد النهائي شغّل: التحقق من الادعاءات + الجودة + التدقيق التقني.",
    "أي تعديل جوهري يجب أن يمر بمراجعة بشرية قبل الاعتماد.",
]

CONSTITUTION_GUIDE = {
    "title": "الدستور التحريري للشروق",
    "purpose": "مرجع تشغيل يومي يضبط جودة الخبر قبل الاعتماد النهائي ويحافظ على الثقة التحريرية.",
    "principles": [
        "الدقة قبل السرعة: لا معلومة بلا مصدر واضح.",
        "الحياد: لا لغة رأي داخل المادة الخبرية.",
        "الوضوح: جمل قصيرة ومباشرة وهيكل هرم مقلوب.",
        "لا للنشر التلقائي: النشر النهائي يدوي بعد الاعتماد.",
    ],
    "must_do": [
        "تشغيل التحقق من الادعاءات قبل الإرسال.",
        "تشغيل جودة النص + SEO + التدقيق التقني.",
        "وضع [VERIFY] لأي عنصر غير مؤكد أو حذفه.",
        "حفظ كل تعديل كنسخة واضحة داخل المحرر الذكي.",
    ],
    "must_not_do": [
        "اختراع أرقام أو أسماء أو تواريخ غير موجودة في المصادر.",
        "إضافة تعليقات جانبية أو ملاحظات غير صحفية داخل المتن.",
        "تمرير نسخة نهائية مع claims غير مؤكدة.",
        "استخدام عناوين مضللة أو clickbait.",
    ],
    "gate_before_final": [
        "بوابة الادعاءات: لا claims غير مؤكدة.",
        "بوابة الجودة: نتيجة مقبولة.",
        "بوابة الدستور: إقرار النسخة الحالية.",
        "مراجعة بشرية: قرار رئيس التحرير.",
    ],
}


@router.get("/latest", response_model=ConstitutionMetaResponse)
async def get_latest_constitution(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ConstitutionMeta)
        .where(ConstitutionMeta.is_active == True)
        .order_by(desc(ConstitutionMeta.updated_at))
        .limit(1)
    )
    latest = result.scalar_one_or_none()
    if not latest:
        return ConstitutionMetaResponse(
            version="v1.0",
            file_url="/constitution/guide",
            updated_at=None,
        )
    return ConstitutionMetaResponse(
        version=latest.version,
        file_url=latest.file_url,
        updated_at=latest.updated_at,
    )


@router.get("/ack", response_model=ConstitutionAckResponse)
async def get_ack_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(ConstitutionMeta)
        .where(ConstitutionMeta.is_active == True)
        .order_by(desc(ConstitutionMeta.updated_at))
        .limit(1)
    )
    latest = result.scalar_one_or_none()
    if not latest:
        return ConstitutionAckResponse(acknowledged=False, version=None)

    ack = await db.execute(
        select(ConstitutionAck)
        .where(
            ConstitutionAck.user_id == current_user.id,
            ConstitutionAck.version == latest.version,
        )
    )
    exists = ack.scalar_one_or_none() is not None
    return ConstitutionAckResponse(acknowledged=exists, version=latest.version)


@router.post("/ack", response_model=ConstitutionAckResponse)
async def acknowledge(
    data: ConstitutionAckRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(ConstitutionMeta).where(ConstitutionMeta.version == data.version))
    meta = result.scalar_one_or_none()
    if not meta:
        # Auto-seed minimal active constitution metadata to avoid blocking the UI gate.
        meta = ConstitutionMeta(
            version=data.version,
            file_url="/constitution/guide",
            is_active=True,
            updated_at=datetime.utcnow(),
        )
        db.add(meta)
        await db.flush()

    existing = await db.execute(
        select(ConstitutionAck)
        .where(
            ConstitutionAck.user_id == current_user.id,
            ConstitutionAck.version == data.version,
        )
    )
    ack = existing.scalar_one_or_none()
    if not ack:
        db.add(
            ConstitutionAck(
                user_id=current_user.id,
                version=data.version,
                acknowledged_at=datetime.utcnow(),
            )
        )
        await db.commit()

    return ConstitutionAckResponse(acknowledged=True, version=data.version)


@router.get("/tips")
async def get_constitution_tips():
    return {"tips": CONSTITUTION_TIPS}


@router.get("/guide")
async def get_constitution_guide():
    return {**CONSTITUTION_GUIDE, "tips": CONSTITUTION_TIPS}
