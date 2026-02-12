"""add minimal performance indexes

Revision ID: 20260211_add_min_indexes
Revises: 
Create Date: 2026-02-11
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260211_add_min_indexes"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.create_index(
        "ix_articles_original_title_trgm",
        "articles",
        ["original_title"],
        postgresql_using="gin",
        postgresql_ops={"original_title": "gin_trgm_ops"},
    )

    op.create_index(
        "ix_articles_title_ar_trgm",
        "articles",
        ["title_ar"],
        postgresql_using="gin",
        postgresql_ops={"title_ar": "gin_trgm_ops"},
    )

    op.create_index(
        "ix_articles_published_at",
        "articles",
        ["published_at"],
        postgresql_using="btree",
    )

    op.create_index(
        "ix_articles_candidate_order",
        "articles",
        ["status", "importance_score", "crawled_at"],
    )

    op.create_index(
        "ix_editor_decisions_article_id",
        "editor_decisions",
        ["article_id"],
    )


def downgrade():
    op.drop_index("ix_editor_decisions_article_id", table_name="editor_decisions")
    op.drop_index("ix_articles_candidate_order", table_name="articles")
    op.drop_index("ix_articles_published_at", table_name="articles")
    op.drop_index("ix_articles_title_ar_trgm", table_name="articles")
    op.drop_index("ix_articles_original_title_trgm", table_name="articles")
