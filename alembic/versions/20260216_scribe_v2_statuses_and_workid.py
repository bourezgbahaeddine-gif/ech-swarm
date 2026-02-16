"""scribe v2 statuses and work_id versioning

Revision ID: 20260216_scribe_v2
Revises: 20260214_add_editorial_drafts
Create Date: 2026-02-16 12:15:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260216_scribe_v2"
down_revision = "20260214_add_editorial_drafts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE newsstatus ADD VALUE IF NOT EXISTS 'approved_handoff'")
    op.execute("ALTER TYPE newsstatus ADD VALUE IF NOT EXISTS 'draft_generated'")

    # editorial_drafts.work_id must support multiple versions under same work_id.
    op.execute(
        """
        DO $$
        DECLARE
            _cname text;
        BEGIN
            SELECT conname INTO _cname
            FROM pg_constraint
            WHERE conrelid = 'editorial_drafts'::regclass
              AND contype = 'u'
              AND conkey = ARRAY[
                (SELECT attnum FROM pg_attribute WHERE attrelid='editorial_drafts'::regclass AND attname='work_id')
              ];
            IF _cname IS NOT NULL THEN
                EXECUTE format('ALTER TABLE editorial_drafts DROP CONSTRAINT %I', _cname);
            END IF;
        END $$;
        """
    )
    op.drop_index("ix_editorial_drafts_work_id", table_name="editorial_drafts")
    op.create_index("ix_editorial_drafts_work_id", "editorial_drafts", ["work_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_editorial_drafts_work_id", table_name="editorial_drafts")
    op.create_index("ix_editorial_drafts_work_id", "editorial_drafts", ["work_id"], unique=True)
    # Downgrade does not remove enum values from PostgreSQL type safely.
