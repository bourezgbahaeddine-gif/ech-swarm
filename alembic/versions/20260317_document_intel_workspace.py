"""Add Document Intel workspace tables.

Revision ID: 20260317_document_intel_workspace
Revises: 20260317_memory_context_upgrade
Create Date: 2026-03-17
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260317_document_intel_workspace"
down_revision = "20260317_memory_context_upgrade"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_intel_documents",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=True),
        sa.Column("parser_used", sa.String(length=64), nullable=False),
        sa.Column("language_hint", sa.String(length=16), nullable=False, server_default="ar"),
        sa.Column("detected_language", sa.String(length=16), nullable=False, server_default="unknown"),
        sa.Column("document_type", sa.String(length=64), nullable=False, server_default="report"),
        sa.Column("document_summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("stats", sa.JSON(), nullable=False),
        sa.Column("headings", sa.JSON(), nullable=False),
        sa.Column("news_candidates", sa.JSON(), nullable=False),
        sa.Column("entities", sa.JSON(), nullable=False),
        sa.Column("story_angles", sa.JSON(), nullable=False),
        sa.Column("data_points", sa.JSON(), nullable=False),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("preview_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("source_job_id", sa.String(length=64), nullable=True),
        sa.Column("uploaded_by_user_id", sa.Integer(), nullable=True),
        sa.Column("uploaded_by_username", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["uploaded_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_document_intel_documents_filename", "document_intel_documents", ["filename"])
    op.create_index("ix_document_intel_documents_document_type", "document_intel_documents", ["document_type"])
    op.create_index("ix_document_intel_documents_source_job_id", "document_intel_documents", ["source_job_id"])
    op.create_index("ix_document_intel_documents_uploaded_by_user_id", "document_intel_documents", ["uploaded_by_user_id"])
    op.create_index("ix_document_intel_documents_created_at", "document_intel_documents", ["created_at"])
    op.create_index("ix_document_intel_documents_updated_at", "document_intel_documents", ["updated_at"])
    op.create_index("ix_document_intel_type_created", "document_intel_documents", ["document_type", "created_at"])

    op.create_table(
        "document_intel_claims",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("claim_type", sa.String(length=32), nullable=False, server_default="factual"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("risk_level", sa.String(length=16), nullable=False, server_default="medium"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["document_intel_documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_document_intel_claims_document_id", "document_intel_claims", ["document_id"])
    op.create_index("ix_document_intel_claims_claim_type", "document_intel_claims", ["claim_type"])
    op.create_index("ix_document_intel_claims_risk_level", "document_intel_claims", ["risk_level"])
    op.create_index("ix_document_intel_claims_created_at", "document_intel_claims", ["created_at"])
    op.create_index("ix_document_intel_claim_doc_rank", "document_intel_claims", ["document_id", "rank"])

    op.create_table(
        "document_intel_actions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("action_type", sa.String(length=48), nullable=False),
        sa.Column("target_type", sa.String(length=48), nullable=True),
        sa.Column("target_id", sa.String(length=64), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("actor_username", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["document_intel_documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_document_intel_actions_document_id", "document_intel_actions", ["document_id"])
    op.create_index("ix_document_intel_actions_action_type", "document_intel_actions", ["action_type"])
    op.create_index("ix_document_intel_actions_actor_user_id", "document_intel_actions", ["actor_user_id"])
    op.create_index("ix_document_intel_actions_created_at", "document_intel_actions", ["created_at"])
    op.create_index("ix_document_intel_action_doc_created", "document_intel_actions", ["document_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_document_intel_action_doc_created", table_name="document_intel_actions")
    op.drop_index("ix_document_intel_actions_created_at", table_name="document_intel_actions")
    op.drop_index("ix_document_intel_actions_actor_user_id", table_name="document_intel_actions")
    op.drop_index("ix_document_intel_actions_action_type", table_name="document_intel_actions")
    op.drop_index("ix_document_intel_actions_document_id", table_name="document_intel_actions")
    op.drop_table("document_intel_actions")

    op.drop_index("ix_document_intel_claim_doc_rank", table_name="document_intel_claims")
    op.drop_index("ix_document_intel_claims_created_at", table_name="document_intel_claims")
    op.drop_index("ix_document_intel_claims_risk_level", table_name="document_intel_claims")
    op.drop_index("ix_document_intel_claims_claim_type", table_name="document_intel_claims")
    op.drop_index("ix_document_intel_claims_document_id", table_name="document_intel_claims")
    op.drop_table("document_intel_claims")

    op.drop_index("ix_document_intel_type_created", table_name="document_intel_documents")
    op.drop_index("ix_document_intel_documents_updated_at", table_name="document_intel_documents")
    op.drop_index("ix_document_intel_documents_created_at", table_name="document_intel_documents")
    op.drop_index("ix_document_intel_documents_uploaded_by_user_id", table_name="document_intel_documents")
    op.drop_index("ix_document_intel_documents_source_job_id", table_name="document_intel_documents")
    op.drop_index("ix_document_intel_documents_document_type", table_name="document_intel_documents")
    op.drop_index("ix_document_intel_documents_filename", table_name="document_intel_documents")
    op.drop_table("document_intel_documents")
