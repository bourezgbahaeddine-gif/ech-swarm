"""fix newsstatus enum case for scribe v2 states

Revision ID: 20260217_newsstatus_case_fix
Revises: 20260217_quality_reports
Create Date: 2026-02-17 12:45:00
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "20260217_newsstatus_case_fix"
down_revision = "20260217_quality_reports"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SQLAlchemy Enum(NewsStatus) persists enum names (UPPER_CASE), not values.
    # Ensure those labels exist in PostgreSQL enum for new Scribe v2 states.
    op.execute("ALTER TYPE newsstatus ADD VALUE IF NOT EXISTS 'APPROVED_HANDOFF'")
    op.execute("ALTER TYPE newsstatus ADD VALUE IF NOT EXISTS 'DRAFT_GENERATED'")

    # Normalize old lowercase rows (if any) to uppercase labels expected by ORM.
    op.execute(
        """
        UPDATE articles
        SET status = 'APPROVED_HANDOFF'::newsstatus
        WHERE status::text = 'approved_handoff';
        """
    )
    op.execute(
        """
        UPDATE articles
        SET status = 'DRAFT_GENERATED'::newsstatus
        WHERE status::text = 'draft_generated';
        """
    )


def downgrade() -> None:
    # Enum label removal is unsafe in PostgreSQL and intentionally skipped.
    pass
