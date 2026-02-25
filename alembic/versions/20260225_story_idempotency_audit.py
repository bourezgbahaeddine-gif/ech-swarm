"""add stories, task idempotency keys, and action audit logs

Revision ID: 20260225_story_idempotency_audit
Revises: 20260222_m10_link_index_metadata
Create Date: 2026-02-25 18:10:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260225_story_idempotency_audit"
down_revision = "20260222_m10_link_index_metadata"
branch_labels = None
depends_on = None


def upgrade() -> None:
    story_status = postgresql.ENUM("open", "monitoring", "closed", "archived", name="story_status")
    story_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "stories",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("story_key", sa.String(length=40), nullable=False),
        sa.Column("title", sa.String(length=1024), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("category", sa.String(length=80), nullable=True),
        sa.Column("geography", sa.String(length=24), nullable=True),
        sa.Column("status", sa.Enum("open", "monitoring", "closed", "archived", name="story_status", create_type=False), nullable=False, server_default="open"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("created_by", sa.String(length=128), nullable=True),
        sa.Column("updated_by", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("story_key", name="uq_stories_story_key"),
    )
    op.create_index("ix_stories_story_key", "stories", ["story_key"], unique=True)
    op.create_index("ix_stories_category", "stories", ["category"], unique=False)
    op.create_index("ix_stories_geography", "stories", ["geography"], unique=False)
    op.create_index("ix_stories_created_at", "stories", ["created_at"], unique=False)
    op.create_index("ix_stories_updated_at", "stories", ["updated_at"], unique=False)

    op.create_table(
        "story_items",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("story_id", sa.Integer(), sa.ForeignKey("stories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("article_id", sa.Integer(), sa.ForeignKey("articles.id", ondelete="SET NULL"), nullable=True),
        sa.Column("draft_id", sa.Integer(), sa.ForeignKey("editorial_drafts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("link_type", sa.String(length=16), nullable=False, server_default="article"),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("story_id", "article_id", name="uq_story_item_story_article"),
        sa.UniqueConstraint("story_id", "draft_id", name="uq_story_item_story_draft"),
    )
    op.create_index("ix_story_items_story_id", "story_items", ["story_id"], unique=False)
    op.create_index("ix_story_items_article_id", "story_items", ["article_id"], unique=False)
    op.create_index("ix_story_items_draft_id", "story_items", ["draft_id"], unique=False)
    op.create_index("ix_story_items_story_link_type", "story_items", ["story_id", "link_type"], unique=False)

    op.create_table(
        "task_idempotency_keys",
        sa.Column("idempotency_key", sa.String(length=190), primary_key=True),
        sa.Column("task_name", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="running"),
        sa.Column("first_job_id", sa.String(length=64), nullable=True),
        sa.Column("last_job_id", sa.String(length=64), nullable=True),
        sa.Column("result_json", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_task_idempotency_task_name", "task_idempotency_keys", ["task_name"], unique=False)
    op.create_index("ix_task_idempotency_status", "task_idempotency_keys", ["status"], unique=False)
    op.create_index("ix_task_idempotency_task_status", "task_idempotency_keys", ["task_name", "status"], unique=False)
    op.create_index("ix_task_idempotency_first_job_id", "task_idempotency_keys", ["first_job_id"], unique=False)
    op.create_index("ix_task_idempotency_last_job_id", "task_idempotency_keys", ["last_job_id"], unique=False)
    op.create_index("ix_task_idempotency_created_at", "task_idempotency_keys", ["created_at"], unique=False)
    op.create_index("ix_task_idempotency_updated_at", "task_idempotency_keys", ["updated_at"], unique=False)

    op.create_table(
        "action_audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("entity_type", sa.String(length=80), nullable=False),
        sa.Column("entity_id", sa.String(length=120), nullable=True),
        sa.Column("from_state", sa.String(length=64), nullable=True),
        sa.Column("to_state", sa.String(length=64), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("details_json", sa.JSON(), nullable=True),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("actor_username", sa.String(length=100), nullable=True),
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_action_audit_action", "action_audit_logs", ["action"], unique=False)
    op.create_index("ix_action_audit_entity_type", "action_audit_logs", ["entity_type"], unique=False)
    op.create_index("ix_action_audit_entity_id", "action_audit_logs", ["entity_id"], unique=False)
    op.create_index("ix_action_audit_actor_user_id", "action_audit_logs", ["actor_user_id"], unique=False)
    op.create_index("ix_action_audit_actor_username", "action_audit_logs", ["actor_username"], unique=False)
    op.create_index("ix_action_audit_correlation_id", "action_audit_logs", ["correlation_id"], unique=False)
    op.create_index("ix_action_audit_request_id", "action_audit_logs", ["request_id"], unique=False)
    op.create_index("ix_action_audit_created_at", "action_audit_logs", ["created_at"], unique=False)
    op.create_index("ix_action_audit_entity_created", "action_audit_logs", ["entity_type", "entity_id", "created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_action_audit_entity_created", table_name="action_audit_logs")
    op.drop_index("ix_action_audit_created_at", table_name="action_audit_logs")
    op.drop_index("ix_action_audit_request_id", table_name="action_audit_logs")
    op.drop_index("ix_action_audit_correlation_id", table_name="action_audit_logs")
    op.drop_index("ix_action_audit_actor_username", table_name="action_audit_logs")
    op.drop_index("ix_action_audit_actor_user_id", table_name="action_audit_logs")
    op.drop_index("ix_action_audit_entity_id", table_name="action_audit_logs")
    op.drop_index("ix_action_audit_entity_type", table_name="action_audit_logs")
    op.drop_index("ix_action_audit_action", table_name="action_audit_logs")
    op.drop_table("action_audit_logs")

    op.drop_index("ix_task_idempotency_updated_at", table_name="task_idempotency_keys")
    op.drop_index("ix_task_idempotency_created_at", table_name="task_idempotency_keys")
    op.drop_index("ix_task_idempotency_last_job_id", table_name="task_idempotency_keys")
    op.drop_index("ix_task_idempotency_first_job_id", table_name="task_idempotency_keys")
    op.drop_index("ix_task_idempotency_task_status", table_name="task_idempotency_keys")
    op.drop_index("ix_task_idempotency_status", table_name="task_idempotency_keys")
    op.drop_index("ix_task_idempotency_task_name", table_name="task_idempotency_keys")
    op.drop_table("task_idempotency_keys")

    op.drop_index("ix_story_items_story_link_type", table_name="story_items")
    op.drop_index("ix_story_items_draft_id", table_name="story_items")
    op.drop_index("ix_story_items_article_id", table_name="story_items")
    op.drop_index("ix_story_items_story_id", table_name="story_items")
    op.drop_table("story_items")

    op.drop_index("ix_stories_updated_at", table_name="stories")
    op.drop_index("ix_stories_created_at", table_name="stories")
    op.drop_index("ix_stories_geography", table_name="stories")
    op.drop_index("ix_stories_category", table_name="stories")
    op.drop_index("ix_stories_story_key", table_name="stories")
    op.drop_table("stories")

    story_status = postgresql.ENUM("open", "monitoring", "closed", "archived", name="story_status")
    story_status.drop(op.get_bind(), checkfirst=True)

