"""Shared asyncio runtime for Celery sync tasks.

Using ``asyncio.run`` per task creates a fresh event loop each time, while
SQLAlchemy/asyncpg pooled connections are bound to the loop they were created
with. This helper reuses one loop per worker process to avoid cross-loop errors.
"""

from __future__ import annotations

import asyncio
import threading
from typing import Any

_loop_lock = threading.Lock()
_worker_loop: asyncio.AbstractEventLoop | None = None


def run_async(awaitable: Any) -> Any:
    global _worker_loop
    with _loop_lock:
        if _worker_loop is None or _worker_loop.is_closed():
            _worker_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(_worker_loop)
        loop = _worker_loop
    return loop.run_until_complete(awaitable)

