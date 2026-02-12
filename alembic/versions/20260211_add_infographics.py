"""add infographics table

Revision ID: 20260211_add_infographics
Revises: 20260211_add_image_prompts
Create Date: 2026-02-11
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260211_add_infographics"
down_revision = "20260211_add_image_prompts"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "infographics",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("article_id", sa.Integer(), nullable=True),
        sa.Column("data_json", sa.Text(), nullable=False),
        sa.Column("prompt_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", sa.String(length=100), nullable=True),
    )
    op.create_index("ix_infographics_article_id", "infographics", ["article_id"])


def downgrade():
    op.drop_index("ix_infographics_article_id", table_name="infographics")
    op.drop_table("infographics")
