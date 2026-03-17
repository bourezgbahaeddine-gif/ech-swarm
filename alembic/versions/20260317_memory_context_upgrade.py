"""expand project memory with subtype and freshness

Revision ID: 20260317_memory_context_upgrade
Revises: 20260312_digital_desk_phase2_3
Create Date: 2026-03-17 18:10:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260317_memory_context_upgrade"
down_revision = "20260312_digital_desk_phase2_3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("project_memory_items", sa.Column("memory_subtype", sa.String(length=48), nullable=True))
    op.add_column(
        "project_memory_items",
        sa.Column("freshness_status", sa.String(length=24), nullable=False, server_default="stable"),
    )
    op.add_column("project_memory_items", sa.Column("valid_until", sa.DateTime(), nullable=True))

    op.execute("UPDATE project_memory_items SET memory_subtype = 'general' WHERE memory_subtype IS NULL")
    op.alter_column("project_memory_items", "memory_subtype", existing_type=sa.String(length=48), nullable=True)

    op.create_index("ix_project_memory_items_memory_subtype", "project_memory_items", ["memory_subtype"], unique=False)
    op.create_index("ix_project_memory_items_freshness_status", "project_memory_items", ["freshness_status"], unique=False)
    op.create_index(
        "ix_project_memory_subtype_freshness",
        "project_memory_items",
        ["memory_subtype", "freshness_status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_project_memory_subtype_freshness", table_name="project_memory_items")
    op.drop_index("ix_project_memory_items_freshness_status", table_name="project_memory_items")
    op.drop_index("ix_project_memory_items_memory_subtype", table_name="project_memory_items")
    op.drop_column("project_memory_items", "valid_until")
    op.drop_column("project_memory_items", "freshness_status")
    op.drop_column("project_memory_items", "memory_subtype")
