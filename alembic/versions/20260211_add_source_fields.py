"""add source fields for rss and scraper

Revision ID: 20260211_add_source_fields
Revises: 20260211_add_min_indexes
Create Date: 2026-02-11
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260211_add_source_fields"
down_revision = "20260211_add_min_indexes"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("sources", sa.Column("method", sa.String(length=20), server_default="rss", nullable=False))
    op.add_column("sources", sa.Column("rss_url", sa.String(length=1024), nullable=True))
    op.add_column("sources", sa.Column("languages", sa.String(length=50), nullable=True))
    op.add_column("sources", sa.Column("region", sa.String(length=50), nullable=True))
    op.add_column("sources", sa.Column("source_type", sa.String(length=50), nullable=True))
    op.add_column("sources", sa.Column("description", sa.Text(), nullable=True))
    op.add_column("sources", sa.Column("credibility", sa.String(length=20), server_default="medium", nullable=False))


def downgrade():
    op.drop_column("sources", "credibility")
    op.drop_column("sources", "description")
    op.drop_column("sources", "source_type")
    op.drop_column("sources", "region")
    op.drop_column("sources", "languages")
    op.drop_column("sources", "rss_url")
    op.drop_column("sources", "method")
