from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import Base
from app.models.news import Article, EditorialDraft, NewsStatus, Source
from app.models.story import Story, StoryItem, StoryStatus


def _build_session() -> Session:
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(
        engine,
        tables=[
            Source.__table__,
            Article.__table__,
            EditorialDraft.__table__,
            Story.__table__,
            StoryItem.__table__,
        ],
    )
    return Session(engine)


def _seed_article_and_draft(session: Session) -> tuple[Article, EditorialDraft]:
    source = Source(name="Test Source", url="https://example.com/rss")
    session.add(source)
    session.flush()

    article = Article(
        unique_hash="article-hash-1",
        original_title="Story source",
        original_url="https://example.com/news/1",
        source_id=source.id,
        source_name=source.name,
        status=NewsStatus.NEW,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    session.add(article)
    session.flush()

    draft = EditorialDraft(
        article_id=article.id,
        work_id="WRK-TEST-001",
        source_action="manual",
        change_origin="manual",
        title="Draft title",
        body="<p>Draft body</p>",
        status="draft",
        version=1,
        created_by="tester",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    session.add(draft)
    session.flush()
    return article, draft


def test_story_smoke_create_and_link_items() -> None:
    with _build_session() as session:
        article, draft = _seed_article_and_draft(session)
        story = Story(
            story_key="STY-TEST-0001",
            title="Story title",
            status=StoryStatus.open,
            priority=5,
            created_by="tester",
            updated_by="tester",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        session.add(story)
        session.flush()

        session.add(
            StoryItem(
                story_id=story.id,
                article_id=article.id,
                link_type="article",
                created_by="tester",
                created_at=datetime.utcnow(),
            )
        )
        session.add(
            StoryItem(
                story_id=story.id,
                draft_id=draft.id,
                link_type="draft",
                created_by="tester",
                created_at=datetime.utcnow(),
            )
        )
        session.commit()

        stored_story = session.execute(select(Story).where(Story.id == story.id)).scalar_one()
        assert len(stored_story.items) == 2
        assert any(item.article_id is not None and item.draft_id is None for item in stored_story.items)
        assert any(item.draft_id is not None and item.article_id is None for item in stored_story.items)


def test_story_item_invalid_dual_reference_rejected() -> None:
    with _build_session() as session:
        article, draft = _seed_article_and_draft(session)
        story = Story(
            story_key="STY-TEST-0002",
            title="Story title",
            status=StoryStatus.open,
            priority=5,
            created_by="tester",
            updated_by="tester",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        session.add(story)
        session.flush()

        session.add(
            StoryItem(
                story_id=story.id,
                article_id=article.id,
                draft_id=draft.id,
                link_type="article",
                created_by="tester",
                created_at=datetime.utcnow(),
            )
        )

        with pytest.raises(IntegrityError):
            session.commit()


def test_story_item_link_type_mismatch_rejected() -> None:
    with _build_session() as session:
        article, _ = _seed_article_and_draft(session)
        story = Story(
            story_key="STY-TEST-0003",
            title="Story title",
            status=StoryStatus.open,
            priority=5,
            created_by="tester",
            updated_by="tester",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        session.add(story)
        session.flush()

        session.add(
            StoryItem(
                story_id=story.id,
                article_id=article.id,
                link_type="draft",
                created_by="tester",
                created_at=datetime.utcnow(),
            )
        )

        with pytest.raises(IntegrityError):
            session.commit()
