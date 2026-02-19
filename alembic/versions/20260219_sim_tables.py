"""add audience simulator tables

Revision ID: 20260219_sim_tables
Revises: 20260219_msi_wl_alias_seed
Create Date: 2026-02-19 13:20:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260219_sim_tables"
down_revision = "20260219_msi_wl_alias_seed"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sim_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("article_id", sa.Integer(), nullable=True),
        sa.Column("draft_id", sa.Integer(), nullable=True),
        sa.Column("headline", sa.String(length=1024), nullable=False),
        sa.Column("body_excerpt", sa.Text(), nullable=True),
        sa.Column("platform", sa.String(length=16), nullable=False, server_default="facebook"),
        sa.Column("mode", sa.String(length=16), nullable=False, server_default="fast"),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="queued"),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_by_username", sa.String(length=64), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["article_id"], ["articles.id"]),
        sa.ForeignKeyConstraint(["draft_id"], ["editorial_drafts.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", name="uq_sim_runs_run_id"),
    )
    op.create_index("ix_sim_runs_run_id", "sim_runs", ["run_id"], unique=True)
    op.create_index("ix_sim_runs_article_id", "sim_runs", ["article_id"], unique=False)
    op.create_index("ix_sim_runs_draft_id", "sim_runs", ["draft_id"], unique=False)
    op.create_index("ix_sim_runs_platform", "sim_runs", ["platform"], unique=False)
    op.create_index("ix_sim_runs_mode", "sim_runs", ["mode"], unique=False)
    op.create_index("ix_sim_runs_status", "sim_runs", ["status"], unique=False)
    op.create_index("ix_sim_runs_created_at", "sim_runs", ["created_at"], unique=False)
    op.create_index("ix_sim_runs_created_by_user_id", "sim_runs", ["created_by_user_id"], unique=False)
    op.create_index("ix_sim_runs_idempotency_key", "sim_runs", ["idempotency_key"], unique=False)
    op.create_index("ix_sim_runs_status_created", "sim_runs", ["status", "created_at"], unique=False)

    op.create_table(
        "sim_results",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("risk_score", sa.Float(), nullable=False),
        sa.Column("virality_score", sa.Float(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("breakdown_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("reactions_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("advice_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("red_flags_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["run_id"], ["sim_runs.run_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sim_results_run_id", "sim_results", ["run_id"], unique=False)
    op.create_index("ix_sim_results_created_at", "sim_results", ["created_at"], unique=False)

    op.create_table(
        "sim_feedback",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("editor_notes", sa.Text(), nullable=True),
        sa.Column("editor_id", sa.Integer(), nullable=True),
        sa.Column("editor_username", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["run_id"], ["sim_runs.run_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["editor_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sim_feedback_run_id", "sim_feedback", ["run_id"], unique=False)
    op.create_index("ix_sim_feedback_action", "sim_feedback", ["action"], unique=False)
    op.create_index("ix_sim_feedback_editor_id", "sim_feedback", ["editor_id"], unique=False)
    op.create_index("ix_sim_feedback_created_at", "sim_feedback", ["created_at"], unique=False)

    op.create_table(
        "sim_calibration",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("platform", sa.String(length=16), nullable=False),
        sa.Column("bucket", sa.String(length=32), nullable=False),
        sa.Column("actual_ctr", sa.Float(), nullable=True),
        sa.Column("actual_backlash", sa.Float(), nullable=True),
        sa.Column("actual_shares", sa.Float(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sim_calibration_platform", "sim_calibration", ["platform"], unique=False)
    op.create_index("ix_sim_calibration_bucket", "sim_calibration", ["bucket"], unique=False)
    op.create_index("ix_sim_calibration_updated_at", "sim_calibration", ["updated_at"], unique=False)

    op.create_table(
        "sim_job_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("node", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("ts", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["run_id"], ["sim_runs.run_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sim_job_events_run_id", "sim_job_events", ["run_id"], unique=False)
    op.create_index("ix_sim_job_events_node", "sim_job_events", ["node"], unique=False)
    op.create_index("ix_sim_job_events_event_type", "sim_job_events", ["event_type"], unique=False)
    op.create_index("ix_sim_job_events_ts", "sim_job_events", ["ts"], unique=False)
    op.create_index("ix_sim_job_events_run_ts", "sim_job_events", ["run_id", "ts"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_sim_job_events_run_ts", table_name="sim_job_events")
    op.drop_index("ix_sim_job_events_ts", table_name="sim_job_events")
    op.drop_index("ix_sim_job_events_event_type", table_name="sim_job_events")
    op.drop_index("ix_sim_job_events_node", table_name="sim_job_events")
    op.drop_index("ix_sim_job_events_run_id", table_name="sim_job_events")
    op.drop_table("sim_job_events")

    op.drop_index("ix_sim_calibration_updated_at", table_name="sim_calibration")
    op.drop_index("ix_sim_calibration_bucket", table_name="sim_calibration")
    op.drop_index("ix_sim_calibration_platform", table_name="sim_calibration")
    op.drop_table("sim_calibration")

    op.drop_index("ix_sim_feedback_created_at", table_name="sim_feedback")
    op.drop_index("ix_sim_feedback_editor_id", table_name="sim_feedback")
    op.drop_index("ix_sim_feedback_action", table_name="sim_feedback")
    op.drop_index("ix_sim_feedback_run_id", table_name="sim_feedback")
    op.drop_table("sim_feedback")

    op.drop_index("ix_sim_results_created_at", table_name="sim_results")
    op.drop_index("ix_sim_results_run_id", table_name="sim_results")
    op.drop_table("sim_results")

    op.drop_index("ix_sim_runs_status_created", table_name="sim_runs")
    op.drop_index("ix_sim_runs_idempotency_key", table_name="sim_runs")
    op.drop_index("ix_sim_runs_created_by_user_id", table_name="sim_runs")
    op.drop_index("ix_sim_runs_created_at", table_name="sim_runs")
    op.drop_index("ix_sim_runs_status", table_name="sim_runs")
    op.drop_index("ix_sim_runs_mode", table_name="sim_runs")
    op.drop_index("ix_sim_runs_platform", table_name="sim_runs")
    op.drop_index("ix_sim_runs_draft_id", table_name="sim_runs")
    op.drop_index("ix_sim_runs_article_id", table_name="sim_runs")
    op.drop_index("ix_sim_runs_run_id", table_name="sim_runs")
    op.drop_table("sim_runs")
