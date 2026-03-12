"""digital desk phase 2-3

Revision ID: 20260312_digital_desk_phase2_3
Revises: 20260311_event_desk_phase3
Create Date: 2026-03-12 13:45:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260312_digital_desk_phase2_3"
down_revision = "20260311_event_desk_phase3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "social_tasks",
        sa.Column("story_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_social_tasks_story_id_stories",
        "social_tasks",
        "stories",
        ["story_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_social_tasks_story_id", "social_tasks", ["story_id"], unique=False)

    op.create_table(
        "social_post_versions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("post_id", sa.Integer(), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("version_type", sa.String(length=32), nullable=False, server_default=sa.text("'edited'")),
        sa.Column("content_text", sa.Text(), nullable=False),
        sa.Column("hashtags", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("media_urls", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_by_username", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["post_id"], ["social_posts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("post_id", "version_no", name="uq_social_post_versions_post_version"),
        sa.CheckConstraint("version_no >= 1", name="ck_social_post_versions_version_no"),
    )
    op.create_index("ix_social_post_versions_post_id", "social_post_versions", ["post_id"], unique=False)
    op.create_index(
        "ix_social_post_versions_post_created",
        "social_post_versions",
        ["post_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_social_post_versions_post_created", table_name="social_post_versions")
    op.drop_index("ix_social_post_versions_post_id", table_name="social_post_versions")
    op.drop_table("social_post_versions")

    op.drop_index("ix_social_tasks_story_id", table_name="social_tasks")
    op.drop_constraint("fk_social_tasks_story_id_stories", "social_tasks", type_="foreignkey")
    op.drop_column("social_tasks", "story_id")
