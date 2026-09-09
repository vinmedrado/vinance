from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from backend.app.financial_policy import service
from backend.app.financial_state import service as state_service
from backend.app.financial_state.engine import calculate_financial_state


NOW = datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc)


def _minimal_inputs() -> dict:
    return {
        "household": {"id": 10, "name": "Casa", "household_type": "PERSONAL"},
        "members": [{"user_id": 91, "status": "ACTIVE"}],
        "incomes": [],
        "expenses": [],
        "liabilities": [],
        "assets": [],
        "goals": [],
        "financial_profiles": [],
    }


def _snapshot(snapshot_id: int = 7) -> SimpleNamespace:
    inputs = _minimal_inputs()
    state = calculate_financial_state(inputs, evaluated_at=NOW)
    return SimpleNamespace(
        id=snapshot_id,
        household_id=10,
        engine_version=state["engine_version"],
        evaluated_at=NOW,
        normalized_inputs=inputs,
        metrics=state["metrics"],
        member_views=state["member_views"],
        data_quality=state["data_quality"],
        confidence=state["confidence"],
        missing_fields=state["missing_fields"],
        inconsistencies=state["inconsistencies"],
        input_fingerprint=service._snapshot_input_fingerprint(inputs),
    )


@pytest.mark.asyncio
async def test_current_policy_builds_canonical_inputs_once_and_remains_read_only(
    monkeypatch,
) -> None:
    calls: list[tuple[int, int]] = []

    async def build(_session, *, household_id: int, user_id: int):
        calls.append((household_id, user_id))
        return _minimal_inputs()

    async def no_previous(*_args, **_kwargs):
        return None

    monkeypatch.setattr(state_service, "build_normalized_inputs", build)
    monkeypatch.setattr(service, "_previous_snapshot", no_previous)

    result = await service.current_financial_policy(
        object(),
        household_id=10,
        user_id=91,
        evaluated_at=NOW,
    )

    assert calls == [(10, 91)]
    assert result["engine_version"] == "financial-policy-v1"
    assert result["source_financial_state"]["engine_version"] == (
        "household-financial-state-v1"
    )
    assert result["policy_state"] == "DATA_BLOCKED"


@pytest.mark.asyncio
async def test_policy_replay_uses_immutable_state_snapshot_inputs(monkeypatch) -> None:
    snapshot = _snapshot()
    captured: dict = {}

    async def get_snapshot(_session, **kwargs):
        captured.update(kwargs)
        return snapshot

    async def no_previous(*_args, **_kwargs):
        return None

    monkeypatch.setattr(state_service, "get_snapshot", get_snapshot)
    monkeypatch.setattr(service, "_previous_snapshot", no_previous)

    first = await service.financial_policy_from_state_snapshot(
        object(), household_id=10, snapshot_id=7, user_id=91
    )
    second = await service.financial_policy_from_state_snapshot(
        object(), household_id=10, snapshot_id=7, user_id=91
    )

    assert first == second
    assert captured == {"household_id": 10, "snapshot_id": 7, "user_id": 91}
    assert first["source_financial_state"]["snapshot_id"] == 7


def test_snapshot_from_another_state_engine_is_rejected() -> None:
    snapshot = SimpleNamespace(
        id=7,
        engine_version="future-state-v2",
        evaluated_at=NOW,
        normalized_inputs=_minimal_inputs(),
    )

    with pytest.raises(state_service.FinancialStateValidationError):
        service._state_from_snapshot(snapshot)


def test_snapshot_replay_fails_closed_when_inputs_were_tampered() -> None:
    snapshot = _snapshot()
    snapshot.normalized_inputs["household"]["id"] = 11

    with pytest.raises(
        state_service.FinancialStateValidationError,
        match="integrity check",
    ):
        service._state_from_snapshot(snapshot)


def test_snapshot_replay_fails_closed_when_persisted_state_diverges() -> None:
    snapshot = _snapshot()
    snapshot.metrics = {**snapshot.metrics, "total_assets": "999999.00"}

    with pytest.raises(
        state_service.FinancialStateValidationError,
        match="immutable contract check",
    ):
        service._state_from_snapshot(snapshot)
