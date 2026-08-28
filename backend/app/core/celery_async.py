from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from typing import TypeVar

from backend.app.core.database import close_database
from backend.app.core.logging import get_logger

T = TypeVar("T")
logger = get_logger(__name__)


def run_celery_coroutine(coro: Awaitable[T]) -> T:
    """Run an async job safely inside a synchronous Celery task.

    Celery workers may fork processes and execute multiple tasks over time. Async
    SQLAlchemy/asyncpg connections are bound to the event loop that created them;
    reusing a pooled connection from a previous loop can raise errors such as
    "got Future attached to a different loop" or "Event loop is closed".

    This helper creates a fresh loop per task invocation, runs the coroutine, then
    disposes async database connections before the loop is closed.
    """
    loop = asyncio.new_event_loop()
    previous_loop: asyncio.AbstractEventLoop | None = None
    try:
        try:
            previous_loop = asyncio.get_event_loop()
        except RuntimeError:
            previous_loop = None
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)
    finally:
        try:
            if not loop.is_closed():
                loop.run_until_complete(close_database())
                loop.run_until_complete(loop.shutdown_asyncgens())
        except Exception as exc:  # noqa: BLE001 - cleanup must not mask task result
            logger.warning("Celery async cleanup failed", extra={"error": str(exc)})
        finally:
            # Do not keep a task-scoped event loop registered after the task.
            # A future Celery task must create and own its own loop.
            asyncio.set_event_loop(None)
            if not loop.is_closed():
                loop.close()
