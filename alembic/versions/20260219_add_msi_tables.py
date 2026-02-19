"""add msi monitor tables

Revision ID: 20260219_add_msi_tables
Revises: 20260218_project_memory
Create Date: 2026-02-19 12:30:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260219_add_msi_tables"
down_revision = "20260218_project_memory"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "msi_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("profile_id", sa.String(length=64), nullable=False),
        sa.Column("entity", sa.String(length=255), nullable=False),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("period_start", sa.DateTime(), nullable=False),
        sa.Column("period_end", sa.DateTime(), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False, server_default="Africa/Algiers"),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="queued"),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_by_username", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", name="uq_msi_runs_run_id"),
    )
    op.create_index("ix_msi_runs_run_id", "msi_runs", ["run_id"], unique=True)
    op.create_index("ix_msi_runs_profile_id", "msi_runs", ["profile_id"], unique=False)
    op.create_index("ix_msi_runs_entity", "msi_runs", ["entity"], unique=False)
    op.create_index("ix_msi_runs_mode", "msi_runs", ["mode"], unique=False)
    op.create_index("ix_msi_runs_status", "msi_runs", ["status"], unique=False)
    op.create_index("ix_msi_runs_created_at", "msi_runs", ["created_at"], unique=False)

    op.create_table(
        "msi_reports",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("report_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["run_id"], ["msi_runs.run_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_msi_reports_run_id", "msi_reports", ["run_id"], unique=False)
    op.create_index("ix_msi_reports_created_at", "msi_reports", ["created_at"], unique=False)

    op.create_table(
        "msi_timeseries",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("profile_id", sa.String(length=64), nullable=False),
        sa.Column("entity", sa.String(length=255), nullable=False),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("period_end", sa.DateTime(), nullable=False),
        sa.Column("msi", sa.Float(), nullable=False),
        sa.Column("level", sa.String(length=16), nullable=False),
        sa.Column("components_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("profile_id", "entity", "mode", "period_end", name="uq_msi_timeseries_point"),
    )
    op.create_index("ix_msi_timeseries_profile_id", "msi_timeseries", ["profile_id"], unique=False)
    op.create_index("ix_msi_timeseries_entity", "msi_timeseries", ["entity"], unique=False)
    op.create_index("ix_msi_timeseries_mode", "msi_timeseries", ["mode"], unique=False)
    op.create_index("ix_msi_timeseries_period_end", "msi_timeseries", ["period_end"], unique=False)
    op.create_index(
        "ix_msi_timeseries_lookup",
        "msi_timeseries",
        ["profile_id", "entity", "mode", "period_end"],
        unique=False,
    )

    op.create_table(
        "msi_artifacts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("items_json", sa.JSON(), nullable=False),
        sa.Column("aggregates_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["run_id"], ["msi_runs.run_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_msi_artifacts_run_id", "msi_artifacts", ["run_id"], unique=False)

    op.create_table(
        "msi_job_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("node", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("ts", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["run_id"], ["msi_runs.run_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_msi_job_events_run_id", "msi_job_events", ["run_id"], unique=False)
    op.create_index("ix_msi_job_events_node", "msi_job_events", ["node"], unique=False)
    op.create_index("ix_msi_job_events_event_type", "msi_job_events", ["event_type"], unique=False)
    op.create_index("ix_msi_job_events_ts", "msi_job_events", ["ts"], unique=False)
    op.create_index("ix_msi_job_events_run_ts", "msi_job_events", ["run_id", "ts"], unique=False)

    op.create_table(
        "msi_watchlist",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("profile_id", sa.String(length=64), nullable=False),
        sa.Column("entity", sa.String(length=255), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("run_daily", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("run_weekly", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_by_username", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("profile_id", "entity", name="uq_msi_watchlist_profile_entity"),
    )
    op.create_index("ix_msi_watchlist_profile_id", "msi_watchlist", ["profile_id"], unique=False)
    op.create_index("ix_msi_watchlist_entity", "msi_watchlist", ["entity"], unique=False)
    op.create_index("ix_msi_watchlist_enabled", "msi_watchlist", ["enabled"], unique=False)

    op.create_table(
        "msi_baselines",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("profile_id", sa.String(length=64), nullable=False),
        sa.Column("entity", sa.String(length=255), nullable=False),
        sa.Column("pressure_history", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("last_topic_dist", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("baseline_window_days", sa.Integer(), nullable=False, server_default="90"),
        sa.Column("last_updated", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("profile_id", "entity", name="uq_msi_baseline_profile_entity"),
    )
    op.create_index("ix_msi_baselines_profile_id", "msi_baselines", ["profile_id"], unique=False)
    op.create_index("ix_msi_baselines_entity", "msi_baselines", ["entity"], unique=False)
    op.create_index("ix_msi_baselines_last_updated", "msi_baselines", ["last_updated"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_msi_baselines_last_updated", table_name="msi_baselines")
    op.drop_index("ix_msi_baselines_entity", table_name="msi_baselines")
    op.drop_index("ix_msi_baselines_profile_id", table_name="msi_baselines")
    op.drop_table("msi_baselines")

    op.drop_index("ix_msi_watchlist_enabled", table_name="msi_watchlist")
    op.drop_index("ix_msi_watchlist_entity", table_name="msi_watchlist")
    op.drop_index("ix_msi_watchlist_profile_id", table_name="msi_watchlist")
    op.drop_table("msi_watchlist")

    op.drop_index("ix_msi_job_events_run_ts", table_name="msi_job_events")
    op.drop_index("ix_msi_job_events_ts", table_name="msi_job_events")
    op.drop_index("ix_msi_job_events_event_type", table_name="msi_job_events")
    op.drop_index("ix_msi_job_events_node", table_name="msi_job_events")
    op.drop_index("ix_msi_job_events_run_id", table_name="msi_job_events")
    op.drop_table("msi_job_events")

    op.drop_index("ix_msi_artifacts_run_id", table_name="msi_artifacts")
    op.drop_table("msi_artifacts")

    op.drop_index("ix_msi_timeseries_lookup", table_name="msi_timeseries")
    op.drop_index("ix_msi_timeseries_period_end", table_name="msi_timeseries")
    op.drop_index("ix_msi_timeseries_mode", table_name="msi_timeseries")
    op.drop_index("ix_msi_timeseries_entity", table_name="msi_timeseries")
    op.drop_index("ix_msi_timeseries_profile_id", table_name="msi_timeseries")
    op.drop_table("msi_timeseries")

    op.drop_index("ix_msi_reports_created_at", table_name="msi_reports")
    op.drop_index("ix_msi_reports_run_id", table_name="msi_reports")
    op.drop_table("msi_reports")

    op.drop_index("ix_msi_runs_created_at", table_name="msi_runs")
    op.drop_index("ix_msi_runs_status", table_name="msi_runs")
    op.drop_index("ix_msi_runs_mode", table_name="msi_runs")
    op.drop_index("ix_msi_runs_entity", table_name="msi_runs")
    op.drop_index("ix_msi_runs_profile_id", table_name="msi_runs")
    op.drop_index("ix_msi_runs_run_id", table_name="msi_runs")
    op.drop_table("msi_runs")
