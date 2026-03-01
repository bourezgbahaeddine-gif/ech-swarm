"""extend events memo board for operations sprint 1

Revision ID: 20260301_event_memo_sprint1
Revises: 20260301_event_memo_board
Create Date: 2026-03-01 11:58:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260301_event_memo_sprint1"
down_revision = "20260301_event_memo_board"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "event_memo_items",
        sa.Column("readiness_status", sa.String(length=24), nullable=False, server_default="idea"),
    )
    op.add_column(
        "event_memo_items",
        sa.Column("checklist", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
    )
    op.add_column("event_memo_items", sa.Column("preparation_started_at", sa.DateTime(), nullable=True))
    op.add_column("event_memo_items", sa.Column("owner_user_id", sa.Integer(), nullable=True))
    op.add_column("event_memo_items", sa.Column("owner_username", sa.String(length=64), nullable=True))

    op.execute(
        """
        UPDATE event_memo_items
        SET readiness_status = CASE
            WHEN status = 'covered' THEN 'covered'
            WHEN status = 'monitoring' THEN 'prepared'
            ELSE 'idea'
        END
        """
    )

    op.create_check_constraint(
        "ck_event_memo_readiness_status",
        "event_memo_items",
        "readiness_status IN ('idea', 'assigned', 'prepared', 'ready', 'covered')",
    )
    op.create_foreign_key(
        "fk_event_memo_items_owner_user_id_users",
        "event_memo_items",
        "users",
        ["owner_user_id"],
        ["id"],
    )

    op.create_index("ix_event_memo_items_readiness_status", "event_memo_items", ["readiness_status"], unique=False)
    op.create_index("ix_event_memo_items_owner_user_id", "event_memo_items", ["owner_user_id"], unique=False)
    op.create_index(
        "ix_event_memo_owner_status_start",
        "event_memo_items",
        ["owner_user_id", "status", "starts_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_event_memo_owner_status_start", table_name="event_memo_items")
    op.drop_index("ix_event_memo_items_owner_user_id", table_name="event_memo_items")
    op.drop_index("ix_event_memo_items_readiness_status", table_name="event_memo_items")

    op.drop_constraint("fk_event_memo_items_owner_user_id_users", "event_memo_items", type_="foreignkey")
    op.drop_constraint("ck_event_memo_readiness_status", "event_memo_items", type_="check")

    op.drop_column("event_memo_items", "owner_username")
    op.drop_column("event_memo_items", "owner_user_id")
    op.drop_column("event_memo_items", "preparation_started_at")
    op.drop_column("event_memo_items", "checklist")
    op.drop_column("event_memo_items", "readiness_status")
