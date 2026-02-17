"""enforce single cluster membership per article

Revision ID: 20260217_single_cluster_member
Revises: 20260216_fingerprints_relations
Create Date: 2026-02-17 12:10:00
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "20260217_single_cluster_member"
down_revision = "20260216_fingerprints_relations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Keep one row per article_id (largest cluster first, then best score).
    op.execute(
        """
        WITH cluster_sizes AS (
            SELECT cluster_id, COUNT(*)::int AS members
            FROM story_cluster_members
            GROUP BY cluster_id
        ),
        ranked AS (
            SELECT
                scm.id,
                ROW_NUMBER() OVER (
                    PARTITION BY scm.article_id
                    ORDER BY cs.members DESC, scm.score DESC, scm.id ASC
                ) AS rn
            FROM story_cluster_members scm
            JOIN cluster_sizes cs ON cs.cluster_id = scm.cluster_id
        )
        DELETE FROM story_cluster_members scm
        USING ranked r
        WHERE scm.id = r.id
          AND r.rn > 1;
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
          IF NOT EXISTS (
            SELECT 1
            FROM pg_constraint
            WHERE conname = 'uq_story_cluster_member_article'
          ) THEN
            ALTER TABLE story_cluster_members
              ADD CONSTRAINT uq_story_cluster_member_article UNIQUE (article_id);
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
            WHERE conname = 'uq_story_cluster_member_article'
          ) THEN
            ALTER TABLE story_cluster_members
              DROP CONSTRAINT uq_story_cluster_member_article;
          END IF;
        END $$;
        """
    )
