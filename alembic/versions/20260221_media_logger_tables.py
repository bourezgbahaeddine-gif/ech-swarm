"""add media logger tables

Revision ID: 20260221_media_logger_tables
Revises: 20260219_sim_tables
Create Date: 2026-02-21 11:20:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260221_media_logger_tables"
down_revision = "20260219_sim_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "media_logger_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("source_type", sa.String(length=16), nullable=False, server_default="url"),
        sa.Column("source_ref", sa.Text(), nullable=False),
        sa.Column("source_label", sa.String(length=255), nullable=True),
        sa.Column("language_hint", sa.String(length=16), nullable=False, server_default="ar"),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="queued"),
        sa.Column("transcript_language", sa.String(length=16), nullable=True),
        sa.Column("transcript_text", sa.Text(), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("segments_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("highlights_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_by_username", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", name="uq_media_logger_runs_run_id"),
    )
    op.create_index("ix_media_logger_runs_run_id", "media_logger_runs", ["run_id"], unique=True)
    op.create_index("ix_media_logger_runs_source_type", "media_logger_runs", ["source_type"], unique=False)
    op.create_index("ix_media_logger_runs_status", "media_logger_runs", ["status"], unique=False)
    op.create_index("ix_media_logger_runs_idempotency_key", "media_logger_runs", ["idempotency_key"], unique=False)
    op.create_index("ix_media_logger_runs_created_by_user_id", "media_logger_runs", ["created_by_user_id"], unique=False)
    op.create_index("ix_media_logger_runs_created_at", "media_logger_runs", ["created_at"], unique=False)
    op.create_index("ix_media_logger_runs_status_created", "media_logger_runs", ["status", "created_at"], unique=False)

    op.create_table(
        "media_logger_segments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("segment_index", sa.Integer(), nullable=False),
        sa.Column("start_sec", sa.Float(), nullable=False),
        sa.Column("end_sec", sa.Float(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("speaker", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["run_id"], ["media_logger_runs.run_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_media_logger_segments_run_id", "media_logger_segments", ["run_id"], unique=False)
    op.create_index("ix_media_logger_segments_segment_index", "media_logger_segments", ["segment_index"], unique=False)
    op.create_index("ix_media_logger_segments_created_at", "media_logger_segments", ["created_at"], unique=False)
    op.create_index("ix_media_logger_segments_run_order", "media_logger_segments", ["run_id", "segment_index"], unique=False)
    op.create_index("ix_media_logger_segments_run_start", "media_logger_segments", ["run_id", "start_sec"], unique=False)

    op.create_table(
        "media_logger_highlights",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("quote", sa.Text(), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column("start_sec", sa.Float(), nullable=False),
        sa.Column("end_sec", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["run_id"], ["media_logger_runs.run_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_media_logger_highlights_run_id", "media_logger_highlights", ["run_id"], unique=False)
    op.create_index("ix_media_logger_highlights_created_at", "media_logger_highlights", ["created_at"], unique=False)
    op.create_index("ix_media_logger_highlights_run_rank", "media_logger_highlights", ["run_id", "rank"], unique=False)

    op.create_table(
        "media_logger_job_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("node", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("ts", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["run_id"], ["media_logger_runs.run_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_media_logger_job_events_run_id", "media_logger_job_events", ["run_id"], unique=False)
    op.create_index("ix_media_logger_job_events_node", "media_logger_job_events", ["node"], unique=False)
    op.create_index("ix_media_logger_job_events_event_type", "media_logger_job_events", ["event_type"], unique=False)
    op.create_index("ix_media_logger_job_events_ts", "media_logger_job_events", ["ts"], unique=False)
    op.create_index("ix_media_logger_job_events_run_ts", "media_logger_job_events", ["run_id", "ts"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_media_logger_job_events_run_ts", table_name="media_logger_job_events")
    op.drop_index("ix_media_logger_job_events_ts", table_name="media_logger_job_events")
    op.drop_index("ix_media_logger_job_events_event_type", table_name="media_logger_job_events")
    op.drop_index("ix_media_logger_job_events_node", table_name="media_logger_job_events")
    op.drop_index("ix_media_logger_job_events_run_id", table_name="media_logger_job_events")
    op.drop_table("media_logger_job_events")

    op.drop_index("ix_media_logger_highlights_run_rank", table_name="media_logger_highlights")
    op.drop_index("ix_media_logger_highlights_created_at", table_name="media_logger_highlights")
    op.drop_index("ix_media_logger_highlights_run_id", table_name="media_logger_highlights")
    op.drop_table("media_logger_highlights")

    op.drop_index("ix_media_logger_segments_run_start", table_name="media_logger_segments")
    op.drop_index("ix_media_logger_segments_run_order", table_name="media_logger_segments")
    op.drop_index("ix_media_logger_segments_created_at", table_name="media_logger_segments")
    op.drop_index("ix_media_logger_segments_segment_index", table_name="media_logger_segments")
    op.drop_index("ix_media_logger_segments_run_id", table_name="media_logger_segments")
    op.drop_table("media_logger_segments")

    op.drop_index("ix_media_logger_runs_status_created", table_name="media_logger_runs")
    op.drop_index("ix_media_logger_runs_created_at", table_name="media_logger_runs")
    op.drop_index("ix_media_logger_runs_created_by_user_id", table_name="media_logger_runs")
    op.drop_index("ix_media_logger_runs_idempotency_key", table_name="media_logger_runs")
    op.drop_index("ix_media_logger_runs_status", table_name="media_logger_runs")
    op.drop_index("ix_media_logger_runs_source_type", table_name="media_logger_runs")
    op.drop_index("ix_media_logger_runs_run_id", table_name="media_logger_runs")
    op.drop_table("media_logger_runs")
