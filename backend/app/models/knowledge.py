"""
Knowledge/Archive models for deep editorial retrieval and vector search.
"""

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class ArticleProfile(Base):
    __tablename__ = "article_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    article_id = Column(Integer, ForeignKey("articles.id"), nullable=False, unique=True, index=True)
    archive_code = Column(String(32), nullable=False, unique=True, index=True)
    language = Column(String(8), nullable=False, default="ar")
    normalized_title = Column(String(1024), nullable=True)
    normalized_summary = Column(Text, nullable=True)
    normalized_content = Column(Text, nullable=True)
    canonical_url = Column(String(2048), nullable=True)
    source_name = Column(String(255), nullable=True, index=True)
    category = Column(String(64), nullable=True, index=True)
    editorial_status = Column(String(64), nullable=True, index=True)
    metadata_json = Column(JSON, nullable=True, default=dict)
    search_text = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    article = relationship("Article")

    __table_args__ = (
        Index("ix_article_profiles_category_status", "category", "editorial_status"),
    )


class ArticleTopic(Base):
    __tablename__ = "article_topics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    article_id = Column(Integer, ForeignKey("articles.id"), nullable=False, index=True)
    topic = Column(String(128), nullable=False, index=True)
    confidence = Column(Float, nullable=False, default=0.5)
    source = Column(String(32), nullable=False, default="rule")
    created_at = Column(DateTime, default=datetime.utcnow)

    article = relationship("Article")

    __table_args__ = (
        UniqueConstraint("article_id", "topic", name="uq_article_topics_article_topic"),
    )


class ArticleEntity(Base):
    __tablename__ = "article_entities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    article_id = Column(Integer, ForeignKey("articles.id"), nullable=False, index=True)
    entity = Column(String(256), nullable=False, index=True)
    entity_type = Column(String(32), nullable=False, default="unknown", index=True)
    confidence = Column(Float, nullable=False, default=0.5)
    source = Column(String(32), nullable=False, default="rule")
    created_at = Column(DateTime, default=datetime.utcnow)

    article = relationship("Article")

    __table_args__ = (
        UniqueConstraint("article_id", "entity", "entity_type", name="uq_article_entities_article_entity_type"),
    )


class ArticleChunk(Base):
    __tablename__ = "article_chunks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    article_id = Column(Integer, ForeignKey("articles.id"), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)
    language = Column(String(8), nullable=False, default="ar")
    content = Column(Text, nullable=False)
    content_length = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    article = relationship("Article")

    __table_args__ = (
        UniqueConstraint("article_id", "chunk_index", name="uq_article_chunks_article_chunk"),
        Index("ix_article_chunks_article_idx", "article_id", "chunk_index"),
    )


class ArticleVector(Base):
    __tablename__ = "article_vectors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    article_id = Column(Integer, ForeignKey("articles.id"), nullable=False, index=True)
    chunk_id = Column(Integer, ForeignKey("article_chunks.id"), nullable=True, index=True)
    vector_type = Column(String(32), nullable=False, index=True)  # title|summary|chunk|query
    model = Column(String(64), nullable=False, default="hash-v1")
    dim = Column(Integer, nullable=False, default=256)
    embedding = Column(Vector(256), nullable=False)
    content_hash = Column(String(64), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    article = relationship("Article")
    chunk = relationship("ArticleChunk")

    __table_args__ = (
        UniqueConstraint("article_id", "chunk_id", "vector_type", name="uq_article_vectors_article_chunk_type"),
        Index("ix_article_vectors_article_type", "article_id", "vector_type"),
    )


class StoryCluster(Base):
    __tablename__ = "story_clusters"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cluster_key = Column(String(64), nullable=False, unique=True, index=True)
    label = Column(String(256), nullable=True)
    geography = Column(String(16), nullable=True, default="DZ", index=True)
    category = Column(String(64), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class StoryClusterMember(Base):
    __tablename__ = "story_cluster_members"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cluster_id = Column(Integer, ForeignKey("story_clusters.id"), nullable=False, index=True)
    article_id = Column(Integer, ForeignKey("articles.id"), nullable=False, index=True)
    score = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)

    cluster = relationship("StoryCluster")
    article = relationship("Article")

    __table_args__ = (
        UniqueConstraint("cluster_id", "article_id", name="uq_story_cluster_member"),
    )
