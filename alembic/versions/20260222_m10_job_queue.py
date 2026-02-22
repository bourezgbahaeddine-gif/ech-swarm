"""add job queue tables for async workers

Revision ID: 20260222_m10_job_queue
Revises: 20260222_link_intelligence_tables
Create Date: 2026-02-22 12:30:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260222_m10_job_queue"
down_revision = "20260222_link_intelligence_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "job_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_type", sa.String(length=64), nullable=False),
        sa.Column("queue_name", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="queued"),
        sa.Column("priority", sa.String(length=16), nullable=False, server_default="normal"),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("actor_username", sa.String(length=64), nullable=True),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("queued_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("result_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_job_runs_job_type", "job_runs", ["job_type"], unique=False)
    op.create_index("ix_job_runs_queue_name", "job_runs", ["queue_name"], unique=False)
    op.create_index("ix_job_runs_entity_id", "job_runs", ["entity_id"], unique=False)
    op.create_index("ix_job_runs_status", "job_runs", ["status"], unique=False)
    op.create_index("ix_job_runs_request_id", "job_runs", ["request_id"], unique=False)
    op.create_index("ix_job_runs_correlation_id", "job_runs", ["correlation_id"], unique=False)
    op.create_index("ix_job_runs_actor_user_id", "job_runs", ["actor_user_id"], unique=False)
    op.create_index("ix_job_runs_queued_at", "job_runs", ["queued_at"], unique=False)
    op.create_index("ix_job_runs_created_at", "job_runs", ["created_at"], unique=False)
    op.create_index("ix_job_runs_updated_at", "job_runs", ["updated_at"], unique=False)
    op.create_index("ix_job_runs_queue_status", "job_runs", ["queue_name", "status"], unique=False)
    op.create_index("ix_job_runs_type_queued", "job_runs", ["job_type", "queued_at"], unique=False)

    op.create_table(
        "dead_letter_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("original_job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_type", sa.String(length=64), nullable=False),
        sa.Column("queue_name", sa.String(length=64), nullable=False),
        sa.Column("failed_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("error", sa.Text(), nullable=False),
        sa.Column("traceback", sa.Text(), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("meta_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_dead_letter_jobs_original_job_id", "dead_letter_jobs", ["original_job_id"], unique=False)
    op.create_index("ix_dead_letter_jobs_job_type", "dead_letter_jobs", ["job_type"], unique=False)
    op.create_index("ix_dead_letter_jobs_queue_name", "dead_letter_jobs", ["queue_name"], unique=False)
    op.create_index("ix_dead_letter_jobs_failed_at", "dead_letter_jobs", ["failed_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_dead_letter_jobs_failed_at", table_name="dead_letter_jobs")
    op.drop_index("ix_dead_letter_jobs_queue_name", table_name="dead_letter_jobs")
    op.drop_index("ix_dead_letter_jobs_job_type", table_name="dead_letter_jobs")
    op.drop_index("ix_dead_letter_jobs_original_job_id", table_name="dead_letter_jobs")
    op.drop_table("dead_letter_jobs")

    op.drop_index("ix_job_runs_type_queued", table_name="job_runs")
    op.drop_index("ix_job_runs_queue_status", table_name="job_runs")
    op.drop_index("ix_job_runs_updated_at", table_name="job_runs")
    op.drop_index("ix_job_runs_created_at", table_name="job_runs")
    op.drop_index("ix_job_runs_queued_at", table_name="job_runs")
    op.drop_index("ix_job_runs_actor_user_id", table_name="job_runs")
    op.drop_index("ix_job_runs_correlation_id", table_name="job_runs")
    op.drop_index("ix_job_runs_request_id", table_name="job_runs")
    op.drop_index("ix_job_runs_status", table_name="job_runs")
    op.drop_index("ix_job_runs_entity_id", table_name="job_runs")
    op.drop_index("ix_job_runs_queue_name", table_name="job_runs")
    op.drop_index("ix_job_runs_job_type", table_name="job_runs")
    op.drop_table("job_runs")

