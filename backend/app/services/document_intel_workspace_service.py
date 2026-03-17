"""Persistence and workflow actions for Document Intelligence documents."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DocumentIntelAction, DocumentIntelClaim, DocumentIntelDocument, ProjectMemoryItem
from app.models.user import User
from app.repositories.story_repository import story_repository
from app.services.audit_service import audit_service
from app.services.project_memory_service import project_memory_service


class DocumentIntelWorkspaceService:
    async def save_document_result(
        self,
        db: AsyncSession,
        *,
        result: dict,
        actor: User | None,
        source_job_id: str | None = None,
    ) -> DocumentIntelDocument:
        document = DocumentIntelDocument(
            filename=str(result.get("filename") or "document.pdf"),
            title=self._derive_title(result),
            parser_used=str(result.get("parser_used") or "unknown"),
            language_hint=str(result.get("language_hint") or "ar"),
            detected_language=str(result.get("detected_language") or "unknown"),
            document_type=str(result.get("document_type") or "report"),
            document_summary=str(result.get("document_summary") or ""),
            stats=result.get("stats") or {},
            headings=result.get("headings") or [],
            news_candidates=result.get("news_candidates") or [],
            entities=result.get("entities") or [],
            story_angles=result.get("story_angles") or [],
            data_points=result.get("data_points") or [],
            warnings=result.get("warnings") or [],
            preview_text=str(result.get("preview_text") or ""),
            source_job_id=source_job_id,
            uploaded_by_user_id=actor.id if actor else None,
            uploaded_by_username=actor.username if actor else None,
        )
        db.add(document)
        await db.flush()

        for idx, claim in enumerate(result.get("claims") or [], start=1):
            db.add(
                DocumentIntelClaim(
                    document_id=document.id,
                    rank=idx,
                    text=str(claim.get("text") or ""),
                    claim_type=str(claim.get("type") or "factual"),
                    confidence=float(claim.get("confidence") or 0.5),
                    risk_level=str(claim.get("risk_level") or "medium"),
                )
            )

        await db.flush()
        await self.log_action(
            db,
            document=document,
            action_type="document_saved",
            actor=actor,
            note="initial_extraction_saved",
            payload={"source_job_id": source_job_id} if source_job_id else {},
        )
        await db.flush()
        return document

    async def get_document(self, db: AsyncSession, document_id: int) -> DocumentIntelDocument | None:
        row = await db.execute(
            select(DocumentIntelDocument).where(DocumentIntelDocument.id == document_id)
        )
        return row.scalar_one_or_none()

    async def list_actions(self, db: AsyncSession, document_id: int) -> list[DocumentIntelAction]:
        row = await db.execute(
            select(DocumentIntelAction)
            .where(DocumentIntelAction.document_id == document_id)
            .order_by(DocumentIntelAction.created_at.desc(), DocumentIntelAction.id.desc())
        )
        return list(row.scalars().all())

    async def load_claims(self, db: AsyncSession, document_id: int) -> list[DocumentIntelClaim]:
        return await self._load_claims(db, document_id)

    async def log_action(
        self,
        db: AsyncSession,
        *,
        document: DocumentIntelDocument,
        action_type: str,
        actor: User | None,
        target_type: str | None = None,
        target_id: str | int | None = None,
        note: str | None = None,
        payload: dict | None = None,
    ) -> DocumentIntelAction:
        action = DocumentIntelAction(
            document_id=document.id,
            action_type=action_type,
            target_type=target_type,
            target_id=str(target_id) if target_id is not None else None,
            note=note,
            payload_json=payload or {},
            actor_user_id=actor.id if actor else None,
            actor_username=actor.username if actor else None,
        )
        db.add(action)
        await db.flush()
        return action

    async def create_story(
        self,
        db: AsyncSession,
        *,
        document: DocumentIntelDocument,
        actor: User,
    ) -> dict:
        story_title = self._story_title(document)
        story_key = f"STY-{datetime.utcnow():%Y%m%d}-{uuid4().hex[:8].upper()}"
        story = await story_repository.create_story(
            db,
            story_key=story_key,
            title=story_title,
            summary=document.document_summary or None,
            category="document_intel",
            geography=None,
            priority=6,
            created_by=actor.username,
        )
        await self.log_action(
            db,
            document=document,
            action_type="story_created",
            actor=actor,
            target_type="story",
            target_id=story.id,
            note="created_from_document_intel",
            payload={"story_key": story.story_key, "title": story.title},
        )
        await audit_service.log_action(
            db,
            action="document_intel_create_story",
            entity_type="document_intel_document",
            entity_id=document.id,
            actor=actor,
            details={"story_id": story.id, "story_key": story.story_key},
        )
        return {"story_id": story.id, "story_key": story.story_key, "title": story.title}

    async def save_memory(
        self,
        db: AsyncSession,
        *,
        document: DocumentIntelDocument,
        actor: User,
    ) -> ProjectMemoryItem:
        claims = await self._load_claims(db, document.id)
        lines = [document.document_summary.strip()] if document.document_summary.strip() else []
        if claims:
            lines.append("أهم الادعاءات:")
            lines.extend(f"- {claim.text}" for claim in claims[:4])
        item = await project_memory_service.create_item(
            db,
            actor=actor,
            memory_type="knowledge",
            title=document.title or document.filename,
            content="\n".join(lines).strip() or (document.preview_text[:800] if document.preview_text else document.filename),
            tags=["document_intel", document.document_type],
            source_type="document_intel",
            source_ref=f"document_intel:{document.id}",
            article_id=None,
            importance=4,
            memory_subtype="source_note",
            freshness_status="stable",
            valid_until=None,
        )
        await self.log_action(
            db,
            document=document,
            action_type="memory_saved",
            actor=actor,
            target_type="memory",
            target_id=item.id,
            note="saved_summary_and_claims",
            payload={"memory_id": item.id},
        )
        return item

    async def build_factcheck_packet(
        self,
        db: AsyncSession,
        *,
        document: DocumentIntelDocument,
        actor: User,
    ) -> dict:
        claims = await self._load_claims(db, document.id)
        lines = [claim.text for claim in claims] or [document.document_summary or document.preview_text[:500]]
        payload = {
            "reference": f"document-intel:{document.id}",
            "text_seed": "\n".join(line.strip() for line in lines if line and line.strip())[:5000],
            "claims_count": len(claims),
        }
        await self.log_action(
            db,
            document=document,
            action_type="factcheck_sent",
            actor=actor,
            target_type="factcheck",
            note="prepared_factcheck_seed",
            payload=payload,
        )
        return payload

    async def _load_claims(self, db: AsyncSession, document_id: int) -> list[DocumentIntelClaim]:
        row = await db.execute(
            select(DocumentIntelClaim)
            .where(DocumentIntelClaim.document_id == document_id)
            .order_by(DocumentIntelClaim.rank.asc(), DocumentIntelClaim.id.asc())
        )
        return list(row.scalars().all())

    @staticmethod
    def _derive_title(result: dict) -> str | None:
        headings = result.get("headings") or []
        if headings:
            return str(headings[0])[:512]
        news = result.get("news_candidates") or []
        if news:
            return str(news[0].get("headline") or "")[:512] or None
        filename = str(result.get("filename") or "").strip()
        return filename[:512] or None

    @staticmethod
    def _story_title(document: DocumentIntelDocument) -> str:
        if document.story_angles and isinstance(document.story_angles, list):
            first = document.story_angles[0]
            if isinstance(first, dict) and first.get("title"):
                return str(first["title"])[:1024]
        if document.title:
            return str(document.title)[:1024]
        return f"قصة من الوثيقة {document.filename}"[:1024]


document_intel_workspace_service = DocumentIntelWorkspaceService()
