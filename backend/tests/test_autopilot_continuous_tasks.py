from __future__ import annotations

from datetime import datetime, timezone

import pytest

from backend.app.continuous_autopilot import tasks
from backend.app.core.celery import celery_app


NOW = datetime(2026, 9, 24, 22, 25, tzinfo=timezone.utc)


class _Session:
    def __init__(self):
        self.rollbacks = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def rollback(self):
        self.rollbacks += 1


class _SessionFactory:
    def __init__(self):
        self.sessions: list[_Session] = []

    def __call__(self):
        session = _Session()
        self.sessions.append(session)
        return session


def test_celery_reuses_existing_intelligence_queue_and_daily_beat() -> None:
    assert "backend.app.continuous_autopilot.tasks" in celery_app.conf.include
    assert celery_app.conf.task_routes["continuous_autopilot.evaluate_due"] == {
        "queue": "intelligence"
    }
    entry = celery_app.conf.beat_schedule["continuous-autopilot-evaluate-daily"]
    assert entry["task"] == "continuous_autopilot.evaluate_due"
    assert entry["options"] == {"queue": "intelligence"}
    assert "22" in str(entry["schedule"])
    assert "25" in str(entry["schedule"])


def test_scheduled_key_matches_exact_frozen_slot_and_request_shape() -> None:
    first = tasks._scheduled_key(
        household_id=10,
        as_of=NOW,
        categories=["MARKET_DATA", "FRESHNESS"],
    )
    reordered = tasks._scheduled_key(
        household_id=10,
        as_of=NOW,
        categories=["FRESHNESS", "MARKET_DATA"],
    )
    assert first == reordered
    assert first != tasks._scheduled_key(
        household_id=11,
        as_of=NOW,
        categories=["MARKET_DATA", "FRESHNESS"],
    )
    assert first != tasks._scheduled_key(
        household_id=10,
        as_of=NOW.replace(hour=23),
        categories=["MARKET_DATA", "FRESHNESS"],
    )
    assert first != tasks._scheduled_key(
        household_id=10,
        as_of=NOW.replace(day=25),
        categories=["MARKET_DATA", "FRESHNESS"],
    )


def test_default_schedule_slot_is_stable_across_same_beat_retry_window() -> None:
    first_delivery = datetime(2026, 9, 25, 1, 25, 30, tzinfo=timezone.utc)
    later_retry = datetime(2026, 9, 25, 18, 0, tzinfo=timezone.utc)
    next_delivery = datetime(2026, 9, 26, 1, 25, 30, tzinfo=timezone.utc)

    assert tasks._scheduled_slot(first_delivery) == datetime(
        2026, 9, 25, 1, 25, tzinfo=timezone.utc
    )
    assert tasks._scheduled_slot(later_retry) == tasks._scheduled_slot(first_delivery)
    assert tasks._scheduled_slot(next_delivery) != tasks._scheduled_slot(first_delivery)


@pytest.mark.asyncio
async def test_cycle_is_bounded_deterministic_and_isolates_household_failures(
    monkeypatch,
) -> None:
    factory = _SessionFactory()
    calls = []
    alert_counts = {10: 0, 11: 0}

    async def scheduled(_session, *, limit):
        assert limit == 2
        return [(10, 91, ["MARKET_DATA"]), (11, 92, [])]

    async def evaluate(_session, **kwargs):
        calls.append(kwargs)
        if kwargs["household_id"] == 11:
            raise RuntimeError("provider unavailable")
        alert_counts[kwargs["household_id"]] = 1
        return {
            "continuous_decision_id": 51,
            "status": "CHANGED",
            "materiality": "HIGH",
            "alert_decision": "IMPORTANT",
            "detected_changes": [{"change_id": "x"}],
            "reevaluation_scope": "INVESTMENT_CHAIN",
        }

    async def alert_count(_session, *, household_id):
        return alert_counts[household_id]

    monkeypatch.setattr(tasks, "AsyncSessionLocal", factory)
    monkeypatch.setattr(tasks.service, "scheduled_households", scheduled)
    monkeypatch.setattr(tasks.service, "evaluate_continuous_autopilot", evaluate)
    monkeypatch.setattr(tasks.service, "operational_alert_count", alert_count)
    result = await tasks.evaluate_due_households(as_of=NOW, limit=2)
    assert result == {
        "status": "PARTIAL",
        "scheduled": 2,
        "evaluated": 1,
        "changed": 1,
        "no_change": 0,
        "alerts_generated": 1,
        "failures": 1,
        "as_of": NOW.isoformat(),
    }
    assert calls[0]["as_of"] == calls[1]["as_of"] == NOW
    assert calls[0]["project_for_user"] is False
    assert calls[1]["project_for_user"] is False
    assert calls[0]["change_categories"] == ["MARKET_DATA"]
    assert calls[1]["change_categories"] == ["FRESHNESS"]
    assert calls[0]["idempotency_key"] == tasks._scheduled_key(
        household_id=10,
        as_of=NOW,
        categories=["MARKET_DATA"],
    )
    assert factory.sessions[-1].rollbacks == 1


def test_sync_task_passes_explicit_time_to_async_boundary(monkeypatch) -> None:
    captured = {}

    def run(coro):
        captured["coroutine"] = coro
        coro.close()
        return {"status": "SUCCESS"}

    monkeypatch.setattr(tasks, "run_celery_coroutine", run)
    result = tasks.evaluate_due_continuous_autopilot.run(
        as_of=NOW.isoformat(), limit=3
    )
    assert result == {"status": "SUCCESS"}
    assert captured["coroutine"].cr_code.co_name == "evaluate_due_households"
