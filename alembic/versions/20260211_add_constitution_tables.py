"""add constitution tables

Revision ID: 20260211_add_constitution_tables
Revises: 20260211_add_settings_audit
Create Date: 2026-02-11
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260211_add_constitution_tables"
down_revision = "20260211_add_settings_audit"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "constitution_meta",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("version", sa.String(length=50), nullable=False),
        sa.Column("file_url", sa.String(length=255), nullable=False, server_default="/Constitution.docx"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_constitution_meta_version", "constitution_meta", ["version"])
    op.create_index("ix_constitution_meta_active", "constitution_meta", ["is_active"])

    op.create_table(
        "constitution_ack",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.String(length=50), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
    )
    op.create_index("ix_constitution_ack_user_version", "constitution_ack", ["user_id", "version"])
    op.create_index("ix_constitution_ack_user_id", "constitution_ack", ["user_id"])

    # Seed initial constitution version
    op.execute(
        "INSERT INTO constitution_meta (version, file_url, is_active, updated_at) "
        "VALUES ('v1', '/Constitution.docx', true, NOW())"
    )


def downgrade():
    op.drop_index("ix_constitution_ack_user_id", table_name="constitution_ack")
    op.drop_index("ix_constitution_ack_user_version", table_name="constitution_ack")
    op.drop_table("constitution_ack")
    op.drop_index("ix_constitution_meta_active", table_name="constitution_meta")
    op.drop_index("ix_constitution_meta_version", table_name="constitution_meta")
    op.drop_table("constitution_meta")
