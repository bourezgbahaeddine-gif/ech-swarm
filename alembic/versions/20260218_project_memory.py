"""add project memory tables

Revision ID: 20260218_project_memory
Revises: 20260218_add_user_activity_logs
Create Date: 2026-02-18 19:40:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260218_project_memory"
down_revision = "20260218_add_user_activity_logs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_memory_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("memory_type", sa.String(length=24), nullable=False, server_default="operational"),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("source_type", sa.String(length=64), nullable=True),
        sa.Column("source_ref", sa.String(length=512), nullable=True),
        sa.Column("article_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="active"),
        sa.Column("importance", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_by_username", sa.String(length=64), nullable=True),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_username", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["article_id"], ["articles.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_project_memory_items_memory_type", "project_memory_items", ["memory_type"], unique=False)
    op.create_index("ix_project_memory_items_status", "project_memory_items", ["status"], unique=False)
    op.create_index("ix_project_memory_items_article_id", "project_memory_items", ["article_id"], unique=False)
    op.create_index("ix_project_memory_items_created_by_user_id", "project_memory_items", ["created_by_user_id"], unique=False)
    op.create_index("ix_project_memory_items_updated_by_user_id", "project_memory_items", ["updated_by_user_id"], unique=False)
    op.create_index(
        "ix_project_memory_type_status_updated",
        "project_memory_items",
        ["memory_type", "status", "updated_at"],
        unique=False,
    )

    op.create_table(
        "project_memory_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("memory_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("actor_username", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["memory_id"], ["project_memory_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_project_memory_events_memory_id", "project_memory_events", ["memory_id"], unique=False)
    op.create_index("ix_project_memory_events_event_type", "project_memory_events", ["event_type"], unique=False)
    op.create_index("ix_project_memory_events_actor_user_id", "project_memory_events", ["actor_user_id"], unique=False)
    op.create_index(
        "ix_project_memory_events_memory_created",
        "project_memory_events",
        ["memory_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_project_memory_events_memory_created", table_name="project_memory_events")
    op.drop_index("ix_project_memory_events_actor_user_id", table_name="project_memory_events")
    op.drop_index("ix_project_memory_events_event_type", table_name="project_memory_events")
    op.drop_index("ix_project_memory_events_memory_id", table_name="project_memory_events")
    op.drop_table("project_memory_events")

    op.drop_index("ix_project_memory_type_status_updated", table_name="project_memory_items")
    op.drop_index("ix_project_memory_items_updated_by_user_id", table_name="project_memory_items")
    op.drop_index("ix_project_memory_items_created_by_user_id", table_name="project_memory_items")
    op.drop_index("ix_project_memory_items_article_id", table_name="project_memory_items")
    op.drop_index("ix_project_memory_items_status", table_name="project_memory_items")
    op.drop_index("ix_project_memory_items_memory_type", table_name="project_memory_items")
    op.drop_table("project_memory_items")
