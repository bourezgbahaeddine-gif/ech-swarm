"""add digital team operations module

Revision ID: 20260301_digital_team_module
Revises: 20260301_event_memo_sprint1
Create Date: 2026-03-01 15:40:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260301_digital_team_module"
down_revision = "20260301_event_memo_sprint1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "digital_team_scopes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("can_manage_news", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("can_manage_tv", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("platforms", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_digital_team_scopes_user_id"),
    )
    op.create_index("ix_digital_team_scopes_user_id", "digital_team_scopes", ["user_id"], unique=True)

    op.create_table(
        "program_slots",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("channel", sa.String(length=16), nullable=False),
        sa.Column("program_title", sa.String(length=255), nullable=False),
        sa.Column("program_type", sa.String(length=64), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("day_of_week", sa.Integer(), nullable=True),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False, server_default=sa.text("60")),
        sa.Column("timezone", sa.String(length=64), nullable=False, server_default=sa.text("'Africa/Algiers'")),
        sa.Column("priority", sa.Integer(), nullable=False, server_default=sa.text("3")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("social_focus", sa.Text(), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("source_ref", sa.String(length=2048), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "channel",
            "program_title",
            "day_of_week",
            "start_time",
            name="uq_program_slot_channel_title_day_time",
        ),
        sa.CheckConstraint("channel IN ('news','tv')", name="ck_program_slots_channel"),
        sa.CheckConstraint("(day_of_week IS NULL) OR (day_of_week >= 0 AND day_of_week <= 6)", name="ck_program_slots_day_of_week"),
        sa.CheckConstraint("duration_minutes >= 5 AND duration_minutes <= 480", name="ck_program_slots_duration"),
        sa.CheckConstraint("priority >= 1 AND priority <= 5", name="ck_program_slots_priority"),
    )
    op.create_index("ix_program_slots_channel", "program_slots", ["channel"], unique=False)
    op.create_index("ix_program_slots_day_of_week", "program_slots", ["day_of_week"], unique=False)
    op.create_index("ix_program_slots_start_time", "program_slots", ["start_time"], unique=False)
    op.create_index("ix_program_slots_is_active", "program_slots", ["is_active"], unique=False)
    op.create_index(
        "ix_program_slots_channel_active_time",
        "program_slots",
        ["channel", "is_active", "day_of_week", "start_time"],
        unique=False,
    )

    op.create_table(
        "social_tasks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("channel", sa.String(length=16), nullable=False),
        sa.Column("platform", sa.String(length=32), nullable=False, server_default=sa.text("'all'")),
        sa.Column("task_type", sa.String(length=32), nullable=False, server_default=sa.text("'manual'")),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("brief", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False, server_default=sa.text("'todo'")),
        sa.Column("priority", sa.Integer(), nullable=False, server_default=sa.text("3")),
        sa.Column("due_at", sa.DateTime(), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("dedupe_key", sa.String(length=255), nullable=True),
        sa.Column("program_slot_id", sa.Integer(), nullable=True),
        sa.Column("event_id", sa.Integer(), nullable=True),
        sa.Column("article_id", sa.Integer(), nullable=True),
        sa.Column("owner_user_id", sa.Integer(), nullable=True),
        sa.Column("owner_username", sa.String(length=64), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_by_username", sa.String(length=64), nullable=True),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_username", sa.String(length=64), nullable=True),
        sa.Column("published_posts_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("last_published_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["article_id"], ["articles.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["event_id"], ["event_memo_items.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["program_slot_id"], ["program_slots.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dedupe_key", name="uq_social_tasks_dedupe_key"),
        sa.CheckConstraint("channel IN ('news','tv')", name="ck_social_tasks_channel"),
        sa.CheckConstraint("status IN ('todo','in_progress','review','done','cancelled')", name="ck_social_tasks_status"),
        sa.CheckConstraint("priority >= 1 AND priority <= 5", name="ck_social_tasks_priority"),
    )
    op.create_index("ix_social_tasks_channel", "social_tasks", ["channel"], unique=False)
    op.create_index("ix_social_tasks_platform", "social_tasks", ["platform"], unique=False)
    op.create_index("ix_social_tasks_task_type", "social_tasks", ["task_type"], unique=False)
    op.create_index("ix_social_tasks_status", "social_tasks", ["status"], unique=False)
    op.create_index("ix_social_tasks_due_at", "social_tasks", ["due_at"], unique=False)
    op.create_index("ix_social_tasks_dedupe_key", "social_tasks", ["dedupe_key"], unique=True)
    op.create_index("ix_social_tasks_program_slot_id", "social_tasks", ["program_slot_id"], unique=False)
    op.create_index("ix_social_tasks_event_id", "social_tasks", ["event_id"], unique=False)
    op.create_index("ix_social_tasks_article_id", "social_tasks", ["article_id"], unique=False)
    op.create_index("ix_social_tasks_owner_user_id", "social_tasks", ["owner_user_id"], unique=False)
    op.create_index("ix_social_tasks_status_due", "social_tasks", ["status", "due_at"], unique=False)
    op.create_index("ix_social_tasks_channel_status_due", "social_tasks", ["channel", "status", "due_at"], unique=False)
    op.create_index("ix_social_tasks_owner_status_due", "social_tasks", ["owner_user_id", "status", "due_at"], unique=False)

    op.create_table(
        "social_posts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("channel", sa.String(length=16), nullable=False),
        sa.Column("platform", sa.String(length=32), nullable=False),
        sa.Column("content_text", sa.Text(), nullable=False),
        sa.Column("hashtags", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("media_urls", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("status", sa.String(length=24), nullable=False, server_default=sa.text("'draft'")),
        sa.Column("scheduled_at", sa.DateTime(), nullable=True),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("published_url", sa.String(length=2048), nullable=True),
        sa.Column("external_post_id", sa.String(length=128), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_by_username", sa.String(length=64), nullable=True),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_username", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["task_id"], ["social_tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("channel IN ('news','tv')", name="ck_social_posts_channel"),
        sa.CheckConstraint("status IN ('draft','ready','approved','scheduled','published','failed')", name="ck_social_posts_status"),
    )
    op.create_index("ix_social_posts_task_id", "social_posts", ["task_id"], unique=False)
    op.create_index("ix_social_posts_channel", "social_posts", ["channel"], unique=False)
    op.create_index("ix_social_posts_platform", "social_posts", ["platform"], unique=False)
    op.create_index("ix_social_posts_status", "social_posts", ["status"], unique=False)
    op.create_index("ix_social_posts_scheduled_at", "social_posts", ["scheduled_at"], unique=False)
    op.create_index("ix_social_posts_published_at", "social_posts", ["published_at"], unique=False)
    op.create_index("ix_social_posts_task_status", "social_posts", ["task_id", "status"], unique=False)
    op.create_index(
        "ix_social_posts_platform_status_scheduled",
        "social_posts",
        ["platform", "status", "scheduled_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_social_posts_platform_status_scheduled", table_name="social_posts")
    op.drop_index("ix_social_posts_task_status", table_name="social_posts")
    op.drop_index("ix_social_posts_published_at", table_name="social_posts")
    op.drop_index("ix_social_posts_scheduled_at", table_name="social_posts")
    op.drop_index("ix_social_posts_status", table_name="social_posts")
    op.drop_index("ix_social_posts_platform", table_name="social_posts")
    op.drop_index("ix_social_posts_channel", table_name="social_posts")
    op.drop_index("ix_social_posts_task_id", table_name="social_posts")
    op.drop_table("social_posts")

    op.drop_index("ix_social_tasks_owner_status_due", table_name="social_tasks")
    op.drop_index("ix_social_tasks_channel_status_due", table_name="social_tasks")
    op.drop_index("ix_social_tasks_status_due", table_name="social_tasks")
    op.drop_index("ix_social_tasks_owner_user_id", table_name="social_tasks")
    op.drop_index("ix_social_tasks_article_id", table_name="social_tasks")
    op.drop_index("ix_social_tasks_event_id", table_name="social_tasks")
    op.drop_index("ix_social_tasks_program_slot_id", table_name="social_tasks")
    op.drop_index("ix_social_tasks_dedupe_key", table_name="social_tasks")
    op.drop_index("ix_social_tasks_due_at", table_name="social_tasks")
    op.drop_index("ix_social_tasks_status", table_name="social_tasks")
    op.drop_index("ix_social_tasks_task_type", table_name="social_tasks")
    op.drop_index("ix_social_tasks_platform", table_name="social_tasks")
    op.drop_index("ix_social_tasks_channel", table_name="social_tasks")
    op.drop_table("social_tasks")

    op.drop_index("ix_program_slots_channel_active_time", table_name="program_slots")
    op.drop_index("ix_program_slots_is_active", table_name="program_slots")
    op.drop_index("ix_program_slots_start_time", table_name="program_slots")
    op.drop_index("ix_program_slots_day_of_week", table_name="program_slots")
    op.drop_index("ix_program_slots_channel", table_name="program_slots")
    op.drop_table("program_slots")

    op.drop_index("ix_digital_team_scopes_user_id", table_name="digital_team_scopes")
    op.drop_table("digital_team_scopes")
