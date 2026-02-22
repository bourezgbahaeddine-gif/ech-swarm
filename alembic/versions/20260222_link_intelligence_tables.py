"""add link intelligence tables

Revision ID: 20260222_link_intelligence_tables
Revises: 20260221_competitor_xray_tables
Create Date: 2026-02-22 09:30:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260222_link_intelligence_tables"
down_revision = "20260221_competitor_xray_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "link_index_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("domain", sa.String(length=255), nullable=False),
        sa.Column("link_type", sa.String(length=16), nullable=False),
        sa.Column("title", sa.String(length=1024), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("category", sa.String(length=64), nullable=True),
        sa.Column("keywords_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("authority_score", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("source_article_id", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("first_seen_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["source_article_id"], ["articles.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("url", name="uq_link_index_items_url"),
    )
    op.create_index("ix_link_index_items_url", "link_index_items", ["url"], unique=True)
    op.create_index("ix_link_index_items_domain", "link_index_items", ["domain"], unique=False)
    op.create_index("ix_link_index_items_link_type", "link_index_items", ["link_type"], unique=False)
    op.create_index("ix_link_index_items_category", "link_index_items", ["category"], unique=False)
    op.create_index("ix_link_index_items_published_at", "link_index_items", ["published_at"], unique=False)
    op.create_index("ix_link_index_items_source_article_id", "link_index_items", ["source_article_id"], unique=False)
    op.create_index("ix_link_index_items_is_active", "link_index_items", ["is_active"], unique=False)
    op.create_index("ix_link_index_items_last_seen_at", "link_index_items", ["last_seen_at"], unique=False)
    op.create_index("ix_link_index_items_created_at", "link_index_items", ["created_at"], unique=False)
    op.create_index("ix_link_index_items_updated_at", "link_index_items", ["updated_at"], unique=False)
    op.create_index(
        "ix_link_index_type_active_recent",
        "link_index_items",
        ["link_type", "is_active", "published_at"],
        unique=False,
    )

    op.create_table(
        "trusted_domains",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("domain", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("trust_score", sa.Float(), nullable=False, server_default="0.7"),
        sa.Column("tier", sa.String(length=24), nullable=False, server_default="standard"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("domain", name="uq_trusted_domains_domain"),
    )
    op.create_index("ix_trusted_domains_domain", "trusted_domains", ["domain"], unique=True)
    op.create_index("ix_trusted_domains_tier", "trusted_domains", ["tier"], unique=False)
    op.create_index("ix_trusted_domains_enabled", "trusted_domains", ["enabled"], unique=False)
    op.create_index("ix_trusted_domains_created_at", "trusted_domains", ["created_at"], unique=False)
    op.create_index("ix_trusted_domains_updated_at", "trusted_domains", ["updated_at"], unique=False)

    op.create_table(
        "link_recommendation_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("work_id", sa.String(length=64), nullable=False),
        sa.Column("article_id", sa.Integer(), nullable=True),
        sa.Column("draft_id", sa.Integer(), nullable=True),
        sa.Column("mode", sa.String(length=16), nullable=False, server_default="mixed"),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="completed"),
        sa.Column("source_counts_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_by_username", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["article_id"], ["articles.id"]),
        sa.ForeignKeyConstraint(["draft_id"], ["editorial_drafts.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", name="uq_link_recommendation_runs_run_id"),
    )
    op.create_index("ix_link_recommendation_runs_run_id", "link_recommendation_runs", ["run_id"], unique=True)
    op.create_index("ix_link_recommendation_runs_work_id", "link_recommendation_runs", ["work_id"], unique=False)
    op.create_index("ix_link_recommendation_runs_article_id", "link_recommendation_runs", ["article_id"], unique=False)
    op.create_index("ix_link_recommendation_runs_draft_id", "link_recommendation_runs", ["draft_id"], unique=False)
    op.create_index("ix_link_recommendation_runs_mode", "link_recommendation_runs", ["mode"], unique=False)
    op.create_index("ix_link_recommendation_runs_status", "link_recommendation_runs", ["status"], unique=False)
    op.create_index(
        "ix_link_recommend_runs_work_created",
        "link_recommendation_runs",
        ["work_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "link_recommendation_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("link_index_item_id", sa.Integer(), nullable=True),
        sa.Column("link_type", sa.String(length=16), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("title", sa.String(length=1024), nullable=False),
        sa.Column("anchor_text", sa.String(length=255), nullable=False),
        sa.Column("placement_hint", sa.String(length=255), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("rel_attrs", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="suggested"),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["run_id"], ["link_recommendation_runs.run_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["link_index_item_id"], ["link_index_items.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_link_recommendation_items_run_id", "link_recommendation_items", ["run_id"], unique=False)
    op.create_index("ix_link_recommendation_items_link_index_item_id", "link_recommendation_items", ["link_index_item_id"], unique=False)
    op.create_index("ix_link_recommendation_items_link_type", "link_recommendation_items", ["link_type"], unique=False)
    op.create_index("ix_link_recommendation_items_score", "link_recommendation_items", ["score"], unique=False)
    op.create_index("ix_link_recommendation_items_status", "link_recommendation_items", ["status"], unique=False)
    op.create_index("ix_link_recommendation_items_created_at", "link_recommendation_items", ["created_at"], unique=False)
    op.create_index(
        "ix_link_recommend_items_run_score",
        "link_recommendation_items",
        ["run_id", "score"],
        unique=False,
    )

    op.create_table(
        "link_click_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("article_id", sa.Integer(), nullable=True),
        sa.Column("work_id", sa.String(length=64), nullable=True),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("link_type", sa.String(length=16), nullable=False),
        sa.Column("clicked_by_user_id", sa.Integer(), nullable=True),
        sa.Column("clicked_by_username", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["article_id"], ["articles.id"]),
        sa.ForeignKeyConstraint(["clicked_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_link_click_events_article_id", "link_click_events", ["article_id"], unique=False)
    op.create_index("ix_link_click_events_work_id", "link_click_events", ["work_id"], unique=False)
    op.create_index("ix_link_click_events_link_type", "link_click_events", ["link_type"], unique=False)
    op.create_index("ix_link_click_events_clicked_by_user_id", "link_click_events", ["clicked_by_user_id"], unique=False)
    op.create_index("ix_link_click_events_created_at", "link_click_events", ["created_at"], unique=False)

    op.execute(
        """
        INSERT INTO trusted_domains (domain, display_name, trust_score, tier, enabled, notes, created_by)
        VALUES
            ('aps.dz', 'وكالة الأنباء الجزائرية', 0.95, 'official', true, 'وكالة وطنية رسمية', 'migration'),
            ('el-mouradia.dz', 'رئاسة الجمهورية', 0.98, 'official', true, 'مصدر رسمي سيادي', 'migration'),
            ('premier-ministre.gov.dz', 'الوزارة الأولى', 0.97, 'official', true, 'بيانات حكومية رسمية', 'migration'),
            ('mfa.gov.dz', 'وزارة الشؤون الخارجية', 0.96, 'official', true, 'مصدر دبلوماسي رسمي', 'migration'),
            ('interieur.gov.dz', 'وزارة الداخلية', 0.96, 'official', true, 'مصدر رسمي محلي', 'migration'),
            ('meteo.dz', 'الديوان الوطني للأرصاد', 0.95, 'official', true, 'نشرات جوية رسمية', 'migration'),
            ('bank-of-algeria.dz', 'بنك الجزائر', 0.95, 'official', true, 'بيانات مالية رسمية', 'migration'),
            ('sonatrach.com', 'سوناطراك', 0.92, 'institutional', true, 'شركة وطنية استراتيجية', 'migration'),
            ('reuters.com', 'Reuters', 0.9, 'wire', true, 'وكالة دولية موثوقة', 'migration'),
            ('apnews.com', 'Associated Press', 0.9, 'wire', true, 'وكالة دولية موثوقة', 'migration'),
            ('france24.com', 'France 24', 0.8, 'standard', true, 'مصدر دولي للتحقق المقارن', 'migration'),
            ('bbc.com', 'BBC', 0.85, 'standard', true, 'مصدر دولي للتحقق المقارن', 'migration')
        ON CONFLICT (domain) DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_index("ix_link_click_events_created_at", table_name="link_click_events")
    op.drop_index("ix_link_click_events_clicked_by_user_id", table_name="link_click_events")
    op.drop_index("ix_link_click_events_link_type", table_name="link_click_events")
    op.drop_index("ix_link_click_events_work_id", table_name="link_click_events")
    op.drop_index("ix_link_click_events_article_id", table_name="link_click_events")
    op.drop_table("link_click_events")

    op.drop_index("ix_link_recommend_items_run_score", table_name="link_recommendation_items")
    op.drop_index("ix_link_recommendation_items_created_at", table_name="link_recommendation_items")
    op.drop_index("ix_link_recommendation_items_status", table_name="link_recommendation_items")
    op.drop_index("ix_link_recommendation_items_score", table_name="link_recommendation_items")
    op.drop_index("ix_link_recommendation_items_link_type", table_name="link_recommendation_items")
    op.drop_index("ix_link_recommendation_items_link_index_item_id", table_name="link_recommendation_items")
    op.drop_index("ix_link_recommendation_items_run_id", table_name="link_recommendation_items")
    op.drop_table("link_recommendation_items")

    op.drop_index("ix_link_recommend_runs_work_created", table_name="link_recommendation_runs")
    op.drop_index("ix_link_recommendation_runs_status", table_name="link_recommendation_runs")
    op.drop_index("ix_link_recommendation_runs_mode", table_name="link_recommendation_runs")
    op.drop_index("ix_link_recommendation_runs_draft_id", table_name="link_recommendation_runs")
    op.drop_index("ix_link_recommendation_runs_article_id", table_name="link_recommendation_runs")
    op.drop_index("ix_link_recommendation_runs_work_id", table_name="link_recommendation_runs")
    op.drop_index("ix_link_recommendation_runs_run_id", table_name="link_recommendation_runs")
    op.drop_table("link_recommendation_runs")

    op.drop_index("ix_trusted_domains_updated_at", table_name="trusted_domains")
    op.drop_index("ix_trusted_domains_created_at", table_name="trusted_domains")
    op.drop_index("ix_trusted_domains_enabled", table_name="trusted_domains")
    op.drop_index("ix_trusted_domains_tier", table_name="trusted_domains")
    op.drop_index("ix_trusted_domains_domain", table_name="trusted_domains")
    op.drop_table("trusted_domains")

    op.drop_index("ix_link_index_type_active_recent", table_name="link_index_items")
    op.drop_index("ix_link_index_items_updated_at", table_name="link_index_items")
    op.drop_index("ix_link_index_items_created_at", table_name="link_index_items")
    op.drop_index("ix_link_index_items_last_seen_at", table_name="link_index_items")
    op.drop_index("ix_link_index_items_is_active", table_name="link_index_items")
    op.drop_index("ix_link_index_items_source_article_id", table_name="link_index_items")
    op.drop_index("ix_link_index_items_published_at", table_name="link_index_items")
    op.drop_index("ix_link_index_items_category", table_name="link_index_items")
    op.drop_index("ix_link_index_items_link_type", table_name="link_index_items")
    op.drop_index("ix_link_index_items_domain", table_name="link_index_items")
    op.drop_index("ix_link_index_items_url", table_name="link_index_items")
    op.drop_table("link_index_items")

