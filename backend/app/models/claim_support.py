from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class ArticleClaim(Base):
    __tablename__ = "article_claims"

    id = Column(Integer, primary_key=True, autoincrement=True)
    article_id = Column(Integer, ForeignKey("articles.id"), nullable=False, index=True)
    quality_report_id = Column(Integer, ForeignKey("article_quality_reports.id"), nullable=True, index=True)
    work_id = Column(String(64), nullable=True, index=True)

    claim_external_id = Column(String(64), nullable=False)
    claim_text = Column(Text, nullable=False)
    claim_type = Column(String(32), nullable=True)
    risk_level = Column(String(16), nullable=False, default="low")
    confidence = Column(Float, nullable=True)
    sensitive = Column(Boolean, nullable=False, default=False)
    blocking = Column(Boolean, nullable=False, default=False)
    supported = Column(Boolean, nullable=False, default=False)
    unverifiable = Column(Boolean, nullable=False, default=False)
    unverifiable_reason = Column(Text, nullable=True)
    metadata_json = Column(JSON, nullable=True, default=dict)

    created_by = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    article = relationship("Article")
    quality_report = relationship("ArticleQualityReport")
    supports = relationship("ArticleClaimSupport", cascade="all, delete-orphan", back_populates="claim")

    __table_args__ = (
        UniqueConstraint("article_id", "claim_external_id", name="uq_article_claim_article_external"),
        Index("ix_article_claim_article_risk", "article_id", "risk_level"),
    )


class ArticleClaimSupport(Base):
    __tablename__ = "article_claim_supports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    claim_id = Column(Integer, ForeignKey("article_claims.id", ondelete="CASCADE"), nullable=False, index=True)
    support_kind = Column(String(24), nullable=False, default="url")  # url|doc_intel_ref
    support_ref = Column(String(2048), nullable=False)
    source_host = Column(String(255), nullable=True)
    metadata_json = Column(JSON, nullable=True, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    claim = relationship("ArticleClaim", back_populates="supports")

    __table_args__ = (
        UniqueConstraint("claim_id", "support_ref", name="uq_article_claim_support_unique"),
        Index("ix_article_claim_support_kind", "support_kind"),
    )

