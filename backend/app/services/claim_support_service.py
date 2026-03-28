from __future__ import annotations

from datetime import datetime
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ArticleClaim, ArticleClaimSupport


_DOC_REF_PREFIXES = ("docintel:", "document-intel:", "doc:", "di://")


class ClaimSupportService:
    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _as_text(value: Any) -> str:
        return str(value or "").strip()

    @classmethod
    def infer_risk_level(cls, claim: dict[str, Any]) -> str:
        raw = cls._as_text(claim.get("risk_level")).lower()
        if raw in {"low", "medium", "high"}:
            return raw
        claim_type = cls._as_text(claim.get("claim_type")).lower()
        confidence = cls._safe_float(claim.get("confidence"), 0.0)
        if claim_type in {"number", "date"} or confidence >= 0.85:
            return "high"
        if confidence >= 0.70:
            return "medium"
        return "low"

    @classmethod
    def normalize_support_refs(cls, value: Any) -> list[dict[str, str]]:
        if not isinstance(value, list):
            return []
        unique: dict[str, dict[str, str]] = {}
        for item in value:
            raw = cls._as_text(item)
            if not raw:
                continue
            low = raw.lower()
            if low.startswith(("http://", "https://")):
                host = (urlparse(raw).hostname or "").lower().strip()
                unique[raw] = {"support_kind": "url", "support_ref": raw, "source_host": host}
                continue
            if low.startswith(_DOC_REF_PREFIXES):
                unique[raw] = {"support_kind": "doc_intel_ref", "support_ref": raw, "source_host": ""}
        return list(unique.values())[:12]

    @classmethod
    def enrich_fact_check_report(cls, report: dict[str, Any]) -> dict[str, Any]:
        claims = report.get("claims")
        if not isinstance(claims, list):
            report["claim_coverage"] = {
                "high_risk_total": 0,
                "high_risk_supported": 0,
                "high_risk_documented_unverifiable": 0,
                "high_risk_unsupported": 0,
                "percent_high_risk_supported": 100.0,
            }
            return report

        high_total = 0
        high_supported = 0
        high_documented_unverifiable = 0
        unsupported_ids: list[str] = []

        for idx, raw_claim in enumerate(claims, start=1):
            if not isinstance(raw_claim, dict):
                continue

            claim_id = cls._as_text(raw_claim.get("id")) or f"clm-{idx}"
            raw_claim["id"] = claim_id

            risk_level = cls.infer_risk_level(raw_claim)
            raw_claim["risk_level"] = risk_level

            supports = cls.normalize_support_refs(raw_claim.get("evidence_links"))
            raw_claim["evidence_links"] = [item["support_ref"] for item in supports]
            raw_claim["support_count"] = len(supports)

            unverifiable = bool(raw_claim.get("unverifiable"))
            unverifiable_reason = cls._as_text(raw_claim.get("unverifiable_reason"))
            raw_claim["unverifiable"] = unverifiable
            raw_claim["unverifiable_reason"] = unverifiable_reason

            supported = len(supports) > 0 or (unverifiable and bool(unverifiable_reason))
            raw_claim["supported"] = supported

            if risk_level != "high":
                continue
            high_total += 1
            if len(supports) > 0:
                high_supported += 1
                continue
            if unverifiable and unverifiable_reason:
                high_documented_unverifiable += 1
                continue
            unsupported_ids.append(claim_id)

        pct_supported = round((high_supported / high_total) * 100.0, 2) if high_total > 0 else 100.0
        coverage = {
            "high_risk_total": high_total,
            "high_risk_supported": high_supported,
            "high_risk_documented_unverifiable": high_documented_unverifiable,
            "high_risk_unsupported": len(unsupported_ids),
            "percent_high_risk_supported": pct_supported,
        }
        report["claim_coverage"] = coverage

        blockers = [str(item) for item in (report.get("blocking_reasons") or [])]
        fixes = [str(item) for item in (report.get("actionable_fixes") or [])]
        if unsupported_ids:
            blocker_msg = "الادعاءات عالية المخاطر تفتقد روابط دعم أو أسباب موثقة لعدم إمكانية التحقق."
            if blocker_msg not in blockers:
                blockers.append(blocker_msg)
            fix_msg = "أضف روابط دعم لكل ادعاء عالي المخاطر أو علّم الادعاء بأنه غير قابل للتحقق مع سبب واضح."
            if fix_msg not in fixes:
                fixes.append(fix_msg)
            report["unsupported_high_risk_claim_ids"] = unsupported_ids
            report["passed"] = False

        report["blocking_reasons"] = blockers
        report["actionable_fixes"] = fixes
        report["stage"] = "FACT_CHECK_PASSED" if bool(report.get("passed")) else "FACT_CHECK_BLOCKED"

        base_score = int(cls._safe_float(report.get("score"), 0.0))
        penalty = min(40, len(unsupported_ids) * 20)
        report["score"] = max(0, min(100, base_score - penalty))
        return report

    async def persist_claim_report(
        self,
        db: AsyncSession,
        *,
        article_id: int,
        quality_report_id: int | None,
        work_id: str | None,
        report: dict[str, Any],
        actor: str | None = None,
    ) -> dict[str, int]:
        claims = report.get("claims")
        if not isinstance(claims, list):
            return {"claims_upserted": 0, "supports_upserted": 0}

        ids = []
        for idx, raw_claim in enumerate(claims, start=1):
            if not isinstance(raw_claim, dict):
                continue
            claim_external_id = self._as_text(raw_claim.get("id")) or f"clm-{idx}"
            ids.append(claim_external_id)
            raw_claim["id"] = claim_external_id

        if not ids:
            return {"claims_upserted": 0, "supports_upserted": 0}

        existing_rows = await db.execute(
            select(ArticleClaim).where(
                ArticleClaim.article_id == article_id,
                ArticleClaim.claim_external_id.in_(ids),
            )
        )
        existing = {row.claim_external_id: row for row in existing_rows.scalars().all()}

        claims_upserted = 0
        supports_upserted = 0
        now = datetime.utcnow()

        for raw_claim in claims:
            if not isinstance(raw_claim, dict):
                continue
            claim_external_id = self._as_text(raw_claim.get("id"))
            if not claim_external_id:
                continue

            risk_level = self.infer_risk_level(raw_claim)
            support_rows = self.normalize_support_refs(raw_claim.get("evidence_links"))
            supported = bool(support_rows) or (
                bool(raw_claim.get("unverifiable")) and bool(self._as_text(raw_claim.get("unverifiable_reason")))
            )

            row = existing.get(claim_external_id)
            if row is None:
                row = ArticleClaim(
                    article_id=article_id,
                    claim_external_id=claim_external_id,
                    created_by=actor,
                    created_at=now,
                )
                db.add(row)

            row.quality_report_id = quality_report_id
            row.work_id = work_id
            row.claim_text = self._as_text(raw_claim.get("text"))
            row.claim_type = self._as_text(raw_claim.get("claim_type")) or None
            row.risk_level = risk_level
            row.confidence = self._safe_float(raw_claim.get("confidence"), 0.0)
            row.sensitive = bool(raw_claim.get("sensitive"))
            row.blocking = bool(raw_claim.get("blocking"))
            row.supported = supported
            row.unverifiable = bool(raw_claim.get("unverifiable"))
            row.unverifiable_reason = self._as_text(raw_claim.get("unverifiable_reason")) or None
            row.metadata_json = {
                "verify_hint": self._as_text(raw_claim.get("verify_hint")) or None,
                "support_count": len(support_rows),
            }
            row.updated_at = now

            await db.flush()
            claims_upserted += 1

            await db.execute(
                delete(ArticleClaimSupport).where(ArticleClaimSupport.claim_id == row.id)
            )
            for support in support_rows:
                db.add(
                    ArticleClaimSupport(
                        claim_id=row.id,
                        support_kind=support["support_kind"],
                        support_ref=support["support_ref"],
                        source_host=support.get("source_host") or None,
                        metadata_json={},
                    )
                )
                supports_upserted += 1

        return {"claims_upserted": claims_upserted, "supports_upserted": supports_upserted}


claim_support_service = ClaimSupportService()
