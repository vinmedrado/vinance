from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Coroutine

from backend.app.core.celery import celery_app
from backend.app.core.database import AsyncSessionLocal, engine
from backend.app.investment_performance.service import process_due_evaluations


logger = logging.getLogger(__name__)


async def _run_with_cleanup(coro: Coroutine[Any, Any, dict[str, Any]]) -> dict[str, Any]:
    try:
        return await coro
    finally:
        await engine.dispose()


def _run_async(coro: Coroutine[Any, Any, dict[str, Any]]) -> dict[str, Any]:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(_run_with_cleanup(coro))
    with ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(asyncio.run, _run_with_cleanup(coro)).result()


@celery_app.task(name="investment_performance.evaluate_due", queue="intelligence")
def evaluate_due_investment_performance() -> dict[str, Any]:
    """Evaluate only matured, not-yet-persisted decision horizons."""

    return _run_async(_evaluate_due_investment_performance())


async def _evaluate_due_investment_performance() -> dict[str, Any]:
    async with AsyncSessionLocal() as session:
        try:
            result = await process_due_evaluations(session)
            logger.info(
                "investment_performance.evaluation_completed",
                extra={
                    "event": "investment_performance.evaluation_completed",
                    "status": result.get("status", "SUCCESS"),
                    "eligible": result.get("eligible", 0),
                    "evaluations_created": result.get("created", 0),
                    "pending_prices": result.get("pending_prices", 0),
                },
            )
            return result
        except Exception as exc:
            await session.rollback()
            logger.exception(
                "investment_performance.evaluation_failed",
                extra={
                    "event": "investment_performance.evaluation_failed",
                    "status": "FAILED",
                    "exception_type": type(exc).__name__,
                },
            )
            raise
