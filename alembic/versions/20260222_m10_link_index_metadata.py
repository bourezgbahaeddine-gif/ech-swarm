"""add metadata_json to link_index_items

Revision ID: 20260222_m10_link_index_metadata
Revises: 20260222_m10_job_queue
Create Date: 2026-02-22 13:30:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260222_m10_link_index_metadata"
down_revision = "20260222_m10_job_queue"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "link_index_items",
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
    )


def downgrade() -> None:
    op.drop_column("link_index_items", "metadata_json")

