"""add fingerprints and article relations tables

Revision ID: 20260216_fingerprints_relations
Revises: 20260216_knowledge_vectors
Create Date: 2026-02-16 19:30:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260216_fingerprints_relations"
down_revision = "20260216_knowledge_vectors"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "article_fingerprints",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("article_id", sa.Integer(), sa.ForeignKey("articles.id"), nullable=False),
        sa.Column("simhash", sa.BigInteger(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("shingles", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("article_id", name="uq_article_fingerprints_article_id"),
    )
    op.create_index("ix_article_fingerprints_article_id", "article_fingerprints", ["article_id"], unique=True)
    op.create_index("ix_article_fingerprints_simhash", "article_fingerprints", ["simhash"], unique=False)

    op.create_table(
        "article_relations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("from_article_id", sa.Integer(), sa.ForeignKey("articles.id"), nullable=False),
        sa.Column("to_article_id", sa.Integer(), sa.ForeignKey("articles.id"), nullable=False),
        sa.Column("relation_type", sa.String(length=32), nullable=False),
        sa.Column("score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint(
            "from_article_id",
            "to_article_id",
            "relation_type",
            name="uq_article_relations_edge",
        ),
    )
    op.create_index("ix_article_relations_from_article_id", "article_relations", ["from_article_id"], unique=False)
    op.create_index("ix_article_relations_to_article_id", "article_relations", ["to_article_id"], unique=False)
    op.create_index("ix_article_relations_relation_type", "article_relations", ["relation_type"], unique=False)
    op.create_index(
        "ix_article_relations_from_type",
        "article_relations",
        ["from_article_id", "relation_type"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_article_relations_from_type", table_name="article_relations")
    op.drop_index("ix_article_relations_relation_type", table_name="article_relations")
    op.drop_index("ix_article_relations_to_article_id", table_name="article_relations")
    op.drop_index("ix_article_relations_from_article_id", table_name="article_relations")
    op.drop_table("article_relations")

    op.drop_index("ix_article_fingerprints_simhash", table_name="article_fingerprints")
    op.drop_index("ix_article_fingerprints_article_id", table_name="article_fingerprints")
    op.drop_table("article_fingerprints")

