"""add user activity logs table

Revision ID: 20260218_add_user_activity_logs
Revises: 20260218_editorial_policy_gate_statuses
Create Date: 2026-02-18 17:30:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260218_add_user_activity_logs"
down_revision = "20260218_editorial_policy_gate_statuses"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_activity_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("actor_username", sa.String(length=50), nullable=True),
        sa.Column("target_user_id", sa.Integer(), nullable=True),
        sa.Column("target_username", sa.String(length=50), nullable=True),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["target_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_activity_logs_action", "user_activity_logs", ["action"], unique=False)
    op.create_index("ix_user_activity_logs_actor_username", "user_activity_logs", ["actor_username"], unique=False)
    op.create_index("ix_user_activity_logs_created_at", "user_activity_logs", ["created_at"], unique=False)
    op.create_index("ix_user_activity_logs_target_username", "user_activity_logs", ["target_username"], unique=False)
    op.create_index(
        "ix_user_activity_target_created_at",
        "user_activity_logs",
        ["target_user_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_user_activity_target_created_at", table_name="user_activity_logs")
    op.drop_index("ix_user_activity_logs_target_username", table_name="user_activity_logs")
    op.drop_index("ix_user_activity_logs_created_at", table_name="user_activity_logs")
    op.drop_index("ix_user_activity_logs_actor_username", table_name="user_activity_logs")
    op.drop_index("ix_user_activity_logs_action", table_name="user_activity_logs")
    op.drop_table("user_activity_logs")
