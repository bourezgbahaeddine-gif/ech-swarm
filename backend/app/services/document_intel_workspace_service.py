"""Persistence and workflow actions for Document Intelligence documents."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Article, DocumentIntelAction, DocumentIntelClaim, DocumentIntelDocument, EditorialDraft, ProjectMemoryItem
from app.models.news import NewsCategory, NewsStatus, UrgencyLevel
from app.models.user import User
from app.repositories.story_repository import story_repository
from app.services.audit_service import audit_service
from app.services.article_index_service import article_index_service
from app.services.project_memory_service import project_memory_service
from app.services.smart_editor_service import smart_editor_service


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
        angle_title: str | None = None,
        angle_why_it_matters: str | None = None,
    ) -> dict:
        claims = await self._load_claims(db, document.id)
        story_title = self._story_title(document, angle_title=angle_title)
        story_key = f"STY-{datetime.utcnow():%Y%m%d}-{uuid4().hex[:8].upper()}"
        brief_lines = []
        if angle_why_it_matters:
            brief_lines.append(angle_why_it_matters.strip())
        elif document.document_summary:
            brief_lines.append(document.document_summary.strip())
        if claims:
            brief_lines.append("أهم ما يستحق المتابعة:")
            brief_lines.extend(f"- {claim.text}" for claim in claims[:3])
        story = await story_repository.create_story(
            db,
            story_key=story_key,
            title=story_title,
            summary="\n".join(line for line in brief_lines if line).strip() or document.document_summary or None,
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
        return {
            "story_id": story.id,
            "story_key": story.story_key,
            "title": story.title,
            "brief": "\n".join(line for line in brief_lines if line).strip() or document.document_summary or "",
        }

    async def create_workspace_draft(
        self,
        db: AsyncSession,
        *,
        document: DocumentIntelDocument,
        actor: User,
        angle_title: str | None = None,
        claim_indexes: list[int] | None = None,
        category: str | None = "international",
        urgency: str | None = "normal",
    ) -> dict:
        claims = await self._load_claims(db, document.id)
        selected_claims = self._select_claims(claims, claim_indexes)
        title = angle_title or self._story_title(document)
        body_html = self._build_workspace_body(document, selected_claims=selected_claims, angle_title=angle_title)
        work_id = self._new_work_id()
        summary = (document.document_summary or "").strip()[:1000] or None
        article = Article(
            unique_hash=f"document-intel:{document.id}:{uuid4().hex}",
            original_title=title,
            original_url=f"document-intel://document/{document.id}",
            original_content=smart_editor_service.html_to_text(body_html),
            source_id=None,
            source_name="document_intel",
            title_ar=title,
            summary=summary,
            body_html=body_html,
            category=self._normalize_category(category),
            importance_score=68,
            urgency=self._normalize_urgency(urgency),
            is_breaking=False,
            status=NewsStatus.DRAFT_GENERATED,
            reviewed_by=actor.full_name_ar,
            reviewed_at=datetime.utcnow(),
        )
        db.add(article)
        await db.flush()

        draft = EditorialDraft(
            article_id=article.id,
            work_id=work_id,
            source_action="document_intel_workspace",
            change_origin="manual",
            title=title,
            body=body_html,
            note=f"document_intel:{document.id}",
            status="draft",
            version=1,
            created_by=actor.full_name_ar,
            updated_by=actor.full_name_ar,
        )
        db.add(draft)
        await db.flush()

        try:
            await article_index_service.upsert_article(db, article)
        except Exception:
            pass

        await self.log_action(
            db,
            document=document,
            action_type="draft_created",
            actor=actor,
            target_type="workspace_draft",
            target_id=work_id,
            note="opened_in_smart_editor",
            payload={"article_id": article.id, "work_id": work_id, "title": title},
        )
        await audit_service.log_action(
            db,
            action="document_intel_create_draft",
            entity_type="document_intel_document",
            entity_id=document.id,
            actor=actor,
            details={"article_id": article.id, "work_id": work_id},
        )
        return {"article_id": article.id, "work_id": work_id, "title": title}

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
    def _story_title(document: DocumentIntelDocument, *, angle_title: str | None = None) -> str:
        if angle_title and angle_title.strip():
            return angle_title.strip()[:1024]
        if document.story_angles and isinstance(document.story_angles, list):
            first = document.story_angles[0]
            if isinstance(first, dict) and first.get("title"):
                return str(first["title"])[:1024]
        if document.title:
            return str(document.title)[:1024]
        return f"قصة من الوثيقة {document.filename}"[:1024]

    @staticmethod
    def _new_work_id() -> str:
        return f"WRK-{datetime.utcnow():%Y%m%d}-{uuid4().hex[:10].upper()}"

    @staticmethod
    def _select_claims(claims: list[DocumentIntelClaim], claim_indexes: list[int] | None) -> list[DocumentIntelClaim]:
        if not claim_indexes:
            return claims[:4]
        index_set = {idx for idx in claim_indexes if idx >= 1}
        chosen = [claim for claim in claims if claim.rank in index_set]
        return chosen or claims[:4]

    @staticmethod
    def _build_workspace_body(
        document: DocumentIntelDocument,
        *,
        selected_claims: list[DocumentIntelClaim],
        angle_title: str | None,
    ) -> str:
        title = angle_title or document.title or document.filename
        lines = [f"<h1>{title}</h1>"]
        if document.document_summary:
            lines.append(f"<p><strong>خلاصة الوثيقة:</strong> {document.document_summary}</p>")
        if document.story_angles:
            first_angle = document.story_angles[0] if isinstance(document.story_angles, list) and document.story_angles else None
            if isinstance(first_angle, dict) and first_angle.get("why_it_matters"):
                lines.append(f"<p><strong>لماذا تهم؟</strong> {first_angle['why_it_matters']}</p>")
        if selected_claims:
            lines.append("<h2>ادعاءات ومحاور قابلة للاستخدام</h2>")
            lines.append("<ul>")
            for claim in selected_claims:
                lines.append(f"<li>{claim.text}</li>")
            lines.append("</ul>")
        if document.entities:
            names = []
            for entity in document.entities[:6]:
                if isinstance(entity, dict) and entity.get("name"):
                    names.append(str(entity["name"]))
            if names:
                lines.append(f"<p><strong>جهات وأسماء بارزة:</strong> {'، '.join(names)}</p>")
        lines.append("<p>ابدأ من هذه الخلاصة ثم ابنِ الخبر بصياغة تحريرية واضحة، مع توثيق الادعاءات وربطها بالمصدر الأصلي للوثيقة.</p>")
        return "\n".join(lines)

    @staticmethod
    def _normalize_category(value: str | None) -> NewsCategory:
        raw = (value or "").strip().lower()
        try:
            return NewsCategory(raw)
        except Exception:
            return NewsCategory.INTERNATIONAL

    @staticmethod
    def _normalize_urgency(value: str | None) -> UrgencyLevel:
        raw = (value or "").strip().lower()
        try:
            return UrgencyLevel(raw)
        except Exception:
            return UrgencyLevel.NORMAL


document_intel_workspace_service = DocumentIntelWorkspaceService()
