"""add api settings table

Revision ID: 20260211_add_api_settings
Revises: 20260211_add_source_slug
Create Date: 2026-02-11
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260211_add_api_settings"
down_revision = "20260211_add_source_slug"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "api_settings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("key", sa.String(length=100), nullable=False, unique=True),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_secret", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_api_settings_key", "api_settings", ["key"])


def downgrade():
    op.drop_index("ix_api_settings_key", table_name="api_settings")
    op.drop_table("api_settings")
