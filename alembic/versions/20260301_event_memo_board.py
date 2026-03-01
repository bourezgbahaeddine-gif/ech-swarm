"""add events memo board table

Revision ID: 20260301_event_memo_board
Revises: 20260226_script_status_failed
Create Date: 2026-03-01 11:10:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260301_event_memo_board"
down_revision = "20260226_script_status_failed"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "event_memo_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("scope", sa.String(length=24), nullable=False, server_default="national"),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("coverage_plan", sa.Text(), nullable=True),
        sa.Column("starts_at", sa.DateTime(), nullable=False),
        sa.Column("ends_at", sa.DateTime(), nullable=True),
        sa.Column("timezone", sa.String(length=64), nullable=False, server_default="Africa/Algiers"),
        sa.Column("country_code", sa.String(length=8), nullable=True),
        sa.Column("is_all_day", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("lead_time_hours", sa.Integer(), nullable=False, server_default="24"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="planned"),
        sa.Column("source_url", sa.String(length=2048), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_by_username", sa.String(length=64), nullable=True),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_username", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("scope IN ('national', 'international', 'religious')", name="ck_event_memo_scope"),
        sa.CheckConstraint("status IN ('planned', 'monitoring', 'covered', 'dismissed')", name="ck_event_memo_status"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_event_memo_items_scope", "event_memo_items", ["scope"], unique=False)
    op.create_index("ix_event_memo_items_status", "event_memo_items", ["status"], unique=False)
    op.create_index("ix_event_memo_items_starts_at", "event_memo_items", ["starts_at"], unique=False)
    op.create_index("ix_event_memo_items_created_by_user_id", "event_memo_items", ["created_by_user_id"], unique=False)
    op.create_index("ix_event_memo_items_updated_by_user_id", "event_memo_items", ["updated_by_user_id"], unique=False)
    op.create_index("ix_event_memo_scope_status_start", "event_memo_items", ["scope", "status", "starts_at"], unique=False)
    op.create_index("ix_event_memo_status_start", "event_memo_items", ["status", "starts_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_event_memo_status_start", table_name="event_memo_items")
    op.drop_index("ix_event_memo_scope_status_start", table_name="event_memo_items")
    op.drop_index("ix_event_memo_items_updated_by_user_id", table_name="event_memo_items")
    op.drop_index("ix_event_memo_items_created_by_user_id", table_name="event_memo_items")
    op.drop_index("ix_event_memo_items_starts_at", table_name="event_memo_items")
    op.drop_index("ix_event_memo_items_status", table_name="event_memo_items")
    op.drop_index("ix_event_memo_items_scope", table_name="event_memo_items")
    op.drop_table("event_memo_items")

