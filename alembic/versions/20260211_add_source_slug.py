"""add source slug

Revision ID: 20260211_add_source_slug
Revises: 20260211_add_source_fields
Create Date: 2026-02-11
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260211_add_source_slug"
down_revision = "20260211_add_source_fields"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("sources", sa.Column("slug", sa.String(length=255), nullable=True))
    # Best-effort slug fill: lower + replace spaces with '-'
    op.execute("UPDATE sources SET slug = lower(replace(name, ' ', '-')) WHERE slug IS NULL")
    op.create_index(
        "ux_sources_slug",
        "sources",
        ["slug"],
        unique=True,
        postgresql_where=sa.text("slug IS NOT NULL"),
    )


def downgrade():
    op.drop_index("ux_sources_slug", table_name="sources")
    op.drop_column("sources", "slug")
