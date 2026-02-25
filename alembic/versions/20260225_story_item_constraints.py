"""enforce story item integrity constraints

Revision ID: 20260225_story_item_constraints
Revises: 20260225_story_idempotency_audit
Create Date: 2026-02-25 22:15:00
"""

from alembic import op


revision = "20260225_story_item_constraints"
down_revision = "20260225_story_idempotency_audit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Normalize potentially inconsistent legacy rows before adding hard constraints.
    op.execute(
        """
        UPDATE story_items
        SET draft_id = NULL
        WHERE link_type = 'article'
          AND article_id IS NOT NULL
          AND draft_id IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE story_items
        SET article_id = NULL
        WHERE link_type = 'draft'
          AND draft_id IS NOT NULL
          AND article_id IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE story_items
        SET link_type = 'article'
        WHERE article_id IS NOT NULL
          AND draft_id IS NULL
          AND link_type <> 'article'
        """
    )
    op.execute(
        """
        UPDATE story_items
        SET link_type = 'draft'
        WHERE draft_id IS NOT NULL
          AND article_id IS NULL
          AND link_type <> 'draft'
        """
    )
    op.execute(
        """
        DELETE FROM story_items
        WHERE (article_id IS NULL AND draft_id IS NULL)
           OR (article_id IS NOT NULL AND draft_id IS NOT NULL)
        """
    )

    op.create_check_constraint(
        "ck_story_items_exactly_one_ref",
        "story_items",
        "((article_id IS NOT NULL AND draft_id IS NULL) OR (article_id IS NULL AND draft_id IS NOT NULL))",
    )
    op.create_check_constraint(
        "ck_story_items_link_type_match",
        "story_items",
        "((link_type = 'article' AND article_id IS NOT NULL AND draft_id IS NULL) "
        "OR (link_type = 'draft' AND draft_id IS NOT NULL AND article_id IS NULL))",
    )


def downgrade() -> None:
    op.drop_constraint("ck_story_items_link_type_match", "story_items", type_="check")
    op.drop_constraint("ck_story_items_exactly_one_ref", "story_items", type_="check")
