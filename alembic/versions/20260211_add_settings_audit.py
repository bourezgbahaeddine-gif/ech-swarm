"""add settings audit log

Revision ID: 20260211_add_settings_audit
Revises: 20260211_add_api_settings
Create Date: 2026-02-11
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260211_add_settings_audit"
down_revision = "20260211_add_api_settings"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "settings_audit",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("action", sa.String(length=30), nullable=False),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("actor", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_settings_audit_key", "settings_audit", ["key"])
    op.create_index("ix_settings_audit_created_at", "settings_audit", ["created_at"])


def downgrade():
    op.drop_index("ix_settings_audit_created_at", table_name="settings_audit")
    op.drop_index("ix_settings_audit_key", table_name="settings_audit")
    op.drop_table("settings_audit")
