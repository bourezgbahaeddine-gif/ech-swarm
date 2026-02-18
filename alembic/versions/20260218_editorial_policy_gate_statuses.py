"""add editorial policy gate statuses to newsstatus enum

Revision ID: 20260218_policy_gate_statuses
Revises: 20260217_m5_smart_editor
Create Date: 2026-02-18 10:00:00
"""

from alembic import op


revision = "20260218_policy_gate_statuses"
down_revision = "20260217_m5_smart_editor"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE newsstatus ADD VALUE IF NOT EXISTS 'ready_for_chief_approval'")
    op.execute("ALTER TYPE newsstatus ADD VALUE IF NOT EXISTS 'approval_request_with_reservations'")
    op.execute("ALTER TYPE newsstatus ADD VALUE IF NOT EXISTS 'ready_for_manual_publish'")


def downgrade() -> None:
    # Postgres enum value deletion is not safe in downgrade without type recreation.
    pass
