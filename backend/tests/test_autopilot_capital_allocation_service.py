from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from backend.app.capital_allocation import service
from backend.app.capital_allocation.engine import calculate_capital_allocation
from backend.app.financial_policy import service as policy_service
from backend.app.financial_policy.engine import calculate_financial_policy
from backend.app.financial_state import service as state_service
from backend.app.financial_state.engine import calculate_financial_state
from backend.tests.test_autopilot_financial_policy_engine import _complete_inputs


NOW = datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc)


def _snapshot(snapshot_id: int = 7) -> SimpleNamespace:
    inputs = _complete_inputs()
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
        input_fingerprint=policy_service._snapshot_input_fingerprint(inputs),
    )


def _policy(policy_id: int = 17) -> dict:
    snapshot = _snapshot()
    state = policy_service._state_from_snapshot(snapshot)
    policy = calculate_financial_policy(state, normalized_inputs=snapshot.normalized_inputs)
    policy.update(
        {
            "policy_id": policy_id,
            "financial_state_snapshot_id": snapshot.id,
            "created_at": NOW,
        }
    )
    return policy


def _decision(decision_id: int = 23) -> SimpleNamespace:
    policy = _policy()
    state = policy_service._state_from_snapshot(_snapshot())
    allocation = calculate_capital_allocation(state, policy)
    return SimpleNamespace(
        id=decision_id,
        household_id=10,
        financial_state_snapshot_id=7,
        financial_policy_decision_id=17,
        created_by_user_id=91,
        engine_version=allocation["engine_version"],
        rules_version=allocation["rules_version"],
        allocation_period=allocation["allocation_period"],
        allocation_status=allocation["allocation_status"],
        currency=allocation["currency"],
        allocatable_capital=allocation["allocatable_capital"],
        allocated_capital=allocation["allocated_capital"],
        remaining_capital=allocation["remaining_capital"],
        investment_bucket_amount=allocation["investment_bucket_amount"],
        input_fingerprint=allocation["input_fingerprint"],
        policy_fingerprint=allocation["policy_fingerprint"],
        ruleset_fingerprint=allocation["ruleset_fingerprint"],
        decision_fingerprint=allocation["decision_fingerprint"],
        decision_payload=service._json_value(allocation),
        idempotency_key="allocation-request",
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
        self.rollbacks = 0

    async def execute(self, _query):
        return self.results.pop(0)

    def add(self, value):
        self.added.append(value)

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1

    async def refresh(self, value):
        value.id = 23
        value.created_at = NOW


@pytest.mark.asyncio
async def test_current_allocation_consumes_one_paired_state_and_policy(monkeypatch) -> None:
    snapshot = _snapshot()
    state = policy_service._state_from_snapshot(snapshot)
    policy = _policy()
    calls = []

    async def context(_session, **kwargs):
        calls.append(kwargs)
        state_without_snapshot = deepcopy(state)
        state_without_snapshot.pop("snapshot_id")
        policy_without_snapshot = deepcopy(policy)
        policy_without_snapshot["policy_id"] = None
        policy_without_snapshot["financial_state_snapshot_id"] = None
        policy_without_snapshot["source_financial_state"]["snapshot_id"] = None
        return state_without_snapshot, policy_without_snapshot

    monkeypatch.setattr(policy_service, "current_financial_policy_context", context)

    result = await service.current_capital_allocation(
        object(), household_id=10, user_id=91, evaluated_at=NOW
    )

    assert calls == [{"household_id": 10, "user_id": 91, "evaluated_at": NOW}]
    assert result["allocation_status"] == "SURPLUS"
    assert result["financial_state_snapshot_id"] is None
    assert result["financial_policy_id"] is None


@pytest.mark.asyncio
async def test_replay_uses_exact_frozen_policy_and_state_snapshot(monkeypatch) -> None:
    policy = _policy()
    snapshot = _snapshot()
    calls = []

    async def get_policy(_session, **kwargs):
        calls.append(("policy", kwargs))
        return policy

    async def get_snapshot(_session, **kwargs):
        calls.append(("state", kwargs))
        return snapshot

    monkeypatch.setattr(policy_service, "get_policy_decision", get_policy)
    monkeypatch.setattr(state_service, "get_snapshot", get_snapshot)

    first = await service.capital_allocation_from_policy_decision(
        object(), household_id=10, policy_id=17, user_id=91
    )
    second = await service.capital_allocation_from_policy_decision(
        object(), household_id=10, policy_id=17, user_id=91
    )

    assert first == second
    assert first["financial_state_snapshot_id"] == 7
    assert first["financial_policy_id"] == 17
    assert calls[0] == ("policy", {"household_id": 10, "policy_id": 17, "user_id": 91})


@pytest.mark.asyncio
async def test_policy_without_snapshot_fails_closed() -> None:
    policy = _policy()
    policy["financial_state_snapshot_id"] = None

    with pytest.raises(state_service.FinancialStateValidationError):
        await service._state_for_policy(
            object(), household_id=10, user_id=91, policy=policy
        )


def test_historical_reader_returns_payload_without_rerunning_engine(monkeypatch) -> None:
    decision = _decision()

    def must_not_run(*_args, **_kwargs):
        raise AssertionError("historical read must not rerun allocation engine")

    monkeypatch.setattr(service, "calculate_capital_allocation", must_not_run)
    result = service._decision_read(decision)

    assert result["allocation_id"] == 23
    assert result["financial_policy_id"] == 17
    assert result["decision_fingerprint"] == decision.decision_fingerprint
    assert result["created_at"] == NOW


@pytest.mark.parametrize(
    ("field", "value"),
    [("allocation_status", "BLOCKED"), ("allocated_capital", "999.00")],
)
def test_historical_reader_fails_closed_on_payload_tampering(field: str, value) -> None:
    decision = _decision()
    decision.decision_payload = deepcopy(decision.decision_payload)
    decision.decision_payload[field] = value

    with pytest.raises(state_service.FinancialStateValidationError, match="immutable contract"):
        service._decision_read(decision)


def test_historical_reader_detects_nested_payload_tampering() -> None:
    decision = _decision()
    decision.decision_payload = deepcopy(decision.decision_payload)
    decision.decision_payload["bucket_totals"]["speculative_capital"] = "999.00"

    with pytest.raises(
        state_service.FinancialStateValidationError,
        match="payload fingerprint",
    ):
        service._decision_read(decision)


@pytest.mark.asyncio
async def test_idempotent_retry_returns_before_creating_policy(monkeypatch) -> None:
    decision = _decision()
    accesses = []

    async def access(*_args, **kwargs):
        accesses.append(kwargs)

    async def existing(*_args, **_kwargs):
        return decision

    async def must_not_create(*_args, **_kwargs):
        raise AssertionError("retry must not create a second Policy or State")

    monkeypatch.setattr(state_service, "get_household_access", access)
    monkeypatch.setattr(service, "_decision_by_idempotency", existing)
    monkeypatch.setattr(policy_service, "create_policy_decision", must_not_create)

    result = await service.create_capital_allocation_decision(
        object(), household_id=10, user_id=91, idempotency_key="allocation-request"
    )

    assert result["allocation_id"] == 23
    assert accesses == [{"household_id": 10, "user_id": 91}]


@pytest.mark.asyncio
async def test_freeze_persists_structured_chain_and_zero_speculative_capital(monkeypatch) -> None:
    snapshot = _snapshot()
    policy = _policy()
    session = _Session()

    async def access(*_args, **_kwargs):
        return None

    async def no_existing(*_args, **_kwargs):
        return None

    async def create_policy(*_args, **kwargs):
        assert kwargs["idempotency_key"].startswith("capital-allocation-v1:")
        return policy

    async def get_snapshot(*_args, **_kwargs):
        return snapshot

    monkeypatch.setattr(state_service, "get_household_access", access)
    monkeypatch.setattr(service, "_decision_by_idempotency", no_existing)
    monkeypatch.setattr(service, "_decision_by_policy", no_existing)
    monkeypatch.setattr(policy_service, "create_policy_decision", create_policy)
    monkeypatch.setattr(state_service, "get_snapshot", get_snapshot)

    result = await service.create_capital_allocation_decision(
        session,
        household_id=10,
        user_id=91,
        idempotency_key="one-allocation-request",
    )

    assert session.commits == 1
    assert len(session.added) == 1
    stored = session.added[0]
    assert stored.financial_state_snapshot_id == 7
    assert stored.financial_policy_decision_id == 17
    assert stored.decision_payload["allocations"]
    assert stored.decision_payload["rules_evaluated"]
    assert stored.decision_payload["bucket_totals"]["speculative_capital"] == "0.00"
    assert result["allocation_id"] == 23


@pytest.mark.asyncio
async def test_history_and_detail_authorize_then_read_frozen_rows(monkeypatch) -> None:
    decision = _decision()
    accesses = []

    async def access(*_args, **kwargs):
        accesses.append(kwargs)

    def must_not_run(*_args, **_kwargs):
        raise AssertionError("history must not replay engines")

    monkeypatch.setattr(state_service, "get_household_access", access)
    monkeypatch.setattr(service, "calculate_capital_allocation", must_not_run)
    history = await service.capital_allocation_history(
        _Session([_ScalarResult(one=1), _ScalarResult(items=[decision])]),
        household_id=10,
        user_id=91,
        limit=20,
        offset=0,
    )
    detail = await service.get_capital_allocation_decision(
        _Session([_ScalarResult(one=decision)]),
        household_id=10,
        allocation_id=23,
        user_id=91,
    )

    assert history["total"] == 1
    assert history["items"][0]["allocation_id"] == 23
    assert detail["allocation_id"] == 23
    assert accesses == [
        {"household_id": 10, "user_id": 91},
        {"household_id": 10, "user_id": 91},
    ]


@pytest.mark.asyncio
async def test_missing_or_cross_household_detail_is_defensive_404_domain_error(monkeypatch) -> None:
    async def access(*_args, **_kwargs):
        return None

    monkeypatch.setattr(state_service, "get_household_access", access)

    with pytest.raises(state_service.FinancialResourceNotFoundError):
        await service.get_capital_allocation_decision(
            _Session([_ScalarResult(one=None)]),
            household_id=10,
            allocation_id=999,
            user_id=91,
        )
