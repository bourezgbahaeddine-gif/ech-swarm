"""add competitor xray tables

Revision ID: 20260221_competitor_xray_tables
Revises: 20260221_media_logger_tables
Create Date: 2026-02-21 12:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260221_competitor_xray_tables"
down_revision = "20260221_media_logger_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "competitor_xray_sources",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("feed_url", sa.String(length=2048), nullable=False),
        sa.Column("domain", sa.String(length=255), nullable=False),
        sa.Column("language", sa.String(length=16), nullable=False, server_default="ar"),
        sa.Column("weight", sa.Float(), nullable=False, server_default="1"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("feed_url", name="uq_competitor_xray_sources_feed_url"),
    )
    op.create_index("ix_competitor_xray_sources_feed_url", "competitor_xray_sources", ["feed_url"], unique=True)
    op.create_index("ix_competitor_xray_sources_domain", "competitor_xray_sources", ["domain"], unique=False)
    op.create_index("ix_competitor_xray_sources_enabled", "competitor_xray_sources", ["enabled"], unique=False)
    op.create_index("ix_competitor_xray_sources_created_at", "competitor_xray_sources", ["created_at"], unique=False)
    op.create_index("ix_competitor_xray_sources_updated_at", "competitor_xray_sources", ["updated_at"], unique=False)

    op.create_table(
        "competitor_xray_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="queued"),
        sa.Column("total_scanned", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_gaps", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_by_username", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", name="uq_competitor_xray_runs_run_id"),
    )
    op.create_index("ix_competitor_xray_runs_run_id", "competitor_xray_runs", ["run_id"], unique=True)
    op.create_index("ix_competitor_xray_runs_status", "competitor_xray_runs", ["status"], unique=False)
    op.create_index("ix_competitor_xray_runs_idempotency_key", "competitor_xray_runs", ["idempotency_key"], unique=False)
    op.create_index("ix_competitor_xray_runs_created_by_user_id", "competitor_xray_runs", ["created_by_user_id"], unique=False)
    op.create_index("ix_competitor_xray_runs_created_at", "competitor_xray_runs", ["created_at"], unique=False)
    op.create_index("ix_competitor_xray_runs_status_created", "competitor_xray_runs", ["status", "created_at"], unique=False)

    op.create_table(
        "competitor_xray_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=True),
        sa.Column("competitor_title", sa.String(length=1024), nullable=False),
        sa.Column("competitor_url", sa.String(length=2048), nullable=False),
        sa.Column("competitor_summary", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("priority_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="new"),
        sa.Column("angle_title", sa.String(length=512), nullable=True),
        sa.Column("angle_rationale", sa.Text(), nullable=True),
        sa.Column("angle_questions_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("starter_sources_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("matched_article_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["run_id"], ["competitor_xray_runs.run_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["competitor_xray_sources.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["matched_article_id"], ["articles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_competitor_xray_items_run_id", "competitor_xray_items", ["run_id"], unique=False)
    op.create_index("ix_competitor_xray_items_source_id", "competitor_xray_items", ["source_id"], unique=False)
    op.create_index("ix_competitor_xray_items_competitor_url", "competitor_xray_items", ["competitor_url"], unique=False)
    op.create_index("ix_competitor_xray_items_published_at", "competitor_xray_items", ["published_at"], unique=False)
    op.create_index("ix_competitor_xray_items_priority_score", "competitor_xray_items", ["priority_score"], unique=False)
    op.create_index("ix_competitor_xray_items_status", "competitor_xray_items", ["status"], unique=False)
    op.create_index("ix_competitor_xray_items_matched_article_id", "competitor_xray_items", ["matched_article_id"], unique=False)
    op.create_index("ix_competitor_xray_items_created_at", "competitor_xray_items", ["created_at"], unique=False)
    op.create_index("ix_competitor_xray_items_updated_at", "competitor_xray_items", ["updated_at"], unique=False)
    op.create_index("ix_competitor_xray_items_priority_created", "competitor_xray_items", ["priority_score", "created_at"], unique=False)

    op.create_table(
        "competitor_xray_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("node", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("ts", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["run_id"], ["competitor_xray_runs.run_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_competitor_xray_events_run_id", "competitor_xray_events", ["run_id"], unique=False)
    op.create_index("ix_competitor_xray_events_node", "competitor_xray_events", ["node"], unique=False)
    op.create_index("ix_competitor_xray_events_event_type", "competitor_xray_events", ["event_type"], unique=False)
    op.create_index("ix_competitor_xray_events_ts", "competitor_xray_events", ["ts"], unique=False)
    op.create_index("ix_competitor_xray_events_run_ts", "competitor_xray_events", ["run_id", "ts"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_competitor_xray_events_run_ts", table_name="competitor_xray_events")
    op.drop_index("ix_competitor_xray_events_ts", table_name="competitor_xray_events")
    op.drop_index("ix_competitor_xray_events_event_type", table_name="competitor_xray_events")
    op.drop_index("ix_competitor_xray_events_node", table_name="competitor_xray_events")
    op.drop_index("ix_competitor_xray_events_run_id", table_name="competitor_xray_events")
    op.drop_table("competitor_xray_events")

    op.drop_index("ix_competitor_xray_items_priority_created", table_name="competitor_xray_items")
    op.drop_index("ix_competitor_xray_items_updated_at", table_name="competitor_xray_items")
    op.drop_index("ix_competitor_xray_items_created_at", table_name="competitor_xray_items")
    op.drop_index("ix_competitor_xray_items_matched_article_id", table_name="competitor_xray_items")
    op.drop_index("ix_competitor_xray_items_status", table_name="competitor_xray_items")
    op.drop_index("ix_competitor_xray_items_priority_score", table_name="competitor_xray_items")
    op.drop_index("ix_competitor_xray_items_published_at", table_name="competitor_xray_items")
    op.drop_index("ix_competitor_xray_items_competitor_url", table_name="competitor_xray_items")
    op.drop_index("ix_competitor_xray_items_source_id", table_name="competitor_xray_items")
    op.drop_index("ix_competitor_xray_items_run_id", table_name="competitor_xray_items")
    op.drop_table("competitor_xray_items")

    op.drop_index("ix_competitor_xray_runs_status_created", table_name="competitor_xray_runs")
    op.drop_index("ix_competitor_xray_runs_created_at", table_name="competitor_xray_runs")
    op.drop_index("ix_competitor_xray_runs_created_by_user_id", table_name="competitor_xray_runs")
    op.drop_index("ix_competitor_xray_runs_idempotency_key", table_name="competitor_xray_runs")
    op.drop_index("ix_competitor_xray_runs_status", table_name="competitor_xray_runs")
    op.drop_index("ix_competitor_xray_runs_run_id", table_name="competitor_xray_runs")
    op.drop_table("competitor_xray_runs")

    op.drop_index("ix_competitor_xray_sources_updated_at", table_name="competitor_xray_sources")
    op.drop_index("ix_competitor_xray_sources_created_at", table_name="competitor_xray_sources")
    op.drop_index("ix_competitor_xray_sources_enabled", table_name="competitor_xray_sources")
    op.drop_index("ix_competitor_xray_sources_domain", table_name="competitor_xray_sources")
    op.drop_index("ix_competitor_xray_sources_feed_url", table_name="competitor_xray_sources")
    op.drop_table("competitor_xray_sources")
