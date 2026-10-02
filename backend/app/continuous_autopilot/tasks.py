from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Sequence
from zoneinfo import ZoneInfo

from backend.app.continuous_autopilot import service
from backend.app.core.celery import celery_app
from backend.app.core.celery_async import run_celery_coroutine
from backend.app.core.config import settings
from backend.app.core.database import AsyncSessionLocal
from backend.app.core.logging import get_logger


logger = get_logger(__name__)
DEFAULT_BATCH_SIZE = 250
SCHEDULE_HOUR = 22
SCHEDULE_MINUTE = 25


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _scheduled_slot(value: datetime) -> datetime:
    """Return the latest deterministic Beat slot in UTC.

    Beat redelivery can execute the task at a later wall-clock instant.  Freezing
    the default ``as_of`` to the scheduled slot keeps the request fingerprint and
    idempotency key identical throughout that retry window.
    """

    local_now = _utc(value).astimezone(ZoneInfo(settings.celery_timezone))
    slot = local_now.replace(
        hour=SCHEDULE_HOUR,
        minute=SCHEDULE_MINUTE,
        second=0,
        microsecond=0,
    )
    if local_now < slot:
        slot -= timedelta(days=1)
    return slot.astimezone(timezone.utc)


def _scheduled_key(
    *, household_id: int, as_of: datetime, categories: Sequence[str]
) -> str:
    identity = json.dumps(
        {
            "household_id": household_id,
            "evaluation_slot": _utc(as_of).isoformat(),
            "categories": sorted({str(item).upper() for item in categories}),
            "engine": "continuous-autopilot-v1",
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return "continuous-scheduled:" + hashlib.sha256(identity.encode("utf-8")).hexdigest()


async def evaluate_due_households(
    *,
    as_of: datetime,
    limit: int = DEFAULT_BATCH_SIZE,
) -> dict[str, Any]:
    """Run one bounded reconciliation cycle with per-household isolation."""

    effective_at = _utc(as_of)
    async with AsyncSessionLocal() as listing_session:
        targets = await service.scheduled_households(
            listing_session,
            limit=max(1, min(int(limit), 1000)),
        )

    summary: dict[str, Any] = {
        "status": "SUCCESS",
        "scheduled": len(targets),
        "evaluated": 0,
        "changed": 0,
        "no_change": 0,
        "alerts_generated": 0,
        "failures": 0,
        "as_of": effective_at.isoformat(),
    }
    for household_id, owner_user_id, pending in targets:
        categories = list(pending or ["FRESHNESS"])
        key = _scheduled_key(
            household_id=household_id,
            as_of=effective_at,
            categories=categories,
        )
        async with AsyncSessionLocal() as household_session:
            try:
                alerts_before = await service.operational_alert_count(
                    household_session, household_id=household_id
                )
                decision = await service.evaluate_continuous_autopilot(
                    household_session,
                    household_id=household_id,
                    user_id=owner_user_id,
                    idempotency_key=key,
                    as_of=effective_at,
                    change_categories=categories,
                    project_for_user=False,
                )
                alerts_after = await service.operational_alert_count(
                    household_session, household_id=household_id
                )
                summary["evaluated"] += 1
                summary["changed"] += int(
                    decision.get("materiality") not in {None, "NONE", "LOW"}
                )
                summary["no_change"] += int(
                    decision.get("materiality") in {"NONE", "LOW"}
                )
                summary["alerts_generated"] += max(0, alerts_after - alerts_before)
                logger.info(
                    "continuous_autopilot.household_evaluated",
                    extra={
                        "event": "continuous_autopilot.household_evaluated",
                        "household_id": household_id,
                        "continuous_decision_id": decision.get(
                            "continuous_decision_id"
                        ),
                        "status": decision.get("status"),
                        "materiality": decision.get("materiality"),
                        "change_count": len(decision.get("detected_changes") or []),
                        "reevaluation_scope": decision.get("reevaluation_scope"),
                    },
                )
            except Exception as exc:  # noqa: BLE001 - isolate each household
                await household_session.rollback()
                summary["failures"] += 1
                logger.exception(
                    "continuous_autopilot.household_failed",
                    extra={
                        "event": "continuous_autopilot.household_failed",
                        "household_id": household_id,
                        "status": "FAILED",
                        "exception_type": type(exc).__name__,
                    },
                )
    if summary["failures"]:
        summary["status"] = "PARTIAL" if summary["evaluated"] else "FAILED"
    logger.info(
        "continuous_autopilot.cycle_completed",
        extra={
            "event": "continuous_autopilot.cycle_completed",
            "status": summary["status"],
            "evaluations": summary["evaluated"],
            "change_count": summary["changed"],
            "alerts_generated": summary["alerts_generated"],
            "no_change": summary["no_change"],
            "failures": summary["failures"],
        },
    )
    return summary


@celery_app.task(name="continuous_autopilot.evaluate_due", queue="intelligence")
def evaluate_due_continuous_autopilot(
    as_of: str | None = None,
    limit: int = DEFAULT_BATCH_SIZE,
) -> dict[str, Any]:
    """Celery boundary; the deterministic engine always receives explicit time."""

    effective_at = (
        datetime.fromisoformat(as_of)
        if as_of
        else _scheduled_slot(datetime.now(timezone.utc))
    )
    return run_celery_coroutine(
        evaluate_due_households(as_of=effective_at, limit=limit)
    )
