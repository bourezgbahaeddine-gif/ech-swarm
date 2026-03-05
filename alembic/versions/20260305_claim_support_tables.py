"""add article claims and claim supports tables

Revision ID: 20260305_claim_support_tables
Revises: 20260301_event_memo_sprint1
Create Date: 2026-03-05 09:30:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260305_claim_support_tables"
down_revision = "20260301_event_memo_sprint1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "article_claims",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("article_id", sa.Integer(), nullable=False),
        sa.Column("quality_report_id", sa.Integer(), nullable=True),
        sa.Column("work_id", sa.String(length=64), nullable=True),
        sa.Column("claim_external_id", sa.String(length=64), nullable=False),
        sa.Column("claim_text", sa.Text(), nullable=False),
        sa.Column("claim_type", sa.String(length=32), nullable=True),
        sa.Column("risk_level", sa.String(length=16), nullable=False, server_default="low"),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("sensitive", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("blocking", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("supported", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("unverifiable", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("unverifiable_reason", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True, server_default=sa.text("'{}'::json")),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["article_id"], ["articles.id"], name="fk_article_claims_article_id_articles"),
        sa.ForeignKeyConstraint(
            ["quality_report_id"],
            ["article_quality_reports.id"],
            name="fk_article_claims_quality_report_id_article_quality_reports",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("article_id", "claim_external_id", name="uq_article_claim_article_external"),
    )
    op.create_index("ix_article_claims_article_id", "article_claims", ["article_id"], unique=False)
    op.create_index("ix_article_claims_quality_report_id", "article_claims", ["quality_report_id"], unique=False)
    op.create_index("ix_article_claims_work_id", "article_claims", ["work_id"], unique=False)
    op.create_index("ix_article_claim_article_risk", "article_claims", ["article_id", "risk_level"], unique=False)

    op.create_table(
        "article_claim_supports",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("claim_id", sa.Integer(), nullable=False),
        sa.Column("support_kind", sa.String(length=24), nullable=False, server_default="url"),
        sa.Column("support_ref", sa.String(length=2048), nullable=False),
        sa.Column("source_host", sa.String(length=255), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["claim_id"], ["article_claims.id"], name="fk_article_claim_supports_claim_id_article_claims", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("claim_id", "support_ref", name="uq_article_claim_support_unique"),
    )
    op.create_index("ix_article_claim_supports_claim_id", "article_claim_supports", ["claim_id"], unique=False)
    op.create_index("ix_article_claim_support_kind", "article_claim_supports", ["support_kind"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_article_claim_support_kind", table_name="article_claim_supports")
    op.drop_index("ix_article_claim_supports_claim_id", table_name="article_claim_supports")
    op.drop_table("article_claim_supports")

    op.drop_index("ix_article_claim_article_risk", table_name="article_claims")
    op.drop_index("ix_article_claims_work_id", table_name="article_claims")
    op.drop_index("ix_article_claims_quality_report_id", table_name="article_claims")
    op.drop_index("ix_article_claims_article_id", table_name="article_claims")
    op.drop_table("article_claims")

