"""Embedding service with provider-backed vectors and deterministic fallback."""

from __future__ import annotations

import asyncio
import hashlib
import math
import time
from collections.abc import Sequence
from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger("services.embedding_service")
settings = get_settings()


def _is_vector_sequence(value: Any) -> bool:
    return isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray))


class EmbeddingService:
    """Generate vectors for query/document text with safe fallback."""

    def __init__(self) -> None:
        self._gemini_client = None

    @property
    def vector_dim(self) -> int:
        return max(64, int(settings.embedding_vector_dim))

    def hash_embedding(self, text: str, dim: int | None = None) -> list[float]:
        target_dim = int(dim or self.vector_dim)
        base = hashlib.sha256((text or "").encode("utf-8")).digest()
        values: list[float] = []
        seed = base
        while len(values) < target_dim:
            seed = hashlib.sha256(seed).digest()
            for byte in seed:
                values.append((byte / 255.0) * 2.0 - 1.0)
                if len(values) >= target_dim:
                    break
        norm = math.sqrt(sum(v * v for v in values)) or 1.0
        return [v / norm for v in values]

    @staticmethod
    def _to_float_list(values: Sequence[Any]) -> list[float]:
        return [float(x) for x in values]

    def _normalize_dim(self, values: Sequence[Any]) -> list[float]:
        vector = self._to_float_list(values)
        dim = self.vector_dim
        if len(vector) > dim:
            vector = vector[:dim]
        elif len(vector) < dim:
            vector = vector + ([0.0] * (dim - len(vector)))
        norm = math.sqrt(sum(v * v for v in vector)) or 1.0
        return [v / norm for v in vector]

    @staticmethod
    def _extract_embedding(response: Any) -> list[float]:
        if response is None:
            raise ValueError("embedding_empty_response")

        if isinstance(response, dict):
            embedded = response.get("embedding")
            if isinstance(embedded, dict) and isinstance(embedded.get("values"), list):
                return [float(v) for v in embedded["values"]]
            if isinstance(embedded, list):
                return [float(v) for v in embedded]

            embeddings = response.get("embeddings")
            if isinstance(embeddings, list) and embeddings:
                first = embeddings[0]
                if isinstance(first, dict):
                    if isinstance(first.get("values"), list):
                        return [float(v) for v in first["values"]]
                    if isinstance(first.get("embedding"), list):
                        return [float(v) for v in first["embedding"]]
                if isinstance(first, list):
                    return [float(v) for v in first]

        embedded = getattr(response, "embedding", None)
        if embedded is not None:
            values = getattr(embedded, "values", embedded)
            if _is_vector_sequence(values):
                return [float(v) for v in values]

        embeddings = getattr(response, "embeddings", None)
        if _is_vector_sequence(embeddings) and embeddings:
            first = embeddings[0]
            values = getattr(first, "values", first)
            if _is_vector_sequence(values):
                return [float(v) for v in values]

        raise ValueError("embedding_vector_not_found")

    async def _get_gemini(self):
        if self._gemini_client is None:
            import google.generativeai as genai

            api_key = (settings.gemini_api_key or "").strip()
            if not api_key:
                raise RuntimeError("gemini_api_key_missing")
            genai.configure(api_key=api_key)
            self._gemini_client = genai
        return self._gemini_client

    async def _embed_with_gemini(self, text: str, *, task_type: str) -> tuple[list[float], str]:
        genai = await self._get_gemini()
        model_name = (settings.embedding_model_gemini or "models/text-embedding-004").strip()
        if not model_name.startswith("models/"):
            model_name = f"models/{model_name}"

        payload = {
            "model": model_name,
            "content": text or ".",
            "task_type": task_type,
            "output_dimensionality": self.vector_dim,
        }

        def _call_with_dim() -> Any:
            return genai.embed_content(**payload)

        def _call_without_dim() -> Any:
            copy_payload = dict(payload)
            copy_payload.pop("output_dimensionality", None)
            return genai.embed_content(**copy_payload)

        try:
            response = await asyncio.to_thread(_call_with_dim)
        except TypeError:
            response = await asyncio.to_thread(_call_without_dim)

        vector = self._extract_embedding(response)
        return self._normalize_dim(vector), model_name

    async def _embed(self, text: str, *, task_type: str) -> tuple[list[float], str]:
        provider = (settings.embedding_provider or "gemini").strip().lower()
        started = time.perf_counter()

        if provider == "gemini":
            try:
                vector, model_name = await self._embed_with_gemini(text, task_type=task_type)
                logger.info(
                    "embedding_generated",
                    provider="gemini",
                    task_type=task_type,
                    model=model_name,
                    elapsed_ms=round((time.perf_counter() - started) * 1000, 2),
                )
                return vector, model_name
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "embedding_provider_failed",
                    provider="gemini",
                    task_type=task_type,
                    error=str(exc),
                    fallback="hash-v1",
                )

        return self.hash_embedding(text), "hash-v1"

    async def embed_document(self, text: str) -> tuple[list[float], str]:
        return await self._embed(text, task_type="retrieval_document")

    async def embed_query(self, text: str) -> tuple[list[float], str]:
        return await self._embed(text, task_type="retrieval_query")


embedding_service = EmbeddingService()
