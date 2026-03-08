from __future__ import annotations

import math

import pytest

import app.services.embedding_service as embedding_module
from app.services.embedding_service import EmbeddingService


def test_hash_embedding_is_deterministic_and_normalized():
    service = EmbeddingService()

    vec1 = service.hash_embedding("economy algeria")
    vec2 = service.hash_embedding("economy algeria")

    assert vec1 == vec2
    assert len(vec1) == service.vector_dim
    norm = math.sqrt(sum(v * v for v in vec1))
    assert abs(norm - 1.0) < 1e-6


@pytest.mark.asyncio
async def test_embed_query_uses_provider_when_available(monkeypatch):
    service = EmbeddingService()
    monkeypatch.setattr(embedding_module.settings, "embedding_provider", "gemini")

    async def fake_embed_with_gemini(text: str, *, task_type: str):
        assert text == "algeria"
        assert task_type == "retrieval_query"
        return ([0.0] * service.vector_dim, "models/test-embedding")

    monkeypatch.setattr(service, "_embed_with_gemini", fake_embed_with_gemini)

    vector, model = await service.embed_query("algeria")

    assert model == "models/test-embedding"
    assert len(vector) == service.vector_dim


@pytest.mark.asyncio
async def test_embed_document_falls_back_to_hash_on_provider_error(monkeypatch):
    service = EmbeddingService()
    monkeypatch.setattr(embedding_module.settings, "embedding_provider", "gemini")

    async def fake_embed_with_gemini(_text: str, *, task_type: str):
        assert task_type == "retrieval_document"
        raise RuntimeError("provider_down")

    monkeypatch.setattr(service, "_embed_with_gemini", fake_embed_with_gemini)

    vector, model = await service.embed_document("news text")

    assert model == "hash-v1"
    assert len(vector) == service.vector_dim

