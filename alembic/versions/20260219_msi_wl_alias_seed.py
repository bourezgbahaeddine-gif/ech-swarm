"""add msi watchlist aliases and seed defaults

Revision ID: 20260219_msi_wl_alias_seed
Revises: 20260219_add_msi_tables
Create Date: 2026-02-19 12:10:00
"""

from __future__ import annotations

import json

from alembic import op
import sqlalchemy as sa


revision = "20260219_msi_wl_alias_seed"
down_revision = "20260219_add_msi_tables"
branch_labels = None
depends_on = None


SEED_ROWS = [
    ("institution_presidency", "رئاسة الجمهورية", ["الرئاسة", "بيان رئاسة الجمهورية"]),
    ("institution_presidency", "عبد المجيد تبون", ["الرئيس عبد المجيد تبون", "الرئيس تبون", "تبون"]),
    ("institution_ministry", "الوزارة الأولى", ["الوزير الأول", "بيان الوزارة الأولى", "اجتماع الحكومة"]),
    ("institution_ministry", "نذير العرباوي", ["الوزير الأول نذير العرباوي", "العرباوي"]),
    ("institution_security", "وزارة الدفاع الوطني", ["الدفاع الوطني", "بيان وزارة الدفاع"]),
    ("institution_security", "الجيش الوطني الشعبي", ["الجيش الجزائري", "الناحية العسكرية"]),
    ("institution_security", "الفريق أول السعيد شنقريحة", ["شنقريحة", "الفريق أول شنقريحة"]),
    ("institution_ministry", "وزارة الداخلية والجماعات المحلية", ["وزارة الداخلية", "الداخلية والجماعات المحلية"]),
    ("institution_ministry", "إبراهيم مراد", ["وزير الداخلية إبراهيم مراد", "مراد"]),
    ("institution_ministry", "وزارة الخارجية", ["الخارجية الجزائرية", "بيان وزارة الخارجية"]),
    ("institution_ministry", "أحمد عطاف", ["وزير الخارجية أحمد عطاف", "عطاف"]),
    ("institution_economy", "سوناطراك", ["مجمع سوناطراك", "شركة سوناطراك"]),
    ("institution_economy", "رشيد حشيشي", ["حشيشي", "الرئيس المدير العام لسوناطراك"]),
    ("institution_economy", "بنك الجزائر", ["البنك المركزي الجزائري", "قرارات بنك الجزائر"]),
    ("institution_economy", "الديوان الوطني للأرصاد الجوية", ["الأرصاد الجوية", "نشرية خاصة", "أحوال الطقس"]),
]


def upgrade() -> None:
    op.add_column(
        "msi_watchlist",
        sa.Column("aliases_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
    )

    bind = op.get_bind()
    stmt = sa.text(
        """
        INSERT INTO msi_watchlist (
            profile_id, entity, aliases_json, enabled, run_daily, run_weekly, created_by_username, created_at, updated_at
        ) VALUES (
            :profile_id, :entity, CAST(:aliases_json AS json), true, true, true, 'system_seed', now(), now()
        )
        ON CONFLICT (profile_id, entity) DO UPDATE
        SET aliases_json = EXCLUDED.aliases_json,
            updated_at = now()
        """
    )
    payload = [
        {"profile_id": profile_id, "entity": entity, "aliases_json": json.dumps(aliases, ensure_ascii=False)}
        for profile_id, entity, aliases in SEED_ROWS
    ]
    bind.execute(stmt, payload)


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("DELETE FROM msi_watchlist WHERE created_by_username = 'system_seed'"))

    op.drop_column("msi_watchlist", "aliases_json")
