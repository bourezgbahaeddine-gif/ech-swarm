"""Correlation/request ID helpers."""

from __future__ import annotations

from contextvars import ContextVar
from uuid import uuid4


request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")
correlation_id_ctx: ContextVar[str] = ContextVar("correlation_id", default="")


def new_request_id() -> str:
    return f"req-{uuid4().hex[:20]}"


def new_correlation_id() -> str:
    return f"corr-{uuid4().hex[:20]}"


def set_request_id(value: str) -> None:
    request_id_ctx.set(value or "")


def set_correlation_id(value: str) -> None:
    correlation_id_ctx.set(value or "")


def get_request_id() -> str:
    return request_id_ctx.get("")


def get_correlation_id() -> str:
    return correlation_id_ctx.get("")

