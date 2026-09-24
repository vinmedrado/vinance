from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import pytest

from backend.app.action_plan import service
from backend.app.action_plan.engine import calculate_action_plan
from backend.app.financial_policy import service as policy_service
from backend.app.financial_state import service as state_service
from backend.app.investment_orchestrator import service as orchestration_service
from backend.tests.test_autopilot_financial_policy_engine import _complete_inputs
from backend.tests.test_autopilot_investment_orchestrator_service import (
    NOW,
    _chain,
    _orchestration,
)


def _frozen_chain():
    _, state, policy, allocation = _chain()
    orchestration = _orchestration()
    orchestration.update({"orchestration_id": 31, "created_at": NOW})
    return state, policy, allocation, orchestration


def _output():
    return calculate_action_plan(*_frozen_chain())


def _decision():
    output = _output()
    summary = output["summary"]
    _, _, _, orchestration = _frozen_chain()
    return SimpleNamespace(
        id=41,
        household_id=10,
        financial_state_snapshot_id=7,
        financial_policy_decision_id=17,
        capital_allocation_decision_id=23,
        investment_orchestration_decision_id=31,
        created_by_user_id=91,
        engine_version=output["engine_version"],
        rules_version=output["rules_version"],
        status=output["status"],
        currency=output["currency"],
        period=output["period"],
        authorized_financial_capital=summary["authorized_financial_capital"],
        investment_budget=summary["authorized_investment_capital"],
        suggested_capital=orchestration["suggested_capital"],
        remaining_investment_cash=orchestration["remaining_investment_cash"],
        total_financial_actions=output["total_financial_actions"],
        total_investment_actions=output["total_investment_actions"],
        total_hold_cash=output["total_hold_cash"],
        speculative_capital=output["speculative_capital"],
        state_fingerprint=output["state_fingerprint"],
        policy_fingerprint=output["policy_fingerprint"],
        allocation_fingerprint=output["allocation_fingerprint"],
        orchestration_fingerprint=output["orchestration_fingerprint"],
        ruleset_fingerprint=output["ruleset_fingerprint"],
        decision_fingerprint=output["decision_fingerprint"],
        decision_payload=service._json_value(output),
        idempotency_key="action-plan-request",
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

    def add(self, item):
        self.added.append(item)

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1

    async def refresh(self, item):
        item.id = 41
        item.created_at = NOW


def test_historical_reader_uses_only_frozen_payload(monkeypatch) -> None:
    decision = _decision()

    def must_not_run(*_args, **_kwargs):
        raise AssertionError("historical Action Plan must never be recalculated")

    monkeypatch.setattr(service, "calculate_action_plan", must_not_run)
    result = service._decision_read(decision)
    assert result["action_plan_id"] == 41
    assert result["actions"] == decision.decision_payload["actions"]


@pytest.mark.parametrize(
    ("field", "value"),
    [("status", "BLOCKED"), ("total_investment_actions", "0.01")],
)
def test_historical_reader_detects_indexed_tampering(field: str, value) -> None:
    decision = _decision()
    decision.decision_payload = deepcopy(decision.decision_payload)
    decision.decision_payload[field] = value
    with pytest.raises(state_service.FinancialStateValidationError, match="immutable contract"):
        service._decision_read(decision)


def test_historical_reader_detects_nested_action_tampering() -> None:
    decision = _decision()
    decision.decision_payload = deepcopy(decision.decision_payload)
    decision.decision_payload["actions"][0]["title"] = "tampered"
    with pytest.raises(state_service.FinancialStateValidationError, match="fingerprint"):
        service._decision_read(decision)


@pytest.mark.asyncio
async def test_current_uses_one_exact_source_chain(monkeypatch) -> None:
    inputs, state, policy, _ = _chain()
    state = deepcopy(state)
    state.pop("snapshot_id")
    policy = deepcopy(policy)
    policy["policy_id"] = None
    policy["financial_state_snapshot_id"] = None
    policy["source_financial_state"]["snapshot_id"] = None
    orchestration = deepcopy(_orchestration())
    orchestration["financial_state_snapshot_id"] = None
    orchestration["financial_policy_decision_id"] = None
    orchestration["capital_allocation_decision_id"] = None
    calls = []

    async def source_context(_session, **kwargs):
        calls.append(kwargs)
        return state, policy, inputs

    async def evaluate(*_args, **_kwargs):
        return orchestration

    monkeypatch.setattr(policy_service, "current_financial_policy_source_context", source_context)
    monkeypatch.setattr(orchestration_service, "_evaluate", evaluate)
    result = await service.current_action_plan(
        object(), household_id=10, user_id=91, evaluated_at=NOW
    )
    assert calls == [{"household_id": 10, "user_id": 91, "evaluated_at": NOW}]
    assert result["engine_version"] == "action-plan-v1"


@pytest.mark.asyncio
async def test_idempotent_retry_returns_before_freezing_orchestration(monkeypatch) -> None:
    decision = _decision()

    async def access(*_args, **_kwargs):
        return None

    async def existing(*_args, **_kwargs):
        return decision

    async def must_not_create(*_args, **_kwargs):
        raise AssertionError("retry must not create another A1-A4 chain")

    monkeypatch.setattr(state_service, "get_household_access", access)
    monkeypatch.setattr(service, "_decision_by_idempotency", existing)
    monkeypatch.setattr(
        orchestration_service, "create_investment_orchestration_decision", must_not_create
    )
    result = await service.create_action_plan_decision(
        object(), household_id=10, user_id=91, idempotency_key="action-plan-request"
    )
    assert result["action_plan_id"] == 41


@pytest.mark.asyncio
async def test_freeze_persists_exact_chain_and_zero_speculation(monkeypatch) -> None:
    state, policy, allocation, orchestration = _frozen_chain()
    session = _Session()

    async def access(*_args, **_kwargs):
        return None

    async def no_existing(*_args, **_kwargs):
        return None

    async def freeze_orchestration(*_args, **_kwargs):
        return orchestration

    async def chain(*_args, **_kwargs):
        return state, policy, allocation, orchestration

    monkeypatch.setattr(state_service, "get_household_access", access)
    monkeypatch.setattr(service, "_decision_by_idempotency", no_existing)
    monkeypatch.setattr(service, "_decision_by_orchestration", no_existing)
    monkeypatch.setattr(
        orchestration_service,
        "create_investment_orchestration_decision",
        freeze_orchestration,
    )
    monkeypatch.setattr(service, "_chain_from_orchestration", chain)
    result = await service.create_action_plan_decision(
        session,
        household_id=10,
        user_id=91,
        idempotency_key="action-plan-request",
    )
    stored = session.added[0]
    assert result["action_plan_id"] == 41
    assert stored.investment_orchestration_decision_id == 31
    assert stored.speculative_capital == 0
    assert stored.total_investment_actions <= stored.suggested_capital
    assert stored.total_investment_actions + stored.total_hold_cash <= stored.investment_budget
    assert session.commits == 1


@pytest.mark.asyncio
async def test_history_and_detail_authorize_without_replaying(monkeypatch) -> None:
    decision = _decision()
    accesses = []

    async def access(*_args, **kwargs):
        accesses.append(kwargs)

    monkeypatch.setattr(state_service, "get_household_access", access)
    history = await service.action_plan_history(
        _Session([_ScalarResult(one=1), _ScalarResult(items=[decision])]),
        household_id=10,
        user_id=91,
        limit=20,
        offset=0,
    )
    detail = await service.get_action_plan_decision(
        _Session([_ScalarResult(one=decision)]),
        household_id=10,
        action_plan_id=41,
        user_id=91,
    )
    assert history["total"] == 1
    assert history["items"][0]["primary_action"] == decision.decision_payload[
        "summary"
    ]["primary_action"]
    assert history["items"][0]["action_titles"] == [
        item["title"] for item in decision.decision_payload["actions"][:3]
    ]
    assert history["items"][0]["investment_budget"] == decision.investment_budget
    assert detail["action_plan_id"] == 41
    assert accesses == [
        {"household_id": 10, "user_id": 91},
        {"household_id": 10, "user_id": 91},
    ]
