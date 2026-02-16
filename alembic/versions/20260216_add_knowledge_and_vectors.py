"""add knowledge archive and vector search tables

Revision ID: 20260216_knowledge_vectors
Revises: 20260216_scribe_v2
Create Date: 2026-02-16 16:20:00
"""

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision = "20260216_knowledge_vectors"
down_revision = "20260216_scribe_v2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "article_profiles",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("article_id", sa.Integer(), sa.ForeignKey("articles.id"), nullable=False),
        sa.Column("archive_code", sa.String(length=32), nullable=False),
        sa.Column("language", sa.String(length=8), nullable=False, server_default="ar"),
        sa.Column("normalized_title", sa.String(length=1024), nullable=True),
        sa.Column("normalized_summary", sa.Text(), nullable=True),
        sa.Column("normalized_content", sa.Text(), nullable=True),
        sa.Column("canonical_url", sa.String(length=2048), nullable=True),
        sa.Column("source_name", sa.String(length=255), nullable=True),
        sa.Column("category", sa.String(length=64), nullable=True),
        sa.Column("editorial_status", sa.String(length=64), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("search_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("article_id", name="uq_article_profiles_article_id"),
        sa.UniqueConstraint("archive_code", name="uq_article_profiles_archive_code"),
    )
    op.create_index("ix_article_profiles_article_id", "article_profiles", ["article_id"], unique=True)
    op.create_index("ix_article_profiles_archive_code", "article_profiles", ["archive_code"], unique=True)
    op.create_index("ix_article_profiles_source_name", "article_profiles", ["source_name"], unique=False)
    op.create_index("ix_article_profiles_category", "article_profiles", ["category"], unique=False)
    op.create_index("ix_article_profiles_editorial_status", "article_profiles", ["editorial_status"], unique=False)
    op.create_index("ix_article_profiles_category_status", "article_profiles", ["category", "editorial_status"], unique=False)

    op.create_table(
        "article_topics",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("article_id", sa.Integer(), sa.ForeignKey("articles.id"), nullable=False),
        sa.Column("topic", sa.String(length=128), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("source", sa.String(length=32), nullable=False, server_default="rule"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("article_id", "topic", name="uq_article_topics_article_topic"),
    )
    op.create_index("ix_article_topics_article_id", "article_topics", ["article_id"], unique=False)
    op.create_index("ix_article_topics_topic", "article_topics", ["topic"], unique=False)

    op.create_table(
        "article_entities",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("article_id", sa.Integer(), sa.ForeignKey("articles.id"), nullable=False),
        sa.Column("entity", sa.String(length=256), nullable=False),
        sa.Column("entity_type", sa.String(length=32), nullable=False, server_default="unknown"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("source", sa.String(length=32), nullable=False, server_default="rule"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("article_id", "entity", "entity_type", name="uq_article_entities_article_entity_type"),
    )
    op.create_index("ix_article_entities_article_id", "article_entities", ["article_id"], unique=False)
    op.create_index("ix_article_entities_entity", "article_entities", ["entity"], unique=False)
    op.create_index("ix_article_entities_entity_type", "article_entities", ["entity_type"], unique=False)

    op.create_table(
        "article_chunks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("article_id", sa.Integer(), sa.ForeignKey("articles.id"), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("language", sa.String(length=8), nullable=False, server_default="ar"),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_length", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("article_id", "chunk_index", name="uq_article_chunks_article_chunk"),
    )
    op.create_index("ix_article_chunks_article_id", "article_chunks", ["article_id"], unique=False)
    op.create_index("ix_article_chunks_article_idx", "article_chunks", ["article_id", "chunk_index"], unique=False)

    op.create_table(
        "article_vectors",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("article_id", sa.Integer(), sa.ForeignKey("articles.id"), nullable=False),
        sa.Column("chunk_id", sa.Integer(), sa.ForeignKey("article_chunks.id"), nullable=True),
        sa.Column("vector_type", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=64), nullable=False, server_default="hash-v1"),
        sa.Column("dim", sa.Integer(), nullable=False, server_default="256"),
        sa.Column("embedding", Vector(256), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("article_id", "chunk_id", "vector_type", name="uq_article_vectors_article_chunk_type"),
    )
    op.create_index("ix_article_vectors_article_id", "article_vectors", ["article_id"], unique=False)
    op.create_index("ix_article_vectors_chunk_id", "article_vectors", ["chunk_id"], unique=False)
    op.create_index("ix_article_vectors_vector_type", "article_vectors", ["vector_type"], unique=False)
    op.create_index("ix_article_vectors_content_hash", "article_vectors", ["content_hash"], unique=False)
    op.create_index("ix_article_vectors_article_type", "article_vectors", ["article_id", "vector_type"], unique=False)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_article_vectors_embedding_ivfflat "
        "ON article_vectors USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )

    op.create_table(
        "story_clusters",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("cluster_key", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=256), nullable=True),
        sa.Column("geography", sa.String(length=16), nullable=True, server_default="DZ"),
        sa.Column("category", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("cluster_key", name="uq_story_clusters_cluster_key"),
    )
    op.create_index("ix_story_clusters_cluster_key", "story_clusters", ["cluster_key"], unique=True)
    op.create_index("ix_story_clusters_geography", "story_clusters", ["geography"], unique=False)
    op.create_index("ix_story_clusters_category", "story_clusters", ["category"], unique=False)

    op.create_table(
        "story_cluster_members",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("cluster_id", sa.Integer(), sa.ForeignKey("story_clusters.id"), nullable=False),
        sa.Column("article_id", sa.Integer(), sa.ForeignKey("articles.id"), nullable=False),
        sa.Column("score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("cluster_id", "article_id", name="uq_story_cluster_member"),
    )
    op.create_index("ix_story_cluster_members_cluster_id", "story_cluster_members", ["cluster_id"], unique=False)
    op.create_index("ix_story_cluster_members_article_id", "story_cluster_members", ["article_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_story_cluster_members_article_id", table_name="story_cluster_members")
    op.drop_index("ix_story_cluster_members_cluster_id", table_name="story_cluster_members")
    op.drop_table("story_cluster_members")

    op.drop_index("ix_story_clusters_category", table_name="story_clusters")
    op.drop_index("ix_story_clusters_geography", table_name="story_clusters")
    op.drop_index("ix_story_clusters_cluster_key", table_name="story_clusters")
    op.drop_table("story_clusters")

    op.execute("DROP INDEX IF EXISTS ix_article_vectors_embedding_ivfflat")
    op.drop_index("ix_article_vectors_article_type", table_name="article_vectors")
    op.drop_index("ix_article_vectors_content_hash", table_name="article_vectors")
    op.drop_index("ix_article_vectors_vector_type", table_name="article_vectors")
    op.drop_index("ix_article_vectors_chunk_id", table_name="article_vectors")
    op.drop_index("ix_article_vectors_article_id", table_name="article_vectors")
    op.drop_table("article_vectors")

    op.drop_index("ix_article_chunks_article_idx", table_name="article_chunks")
    op.drop_index("ix_article_chunks_article_id", table_name="article_chunks")
    op.drop_table("article_chunks")

    op.drop_index("ix_article_entities_entity_type", table_name="article_entities")
    op.drop_index("ix_article_entities_entity", table_name="article_entities")
    op.drop_index("ix_article_entities_article_id", table_name="article_entities")
    op.drop_table("article_entities")

    op.drop_index("ix_article_topics_topic", table_name="article_topics")
    op.drop_index("ix_article_topics_article_id", table_name="article_topics")
    op.drop_table("article_topics")

    op.drop_index("ix_article_profiles_category_status", table_name="article_profiles")
    op.drop_index("ix_article_profiles_editorial_status", table_name="article_profiles")
    op.drop_index("ix_article_profiles_category", table_name="article_profiles")
    op.drop_index("ix_article_profiles_source_name", table_name="article_profiles")
    op.drop_index("ix_article_profiles_archive_code", table_name="article_profiles")
    op.drop_index("ix_article_profiles_article_id", table_name="article_profiles")
    op.drop_table("article_profiles")
