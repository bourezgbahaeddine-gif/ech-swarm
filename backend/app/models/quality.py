from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, Text, Index
from sqlalchemy.orm import relationship

from app.core.database import Base


class ArticleQualityReport(Base):
    __tablename__ = "article_quality_reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    article_id = Column(Integer, ForeignKey("articles.id"), nullable=False, index=True)
    stage = Column(String(64), nullable=False, index=True)  # TREND_VALIDATED|READABILITY|SEO_TECH|POST_PUBLISH
    passed = Column(Integer, nullable=False, default=0)  # 0/1 for cross-db compatibility
    score = Column(Integer, nullable=True)  # 0..100 when applicable
    blocking_reasons = Column(JSON, nullable=True, default=list)
    actionable_fixes = Column(JSON, nullable=True, default=list)
    report_json = Column(JSON, nullable=True, default=dict)
    created_by = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    article = relationship("Article")

    __table_args__ = (
        Index("ix_quality_article_stage_created", "article_id", "stage", "created_at"),
    )

