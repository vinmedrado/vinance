from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from backend.app.capital_allocation.engine import calculate_capital_allocation
from backend.app.financial_policy import service as policy_service
from backend.app.financial_policy.engine import calculate_financial_policy
from backend.app.financial_state import service as state_service
from backend.app.financial_state.engine import calculate_financial_state
from backend.app.investment_orchestrator import service
from backend.app.investment_orchestrator.engine import calculate_investment_orchestration
from backend.tests.test_autopilot_financial_policy_engine import _complete_inputs


NOW = datetime(2026, 9, 19, 12, 0, tzinfo=timezone.utc)


def _chain():
    inputs = _complete_inputs()
    state = calculate_financial_state(inputs, evaluated_at=NOW)
    state["snapshot_id"] = 7
    policy = calculate_financial_policy(state, normalized_inputs=inputs)
    policy.update(
        {"policy_id": 17, "financial_state_snapshot_id": 7, "created_at": NOW}
    )
    allocation = calculate_capital_allocation(state, policy)
    allocation.update({"allocation_id": 23, "created_at": NOW})
    return inputs, state, policy, allocation


def _orchestration():
    _, state, policy, allocation = _chain()
    return calculate_investment_orchestration(
        state,
        policy,
        allocation,
        profile_context={
            "status": "COMPLETE",
            "effective_profile": "MODERATE",
            "members": [{"user_id": 1, "profile": "MODERATE"}],
        },
        portfolio_context={
            "status": "COMPLETE",
            "positions": [],
            "concentration": [],
            "missing_information": [],
        },
        market_context={
            "captured_at": NOW,
            "status": "AVAILABLE",
            "markets": [
                {"market": "ACOES", "status": "AVAILABLE", "freshness_status": "FRESH"}
            ],
            "candidates": [
                {
                    "asset_id": 1,
                    "symbol": "TEST3",
                    "ticker": "TEST3",
                    "asset_class": "ACOES",
                    "market": "ACOES",
                    "price_reference": "100",
                    "quantity_candidate": 50,
                    "capital_required": "5000",
                    "recommendation_score": "80",
                    "risk_level": "LOW",
                    "guardrail_status": "APPROVED",
                    "reasons": [],
                    "warnings": [],
                    "freshness_status": "FRESH",
                }
            ],
            "partial_failures": [],
            "missing_information": [],
            "sources": {},
        },
        generated_at=NOW,
    )


def _decision():
    output = _orchestration()
    return SimpleNamespace(
        id=31,
        household_id=10,
        financial_state_snapshot_id=7,
        financial_policy_decision_id=17,
        capital_allocation_decision_id=23,
        created_by_user_id=91,
        engine_version=output["engine_version"],
        rules_version=output["rules_version"],
        status=output["status"],
        currency=output["currency"],
        investment_budget=output["investment_budget"],
        suggested_capital=output["suggested_capital"],
        remaining_investment_cash=output["remaining_investment_cash"],
        speculative_capital=output["speculative_capital"],
        state_fingerprint=output["state_fingerprint"],
        policy_fingerprint=output["policy_fingerprint"],
        allocation_fingerprint=output["allocation_fingerprint"],
        market_context_fingerprint=output["market_context_fingerprint"],
        ruleset_fingerprint=output["ruleset_fingerprint"],
        decision_fingerprint=output["decision_fingerprint"],
        decision_payload=service._json_value(output),
        idempotency_key="orchestration-request",
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
        item.id = 31
        item.created_at = NOW


def test_frozen_reader_never_recalculates_or_uses_live_market(monkeypatch) -> None:
    decision = _decision()

    def must_not_run(*_args, **_kwargs):
        raise AssertionError("historical read must remain frozen")

    monkeypatch.setattr(service, "calculate_investment_orchestration", must_not_run)
    result = service._decision_read(decision)
    assert result["orchestration_id"] == 31
    assert result["market_context"] == decision.decision_payload["market_context"]


@pytest.mark.parametrize(
    ("field", "value"), [("status", "BLOCKED"), ("suggested_capital", "0.01")]
)
def test_frozen_reader_detects_indexed_tampering(field: str, value) -> None:
    decision = _decision()
    decision.decision_payload = deepcopy(decision.decision_payload)
    decision.decision_payload[field] = value
    with pytest.raises(state_service.FinancialStateValidationError, match="immutable contract"):
        service._decision_read(decision)


def test_frozen_reader_detects_nested_market_tampering() -> None:
    decision = _decision()
    decision.decision_payload = deepcopy(decision.decision_payload)
    decision.decision_payload["market_context"]["status"] = "UNAVAILABLE"
    with pytest.raises(state_service.FinancialStateValidationError, match="fingerprint"):
        service._decision_read(decision)


@pytest.mark.asyncio
async def test_current_uses_one_exact_state_policy_source_context(monkeypatch) -> None:
    inputs, state, policy, _ = _chain()
    state = deepcopy(state)
    state.pop("snapshot_id")
    policy = deepcopy(policy)
    policy["policy_id"] = None
    policy["financial_state_snapshot_id"] = None
    policy["source_financial_state"]["snapshot_id"] = None
    calls = []

    async def source_context(_session, **kwargs):
        calls.append(kwargs)
        return state, policy, inputs

    async def profile(*_args, **_kwargs):
        return {"status": "MISSING", "effective_profile": None, "members": []}

    async def portfolio(*_args, **_kwargs):
        return {"status": "UNKNOWN", "positions": [], "concentration": []}

    monkeypatch.setattr(policy_service, "current_financial_policy_source_context", source_context)
    monkeypatch.setattr(service, "load_profile_context", profile)
    monkeypatch.setattr(service, "load_portfolio_context", portfolio)
    result = await service.current_investment_orchestration(
        object(), household_id=10, user_id=91, evaluated_at=NOW
    )
    assert calls == [{"household_id": 10, "user_id": 91, "evaluated_at": NOW}]
    assert result["status"] == "BLOCKED"


@pytest.mark.asyncio
async def test_idempotent_retry_returns_before_creating_allocation(monkeypatch) -> None:
    decision = _decision()

    async def access(*_args, **_kwargs):
        return None

    async def existing(*_args, **_kwargs):
        return decision

    async def must_not_create(*_args, **_kwargs):
        raise AssertionError("retry must not create A1-A3 decisions")

    monkeypatch.setattr(state_service, "get_household_access", access)
    monkeypatch.setattr(service, "_decision_by_idempotency", existing)
    monkeypatch.setattr(
        service.allocation_service, "create_capital_allocation_decision", must_not_create
    )
    result = await service.create_investment_orchestration_decision(
        object(), household_id=10, user_id=91, idempotency_key="orchestration-request"
    )
    assert result["orchestration_id"] == 31


@pytest.mark.asyncio
async def test_freeze_persists_exact_chain_and_zero_speculation(monkeypatch) -> None:
    output = _orchestration()
    _, state, policy, allocation = _chain()
    session = _Session()

    async def access(*_args, **_kwargs):
        return None

    async def no_existing(*_args, **_kwargs):
        return None

    async def freeze_allocation(*_args, **_kwargs):
        return allocation

    async def chain(*_args, **_kwargs):
        return state, policy, allocation, _complete_inputs()

    async def evaluate(*_args, **_kwargs):
        return output

    monkeypatch.setattr(state_service, "get_household_access", access)
    monkeypatch.setattr(service, "_decision_by_idempotency", no_existing)
    monkeypatch.setattr(service, "_decision_by_allocation", no_existing)
    monkeypatch.setattr(
        service.allocation_service,
        "create_capital_allocation_decision",
        freeze_allocation,
    )
    monkeypatch.setattr(service, "_chain_from_allocation", chain)
    monkeypatch.setattr(service, "_evaluate", evaluate)
    result = await service.create_investment_orchestration_decision(
        session,
        household_id=10,
        user_id=91,
        idempotency_key="orchestration-request",
    )
    stored = session.added[0]
    assert result["orchestration_id"] == 31
    assert stored.capital_allocation_decision_id == 23
    assert stored.investment_budget == allocation["investment_bucket_amount"]
    assert stored.speculative_capital == 0
    assert session.commits == 1


@pytest.mark.asyncio
async def test_history_and_detail_authorize_and_do_not_replay(monkeypatch) -> None:
    decision = _decision()
    accesses = []

    async def access(*_args, **kwargs):
        accesses.append(kwargs)

    monkeypatch.setattr(state_service, "get_household_access", access)
    history = await service.investment_orchestration_history(
        _Session([_ScalarResult(one=1), _ScalarResult(items=[decision])]),
        household_id=10,
        user_id=91,
        limit=20,
        offset=0,
    )
    detail = await service.get_investment_orchestration_decision(
        _Session([_ScalarResult(one=decision)]),
        household_id=10,
        orchestration_id=31,
        user_id=91,
    )
    assert history["total"] == 1
    assert detail["orchestration_id"] == 31
    assert accesses == [
        {"household_id": 10, "user_id": 91},
        {"household_id": 10, "user_id": 91},
    ]
