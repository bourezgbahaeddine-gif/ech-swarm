from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi.responses import JSONResponse

from app.core.correlation import get_correlation_id, get_request_id


def response_meta(extra: dict[str, Any] | None = None) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "request_id": get_request_id() or None,
        "correlation_id": get_correlation_id() or None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if extra:
        meta.update(extra)
    return meta


def success_envelope(
    data: Any,
    *,
    status_code: int = 200,
    meta: dict[str, Any] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "ok": True,
            "data": data,
            "error": None,
            "meta": response_meta(meta),
        },
    )


def error_envelope(
    *,
    code: str,
    message: str,
    status_code: int = 400,
    details: Any = None,
    meta: dict[str, Any] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "ok": False,
            "data": None,
            "error": {
                "code": code,
                "message": message,
                "details": details,
            },
            "meta": response_meta(meta),
        },
    )

