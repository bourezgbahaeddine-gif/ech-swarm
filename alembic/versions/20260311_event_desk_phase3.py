"""event desk phase 1-3 schema

Revision ID: 20260311_event_desk_phase3
Revises: 20260308_merge_archive_heads
Create Date: 2026-03-11 11:30:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260311_event_desk_phase3"
down_revision = "20260308_merge_archive_heads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "event_memo_items",
        sa.Column("playbook_key", sa.String(length=32), nullable=False, server_default="general"),
    )
    op.add_column(
        "event_memo_items",
        sa.Column("story_id", sa.Integer(), nullable=True),
    )

    op.create_foreign_key(
        "fk_event_memo_items_story_id_stories",
        "event_memo_items",
        "stories",
        ["story_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_event_memo_items_story_id", "event_memo_items", ["story_id"], unique=False)
    op.create_index(
        "ix_event_memo_story_status_start",
        "event_memo_items",
        ["story_id", "status", "starts_at"],
        unique=False,
    )
    op.alter_column("event_memo_items", "playbook_key", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_event_memo_story_status_start", table_name="event_memo_items")
    op.drop_index("ix_event_memo_items_story_id", table_name="event_memo_items")
    op.drop_constraint("fk_event_memo_items_story_id_stories", "event_memo_items", type_="foreignkey")
    op.drop_column("event_memo_items", "story_id")
    op.drop_column("event_memo_items", "playbook_key")
