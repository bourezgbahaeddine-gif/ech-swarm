from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import relationship

from app.core.database import Base


class DocumentIntelDocument(Base):
    __tablename__ = "document_intel_documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    filename = Column(String(255), nullable=False, index=True)
    title = Column(String(512), nullable=True)
    parser_used = Column(String(64), nullable=False)
    language_hint = Column(String(16), nullable=False, default="ar")
    detected_language = Column(String(16), nullable=False, default="unknown")
    document_type = Column(String(64), nullable=False, default="report", index=True)
    document_summary = Column(Text, nullable=False, default="")
    stats = Column(JSON, nullable=False, default=dict)
    headings = Column(JSON, nullable=False, default=list)
    news_candidates = Column(JSON, nullable=False, default=list)
    entities = Column(JSON, nullable=False, default=list)
    story_angles = Column(JSON, nullable=False, default=list)
    data_points = Column(JSON, nullable=False, default=list)
    warnings = Column(JSON, nullable=False, default=list)
    preview_text = Column(Text, nullable=False, default="")
    source_job_id = Column(String(64), nullable=True, index=True)

    uploaded_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    uploaded_by_username = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False, index=True)

    claims = relationship("DocumentIntelClaim", back_populates="document", cascade="all, delete-orphan", lazy="selectin")
    actions = relationship("DocumentIntelAction", back_populates="document", cascade="all, delete-orphan", lazy="selectin")

    __table_args__ = (
        Index("ix_document_intel_type_created", "document_type", "created_at"),
    )


class DocumentIntelClaim(Base):
    __tablename__ = "document_intel_claims"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey("document_intel_documents.id", ondelete="CASCADE"), nullable=False, index=True)
    rank = Column(Integer, nullable=False, default=1)
    text = Column(Text, nullable=False)
    claim_type = Column(String(32), nullable=False, default="factual", index=True)
    confidence = Column(Float, nullable=False, default=0.5)
    risk_level = Column(String(16), nullable=False, default="medium", index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    document = relationship("DocumentIntelDocument", back_populates="claims")

    __table_args__ = (
        Index("ix_document_intel_claim_doc_rank", "document_id", "rank"),
    )


class DocumentIntelAction(Base):
    __tablename__ = "document_intel_actions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey("document_intel_documents.id", ondelete="CASCADE"), nullable=False, index=True)
    action_type = Column(String(48), nullable=False, index=True)
    target_type = Column(String(48), nullable=True)
    target_id = Column(String(64), nullable=True)
    note = Column(Text, nullable=True)
    payload_json = Column(JSON, nullable=False, default=dict)
    actor_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    actor_username = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    document = relationship("DocumentIntelDocument", back_populates="actions")

    __table_args__ = (
        Index("ix_document_intel_action_doc_created", "document_id", "created_at"),
    )
