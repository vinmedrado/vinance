from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Coroutine

from backend.app.core.celery import celery_app
from backend.app.core.database import engine
from backend.app.core.logging import get_logger
from backend.app.investment_alerts.service import evaluate_active_subscriptions


logger = get_logger(__name__)


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


@celery_app.task(name="investment_alerts.evaluate_subscriptions", queue="intelligence")
def evaluate_investment_alert_subscriptions() -> dict[str, Any]:
    """Evaluate subscriptions independently; never execute an order."""

    result = _run_async(evaluate_active_subscriptions())
    logger.info(
        "investment_alert.cycle_completed",
        extra={
            "event": "investment_alert.cycle_completed",
            "status": result.get("status", "SUCCESS"),
            "evaluations": result.get("evaluated", 0),
            "alerts_generated": result.get("alerts_generated", 0),
            "cooldown_suppressed": result.get("cooldown_suppressed", 0),
            "duplicates_prevented": result.get("duplicates_prevented", 0),
            "errors": result.get("errors", 0),
        },
    )
    return result
