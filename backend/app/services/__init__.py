"""Lazy service exports to avoid importing heavy optional dependencies at package import time."""

__all__ = [
    "ai_service",
    "cache_service",
    "notification_service",
    "article_index_service",
    "news_knowledge_service",
    "quality_gate_service",
    "smart_editor_service",
    "project_memory_service",
]


def __getattr__(name: str):
    if name == "ai_service":
        from app.services.ai_service import ai_service

        return ai_service
    if name == "cache_service":
        from app.services.cache_service import cache_service

        return cache_service
    if name == "notification_service":
        from app.services.notification_service import notification_service

        return notification_service
    if name == "article_index_service":
        from app.services.article_index_service import article_index_service

        return article_index_service
    if name == "news_knowledge_service":
        from app.services.news_knowledge_service import news_knowledge_service

        return news_knowledge_service
    if name == "quality_gate_service":
        from app.services.quality_gate_service import quality_gate_service

        return quality_gate_service
    if name == "smart_editor_service":
        from app.services.smart_editor_service import smart_editor_service

        return smart_editor_service
    if name == "project_memory_service":
        from app.services.project_memory_service import project_memory_service

        return project_memory_service
    raise AttributeError(name)
