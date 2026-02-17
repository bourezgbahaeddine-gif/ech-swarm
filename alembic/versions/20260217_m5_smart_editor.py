"""m5 smart editor schema updates

Revision ID: 20260217_m5_smart_editor
Revises: 20260217_newsstatus_case_fix
Create Date: 2026-02-17 16:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260217_m5_smart_editor"
down_revision = "20260217_newsstatus_case_fix"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("editorial_drafts")}

    if "parent_draft_id" not in cols:
        op.add_column("editorial_drafts", sa.Column("parent_draft_id", sa.Integer(), nullable=True))
        op.create_foreign_key(
            "fk_editorial_drafts_parent_draft",
            "editorial_drafts",
            "editorial_drafts",
            ["parent_draft_id"],
            ["id"],
        )

    if "change_origin" not in cols:
        op.add_column(
            "editorial_drafts",
            sa.Column("change_origin", sa.String(length=40), nullable=True, server_default="manual"),
        )
        op.execute("UPDATE editorial_drafts SET change_origin = 'manual' WHERE change_origin IS NULL")
        op.alter_column("editorial_drafts", "change_origin", nullable=False, server_default=None)

    # Ensure work_id+version is unique for deterministic version history.
    op.execute(
        """
        DELETE FROM editorial_drafts d
        USING editorial_drafts x
        WHERE d.work_id = x.work_id
          AND d.version = x.version
          AND d.id < x.id;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
          IF NOT EXISTS (
            SELECT 1
            FROM pg_constraint
            WHERE conname = 'uq_draft_work_version'
          ) THEN
            ALTER TABLE editorial_drafts
              ADD CONSTRAINT uq_draft_work_version UNIQUE (work_id, version);
          END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (
            SELECT 1
            FROM pg_constraint
            WHERE conname = 'uq_draft_work_version'
          ) THEN
            ALTER TABLE editorial_drafts
              DROP CONSTRAINT uq_draft_work_version;
          END IF;
        END $$;
        """
    )

    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("editorial_drafts")}

    if "change_origin" in cols:
        op.drop_column("editorial_drafts", "change_origin")

    if "parent_draft_id" in cols:
        op.drop_constraint("fk_editorial_drafts_parent_draft", "editorial_drafts", type_="foreignkey")
        op.drop_column("editorial_drafts", "parent_draft_id")

