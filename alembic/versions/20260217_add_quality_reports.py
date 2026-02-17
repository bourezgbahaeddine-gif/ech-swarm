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
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_exists = "article_quality_reports" in inspector.get_table_names()

    if not table_exists:
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

    # Keep migration idempotent for environments where table was pre-created manually.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_article_quality_reports_article_id "
        "ON article_quality_reports (article_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_article_quality_reports_stage "
        "ON article_quality_reports (stage)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_quality_article_stage_created "
        "ON article_quality_reports (article_id, stage, created_at)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_quality_article_stage_created")
    op.execute("DROP INDEX IF EXISTS ix_article_quality_reports_stage")
    op.execute("DROP INDEX IF EXISTS ix_article_quality_reports_article_id")
    op.execute("DROP TABLE IF EXISTS article_quality_reports")
