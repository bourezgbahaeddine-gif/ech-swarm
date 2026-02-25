"""add failed status to script project enum

Revision ID: 20260226_script_status_failed
Revises: 20260225_script_studio
Create Date: 2026-02-26 10:30:00
"""

from alembic import op


revision = "20260226_script_status_failed"
down_revision = "20260225_script_studio"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_enum e
                JOIN pg_type t ON t.oid = e.enumtypid
                WHERE t.typname = 'script_project_status'
                  AND e.enumlabel = 'failed'
            ) THEN
                ALTER TYPE script_project_status ADD VALUE 'failed';
            END IF;
        END$$;
        """
    )


def downgrade() -> None:
    # PostgreSQL enum values are not safely removable in-place.
    # Keep downgrade idempotent and non-destructive.
    pass

