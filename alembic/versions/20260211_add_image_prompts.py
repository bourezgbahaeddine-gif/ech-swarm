"""add image prompts table

Revision ID: 20260211_add_image_prompts
Revises: 20260211_add_constitution_tables
Create Date: 2026-02-11
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260211_add_image_prompts"
down_revision = "20260211_add_constitution_tables"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "image_prompts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("article_id", sa.Integer(), nullable=True),
        sa.Column("prompt_text", sa.Text(), nullable=False),
        sa.Column("style", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", sa.String(length=100), nullable=True),
    )
    op.create_index("ix_image_prompts_article_id", "image_prompts", ["article_id"])


def downgrade():
    op.drop_index("ix_image_prompts_article_id", table_name="image_prompts")
    op.drop_table("image_prompts")
