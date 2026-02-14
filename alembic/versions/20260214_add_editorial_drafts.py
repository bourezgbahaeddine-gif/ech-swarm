"""add editorial drafts table

Revision ID: 20260214_add_editorial_drafts
Revises: 20260211_add_infographics
Create Date: 2026-02-14 15:20:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260214_add_editorial_drafts"
down_revision = "20260211_add_infographics"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "editorial_drafts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("article_id", sa.Integer(), nullable=False),
        sa.Column("work_id", sa.String(length=64), nullable=False),
        sa.Column("source_action", sa.String(length=100), nullable=False, server_default="manual"),
        sa.Column("title", sa.String(length=1024), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="draft"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.String(length=255), nullable=False),
        sa.Column("updated_by", sa.String(length=255), nullable=True),
        sa.Column("applied_by", sa.String(length=255), nullable=True),
        sa.Column("applied_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["article_id"], ["articles.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("work_id"),
        sa.UniqueConstraint("article_id", "source_action", "version", name="uq_draft_article_action_version"),
    )
    op.create_index("ix_editorial_drafts_article_id", "editorial_drafts", ["article_id"], unique=False)
    op.create_index("ix_editorial_drafts_work_id", "editorial_drafts", ["work_id"], unique=True)
    op.create_index(
        "ix_editorial_drafts_article_status",
        "editorial_drafts",
        ["article_id", "status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_editorial_drafts_work_id", table_name="editorial_drafts")
    op.drop_index("ix_editorial_drafts_article_status", table_name="editorial_drafts")
    op.drop_index("ix_editorial_drafts_article_id", table_name="editorial_drafts")
    op.drop_table("editorial_drafts")
