"""add article quality reports table

Revision ID: 20260217_quality_reports
Revises: 20260217_single_cluster_member
Create Date: 2026-02-17 13:20:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260217_quality_reports"
down_revision = "20260217_single_cluster_member"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "article_quality_reports",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("article_id", sa.Integer(), sa.ForeignKey("articles.id"), nullable=False),
        sa.Column("stage", sa.String(length=64), nullable=False),
        sa.Column("passed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("blocking_reasons", sa.JSON(), nullable=True),
        sa.Column("actionable_fixes", sa.JSON(), nullable=True),
        sa.Column("report_json", sa.JSON(), nullable=True),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_article_quality_reports_article_id", "article_quality_reports", ["article_id"], unique=False)
    op.create_index("ix_article_quality_reports_stage", "article_quality_reports", ["stage"], unique=False)
    op.create_index(
        "ix_quality_article_stage_created",
        "article_quality_reports",
        ["article_id", "stage", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_quality_article_stage_created", table_name="article_quality_reports")
    op.drop_index("ix_article_quality_reports_stage", table_name="article_quality_reports")
    op.drop_index("ix_article_quality_reports_article_id", table_name="article_quality_reports")
    op.drop_table("article_quality_reports")

