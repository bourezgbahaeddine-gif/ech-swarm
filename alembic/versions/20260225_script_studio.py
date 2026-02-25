"""add script studio tables

Revision ID: 20260225_script_studio
Revises: 20260225_story_item_constraints
Create Date: 2026-02-25 23:15:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260225_script_studio"
down_revision = "20260225_story_item_constraints"
branch_labels = None
depends_on = None


def upgrade() -> None:
    script_project_type = postgresql.ENUM(
        "story_script",
        "video_script",
        "bulletin_daily",
        "bulletin_weekly",
        name="script_project_type",
        create_type=False,
    )
    script_project_status = postgresql.ENUM(
        "new",
        "generating",
        "ready_for_review",
        "approved",
        "rejected",
        "archived",
        name="script_project_status",
        create_type=False,
    )
    script_output_format = postgresql.ENUM(
        "markdown",
        "json",
        "srt",
        name="script_output_format",
        create_type=False,
    )
    script_project_type.create(op.get_bind(), checkfirst=True)
    script_project_status.create(op.get_bind(), checkfirst=True)
    script_output_format.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "script_projects",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("type", script_project_type, nullable=False),
        sa.Column("status", script_project_status, nullable=False, server_default="new"),
        sa.Column("story_id", sa.Integer(), sa.ForeignKey("stories.id", ondelete="SET NULL"), nullable=True),
        sa.Column("article_id", sa.Integer(), sa.ForeignKey("articles.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(length=1024), nullable=False),
        sa.Column("params_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_by", sa.String(length=128), nullable=True),
        sa.Column("updated_by", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "("
            "(type IN ('story_script','video_script') AND "
            " ((story_id IS NOT NULL AND article_id IS NULL) OR (story_id IS NULL AND article_id IS NOT NULL))) "
            "OR "
            "(type IN ('bulletin_daily','bulletin_weekly') AND story_id IS NULL AND article_id IS NULL)"
            ")",
            name="ck_script_projects_target_scope",
        ),
    )
    op.create_index("ix_script_projects_type", "script_projects", ["type"], unique=False)
    op.create_index("ix_script_projects_status", "script_projects", ["status"], unique=False)
    op.create_index("ix_script_projects_story_id", "script_projects", ["story_id"], unique=False)
    op.create_index("ix_script_projects_article_id", "script_projects", ["article_id"], unique=False)
    op.create_index("ix_script_projects_created_at", "script_projects", ["created_at"], unique=False)
    op.create_index("ix_script_projects_updated_at", "script_projects", ["updated_at"], unique=False)
    op.create_index("ix_script_projects_type_status", "script_projects", ["type", "status"], unique=False)

    op.create_table(
        "script_outputs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("script_id", sa.Integer(), sa.ForeignKey("script_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("content_json", sa.JSON(), nullable=True),
        sa.Column("content_text", sa.Text(), nullable=True),
        sa.Column("format", script_output_format, nullable=False, server_default="json"),
        sa.Column("quality_issues_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("script_id", "version", name="uq_script_output_script_version"),
    )
    op.create_index("ix_script_outputs_script_id", "script_outputs", ["script_id"], unique=False)
    op.create_index("ix_script_outputs_created_at", "script_outputs", ["created_at"], unique=False)
    op.create_index("ix_script_outputs_script_created", "script_outputs", ["script_id", "created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_script_outputs_script_created", table_name="script_outputs")
    op.drop_index("ix_script_outputs_created_at", table_name="script_outputs")
    op.drop_index("ix_script_outputs_script_id", table_name="script_outputs")
    op.drop_table("script_outputs")

    op.drop_index("ix_script_projects_type_status", table_name="script_projects")
    op.drop_index("ix_script_projects_updated_at", table_name="script_projects")
    op.drop_index("ix_script_projects_created_at", table_name="script_projects")
    op.drop_index("ix_script_projects_article_id", table_name="script_projects")
    op.drop_index("ix_script_projects_story_id", table_name="script_projects")
    op.drop_index("ix_script_projects_status", table_name="script_projects")
    op.drop_index("ix_script_projects_type", table_name="script_projects")
    op.drop_table("script_projects")

    script_output_format = postgresql.ENUM("markdown", "json", "srt", name="script_output_format", create_type=False)
    script_project_status = postgresql.ENUM(
        "new",
        "generating",
        "ready_for_review",
        "approved",
        "rejected",
        "archived",
        name="script_project_status",
        create_type=False,
    )
    script_project_type = postgresql.ENUM(
        "story_script",
        "video_script",
        "bulletin_daily",
        "bulletin_weekly",
        name="script_project_type",
        create_type=False,
    )

    script_output_format.drop(op.get_bind(), checkfirst=True)
    script_project_status.drop(op.get_bind(), checkfirst=True)
    script_project_type.drop(op.get_bind(), checkfirst=True)
