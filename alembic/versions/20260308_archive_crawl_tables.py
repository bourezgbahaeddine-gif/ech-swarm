"""add archive crawl state tables

Revision ID: 20260308_archive_crawl_tables
Revises: 20260305_claim_support_tables
Create Date: 2026-03-08 14:15:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260308_archive_crawl_tables"
down_revision = "20260305_claim_support_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "archive_crawl_states",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source_key", sa.String(length=64), nullable=False),
        sa.Column("source_name", sa.String(length=255), nullable=False),
        sa.Column("base_url", sa.String(length=2048), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="idle"),
        sa.Column("seeded_at", sa.DateTime(), nullable=True),
        sa.Column("last_run_started_at", sa.DateTime(), nullable=True),
        sa.Column("last_run_finished_at", sa.DateTime(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("stats_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_key", name="uq_archive_crawl_states_source_key"),
    )
    op.create_index("ix_archive_crawl_states_source_key", "archive_crawl_states", ["source_key"], unique=True)
    op.create_index("ix_archive_crawl_states_status", "archive_crawl_states", ["status"], unique=False)

    op.create_table(
        "archive_crawl_urls",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("state_id", sa.Integer(), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("url_type", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="discovered"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("depth", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("discovered_from_url", sa.String(length=2048), nullable=True),
        sa.Column("canonical_url", sa.String(length=2048), nullable=True),
        sa.Column("article_id", sa.Integer(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_http_status", sa.Integer(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("discovered_at", sa.DateTime(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(), nullable=True),
        sa.Column("indexed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["article_id"], ["articles.id"], name="fk_archive_crawl_urls_article_id_articles"),
        sa.ForeignKeyConstraint(["state_id"], ["archive_crawl_states.id"], name="fk_archive_crawl_urls_state_id_archive_crawl_states"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("state_id", "url", name="uq_archive_crawl_urls_state_url"),
    )
    op.create_index("ix_archive_crawl_urls_state_id", "archive_crawl_urls", ["state_id"], unique=False)
    op.create_index("ix_archive_crawl_urls_url_type", "archive_crawl_urls", ["url_type"], unique=False)
    op.create_index("ix_archive_crawl_urls_status", "archive_crawl_urls", ["status"], unique=False)
    op.create_index("ix_archive_crawl_urls_priority", "archive_crawl_urls", ["priority"], unique=False)
    op.create_index("ix_archive_crawl_urls_article_id", "archive_crawl_urls", ["article_id"], unique=False)
    op.create_index(
        "ix_archive_crawl_urls_state_type_status",
        "archive_crawl_urls",
        ["state_id", "url_type", "status"],
        unique=False,
    )
    op.create_index(
        "ix_archive_crawl_urls_state_priority",
        "archive_crawl_urls",
        ["state_id", "priority", "id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_archive_crawl_urls_state_priority", table_name="archive_crawl_urls")
    op.drop_index("ix_archive_crawl_urls_state_type_status", table_name="archive_crawl_urls")
    op.drop_index("ix_archive_crawl_urls_article_id", table_name="archive_crawl_urls")
    op.drop_index("ix_archive_crawl_urls_priority", table_name="archive_crawl_urls")
    op.drop_index("ix_archive_crawl_urls_status", table_name="archive_crawl_urls")
    op.drop_index("ix_archive_crawl_urls_url_type", table_name="archive_crawl_urls")
    op.drop_index("ix_archive_crawl_urls_state_id", table_name="archive_crawl_urls")
    op.drop_table("archive_crawl_urls")

    op.drop_index("ix_archive_crawl_states_status", table_name="archive_crawl_states")
    op.drop_index("ix_archive_crawl_states_source_key", table_name="archive_crawl_states")
    op.drop_table("archive_crawl_states")
