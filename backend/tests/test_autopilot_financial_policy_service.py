from __future__ import annotations

from datetime import datetime, timezone
from copy import deepcopy
from types import SimpleNamespace

import pytest

from backend.app.financial_policy import service
from backend.app.financial_policy.engine import calculate_financial_policy
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


def _decision(decision_id: int = 17) -> SimpleNamespace:
    snapshot = _snapshot()
    state = service._state_from_snapshot(snapshot)
    policy = calculate_financial_policy(
        state,
        normalized_inputs=snapshot.normalized_inputs,
    )
    return SimpleNamespace(
        id=decision_id,
        household_id=10,
        financial_state_snapshot_id=snapshot.id,
        created_by_user_id=91,
        engine_version=policy["engine_version"],
        rules_version=policy["rules_version"],
        policy_state=policy["policy_state"],
        investment_readiness=policy["investment_readiness"],
        input_fingerprint=policy["input_fingerprint"],
        ruleset_fingerprint=policy["ruleset_fingerprint"],
        decision_fingerprint=policy["decision_fingerprint"],
        decision_payload=service._json_value(policy),
        idempotency_key="logical-request",
        generated_at=NOW,
        created_at=NOW,
    )


class _ScalarResult:
    def __init__(self, *, one=None, items=None):
        self.one = one
        self.items = items or []

    def scalar_one_or_none(self):
        return self.one

    def scalar_one(self):
        return self.one

    def scalars(self):
        return self

    def all(self):
        return self.items


class _Session:
    def __init__(self, results=None):
        self.results = list(results or [])
        self.added = []
        self.commits = 0

    async def execute(self, _query):
        return self.results.pop(0)

    def add(self, value):
        self.added.append(value)

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        pass

    async def refresh(self, value):
        value.id = 23
        value.created_at = NOW


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


def test_frozen_decision_reader_returns_stored_payload_without_recalculation(
    monkeypatch,
) -> None:
    decision = _decision()

    def must_not_run(*_args, **_kwargs):
        raise AssertionError("historical reads must not rerun an engine")

    monkeypatch.setattr(service, "calculate_financial_policy", must_not_run)
    result = service._decision_read(decision)

    assert result["policy_id"] == 17
    assert result["financial_state_snapshot_id"] == 7
    assert result["decision_fingerprint"] == decision.decision_fingerprint
    assert result["created_at"] == NOW


def test_frozen_decision_reader_fails_closed_on_indexed_payload_divergence() -> None:
    decision = _decision()
    decision.decision_payload = deepcopy(decision.decision_payload)
    decision.decision_payload["policy_state"] = "INVESTMENT_READY"

    with pytest.raises(
        state_service.FinancialStateValidationError,
        match="immutable contract check",
    ):
        service._decision_read(decision)


@pytest.mark.asyncio
async def test_policy_freeze_is_idempotent_before_creating_another_state_snapshot(
    monkeypatch,
) -> None:
    decision = _decision()
    accesses = []

    async def access(*_args, **kwargs):
        accesses.append(kwargs)

    async def existing(*_args, **_kwargs):
        return decision

    async def must_not_snapshot(*_args, **_kwargs):
        raise AssertionError("idempotent retry must not create a State snapshot")

    monkeypatch.setattr(state_service, "get_household_access", access)
    monkeypatch.setattr(service, "_decision_by_idempotency", existing)
    monkeypatch.setattr(state_service, "create_snapshot", must_not_snapshot)

    result = await service.create_policy_decision(
        object(),
        household_id=10,
        user_id=91,
        idempotency_key="logical-request",
    )

    assert accesses == [{"household_id": 10, "user_id": 91}]
    assert result["policy_id"] == 17


@pytest.mark.asyncio
async def test_policy_freeze_persists_full_structured_payload(monkeypatch) -> None:
    snapshot = _snapshot()
    policy = calculate_financial_policy(
        service._state_from_snapshot(snapshot),
        normalized_inputs=snapshot.normalized_inputs,
    )
    session = _Session()

    async def access(*_args, **_kwargs):
        return None

    async def no_existing(*_args, **_kwargs):
        return None

    async def create_snapshot(*_args, **kwargs):
        assert kwargs["idempotency_key"].startswith("financial-policy-v1:")
        return snapshot

    async def replay(*_args, **_kwargs):
        return policy

    monkeypatch.setattr(state_service, "get_household_access", access)
    monkeypatch.setattr(service, "_decision_by_idempotency", no_existing)
    monkeypatch.setattr(state_service, "create_snapshot", create_snapshot)
    monkeypatch.setattr(service, "financial_policy_from_state_snapshot", replay)

    result = await service.create_policy_decision(
        session,
        household_id=10,
        user_id=91,
        idempotency_key="one-logical-request",
    )

    assert session.commits == 1
    assert len(session.added) == 1
    stored = session.added[0]
    assert stored.financial_state_snapshot_id == 7
    assert stored.decision_payload["explanations"]
    assert stored.decision_payload["rules_evaluated"]
    assert result["policy_id"] == 23
    assert result["financial_state_snapshot_id"] == 7


@pytest.mark.asyncio
async def test_history_and_detail_use_stored_rows_after_household_authorization(
    monkeypatch,
) -> None:
    decision = _decision()
    accesses = []

    async def access(*_args, **kwargs):
        accesses.append(kwargs)

    def must_not_run(*_args, **_kwargs):
        raise AssertionError("history/detail must not rerun an engine")

    monkeypatch.setattr(state_service, "get_household_access", access)
    monkeypatch.setattr(service, "calculate_financial_policy", must_not_run)
    history_session = _Session(
        [_ScalarResult(one=1), _ScalarResult(items=[decision])]
    )
    detail_session = _Session([_ScalarResult(one=decision)])

    history = await service.policy_decision_history(
        history_session,
        household_id=10,
        user_id=91,
        limit=20,
        offset=0,
    )
    detail = await service.get_policy_decision(
        detail_session,
        household_id=10,
        policy_id=17,
        user_id=91,
    )

    assert history["total"] == 1
    assert history["items"][0]["policy_id"] == 17
    assert detail["policy_id"] == 17
    assert accesses == [
        {"household_id": 10, "user_id": 91},
        {"household_id": 10, "user_id": 91},
    ]


@pytest.mark.asyncio
async def test_missing_policy_detail_uses_defensive_resource_not_found(monkeypatch) -> None:
    async def access(*_args, **_kwargs):
        return None

    monkeypatch.setattr(state_service, "get_household_access", access)
    session = _Session([_ScalarResult(one=None)])

    with pytest.raises(state_service.FinancialResourceNotFoundError):
        await service.get_policy_decision(
            session,
            household_id=10,
            policy_id=999,
            user_id=91,
        )
