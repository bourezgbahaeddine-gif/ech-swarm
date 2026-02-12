"""
Echorouk AI Swarm — Constitution Routes
=======================================
Expose latest constitution and user acknowledgements.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.constitution import ConstitutionMeta, ConstitutionAck
from app.models.user import User
from app.api.routes.auth import get_current_user
from app.schemas import ConstitutionMetaResponse, ConstitutionAckResponse, ConstitutionAckRequest

router = APIRouter(prefix="/constitution", tags=["Constitution"])


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
        raise HTTPException(status_code=404, detail="Constitution not found")
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
    # latest version
    result = await db.execute(
        select(ConstitutionMeta)
        .where(ConstitutionMeta.is_active == True)
        .order_by(desc(ConstitutionMeta.updated_at))
        .limit(1)
    )
    latest = result.scalar_one_or_none()
    if not latest:
        raise HTTPException(status_code=404, detail="Constitution not found")

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
    # Ensure version exists
    result = await db.execute(
        select(ConstitutionMeta).where(ConstitutionMeta.version == data.version)
    )
    meta = result.scalar_one_or_none()
    if not meta:
        raise HTTPException(status_code=404, detail="Constitution version not found")

    # Upsert acknowledgement
    existing = await db.execute(
        select(ConstitutionAck)
        .where(
            ConstitutionAck.user_id == current_user.id,
            ConstitutionAck.version == data.version,
        )
    )
    ack = existing.scalar_one_or_none()
    if not ack:
        db.add(ConstitutionAck(
            user_id=current_user.id,
            version=data.version,
            acknowledged_at=datetime.utcnow(),
        ))
        await db.commit()

    return ConstitutionAckResponse(acknowledged=True, version=data.version)
