from __future__ import annotations

from copy import deepcopy
from decimal import Decimal

import pytest

from backend.app.action_plan.engine import calculate_action_plan
from backend.app.action_plan.rules import ENGINE_VERSION, RULES_VERSION
from backend.app.action_plan.schemas import ActionPlanRead
from backend.app.capital_allocation.engine import (
    calculate_capital_allocation,
    decision_fingerprint_from_payload as allocation_fingerprint,
)
from backend.app.financial_policy.engine import (
    decision_fingerprint_from_payload as policy_fingerprint,
)
from backend.app.investment_orchestrator.engine import (
    calculate_investment_orchestration,
    decision_fingerprint_from_payload as orchestration_fingerprint,
)
from backend.tests.test_autopilot_investment_orchestrator_engine import (
    NOW,
    _candidate,
    _chain,
    _market,
    _portfolio,
    _profile,
    _run,
)


def _plan():
    state, policy, allocation = _chain()
    orchestration = _run()
    return calculate_action_plan(state, policy, allocation, orchestration)


def _complete_chain():
    state, policy, _ = _chain()
    policy = deepcopy(policy)
    policy["missing_information"] = []
    policy["decision_fingerprint"] = policy_fingerprint(policy)
    allocation = calculate_capital_allocation(state, policy)
    orchestration = calculate_investment_orchestration(
        state,
        policy,
        allocation,
        profile_context=_profile(),
        portfolio_context=_portfolio(),
        market_context=_market(_candidate()),
        generated_at=NOW,
    )
    return state, policy, allocation, orchestration


def test_ready_plan_is_versioned_deterministic_and_conservative() -> None:
    state, policy, allocation = _chain()
    orchestration = _run()
    first = calculate_action_plan(state, policy, allocation, orchestration)
    second = calculate_action_plan(state, policy, allocation, orchestration)

    assert first == second
    assert first["engine_version"] == ENGINE_VERSION
    assert first["rules_version"] == RULES_VERSION
    # The canonical fixture intentionally carries contextual information gaps.
    assert first["status"] == "PARTIAL"
    assert first["total_investment_actions"] <= orchestration["suggested_capital"]
    assert (
        first["total_investment_actions"] + first["total_hold_cash"]
        <= orchestration["investment_budget"]
    )
    assert first["speculative_capital"] == 0
    assert first["trading_dispatch"] is False
    ActionPlanRead.model_validate(first)


def test_complete_canonical_chain_is_ready() -> None:
    result = calculate_action_plan(*_complete_chain())
    assert result["status"] == "READY"
    assert result["missing_information"] == []


def test_valid_chain_with_no_emitted_actions_is_no_action_required(monkeypatch) -> None:
    state, policy, allocation, orchestration = _complete_chain()
    monkeypatch.setattr(
        "backend.app.action_plan.engine._investment_actions",
        lambda *_args, **_kwargs: [],
    )
    result = calculate_action_plan(state, policy, allocation, orchestration)
    assert result["status"] == "NO_ACTION_REQUIRED"
    assert result["actions"][0]["action_type"] == "NO_ACTION"


@pytest.mark.parametrize(
    ("upstream", "expected"),
    [("BUY", "INVESTMENT_BUY"), ("WAIT", "INVESTMENT_WAIT"), ("AVOID", "INVESTMENT_AVOID")],
)
def test_investment_semantics_are_preserved(upstream: str, expected: str) -> None:
    state, policy, allocation = _chain()
    orchestration = deepcopy(_run())
    opportunity = orchestration["ranked_opportunities"][0]
    opportunity["action"] = upstream
    if upstream != "BUY":
        opportunity["capital_committed"] = Decimal("0.00")
        orchestration["suggested_capital"] = Decimal("0.00")
        orchestration["remaining_investment_cash"] = orchestration["investment_budget"]
    if upstream == "WAIT":
        opportunity["guardrail_status"] = "WARNING"
    elif upstream == "AVOID":
        opportunity["guardrail_status"] = "BLOCKED"
    orchestration["decision_fingerprint"] = orchestration_fingerprint(orchestration)

    result = calculate_action_plan(state, policy, allocation, orchestration)

    assert result["investment_actions"][0]["action_type"] == expected
    if upstream != "BUY":
        assert result["investment_actions"][0]["amount"] is None


def test_guardrail_conflict_never_becomes_buy() -> None:
    state, policy, allocation = _chain()
    orchestration = deepcopy(_run())
    orchestration["ranked_opportunities"][0]["guardrail_status"] = "BLOCKED"
    orchestration["ranked_opportunities"][0]["capital_committed"] = Decimal("0.00")
    orchestration["suggested_capital"] = Decimal("0.00")
    orchestration["remaining_investment_cash"] = orchestration["investment_budget"]
    orchestration["decision_fingerprint"] = orchestration_fingerprint(orchestration)

    result = calculate_action_plan(state, policy, allocation, orchestration)

    assert result["investment_actions"][0]["action_type"] == "INVESTMENT_AVOID"
    assert result["investment_actions"][0]["amount"] is None


def test_financial_actions_copy_allocation_amount_and_ownership() -> None:
    state, policy, allocation = _chain()
    allocation = deepcopy(allocation)
    allocation["allocations"].insert(
        0,
        {
            "priority_code": "BUILD_EMERGENCY_RESERVE",
            "priority_rank": 1,
            "bucket_type": "PROTECTED_CAPITAL",
            "target_type": "EMERGENCY_RESERVE",
            "target_id": 77,
            "target_name": "Reserva compartilhada",
            "ownership_scope": "HOUSEHOLD",
            "user_id": 1,
            "requested_amount": Decimal("700.00"),
            "allocated_amount": Decimal("600.00"),
            "remaining_need": Decimal("100.00"),
            "status": "PARTIALLY_FUNDED",
            "reason": "Valor já decidido pela Allocation.",
            "evidence_refs": ["RESERVE_GAP"],
        },
    )
    allocation["decision_fingerprint"] = allocation_fingerprint(allocation)
    orchestration = deepcopy(_run(allocation=allocation))

    result = calculate_action_plan(state, policy, allocation, orchestration)

    reserve = next(
        item
        for item in result["financial_actions"]
        if item["action_type"] == "EMERGENCY_RESERVE_CONTRIBUTION"
    )
    assert reserve["amount"] == Decimal("600.00")
    assert reserve["remaining_need"] == Decimal("100.00")
    assert reserve["ownership_scope"] == "HOUSEHOLD"
    assert reserve["owner_user_id"] == 1


@pytest.mark.parametrize(
    ("target_type", "action_type", "scope", "owner_user_id"),
    [
        ("CASH_FLOW", "STABILIZE_CASHFLOW", "HOUSEHOLD", None),
        ("LIABILITY", "DEBT_PAYMENT", "PERSONAL", 1),
    ],
)
def test_cashflow_and_debt_actions_copy_upstream_values(
    target_type: str,
    action_type: str,
    scope: str,
    owner_user_id: int | None,
) -> None:
    state, policy, allocation = _chain()
    allocation = deepcopy(allocation)
    allocation["allocations"].insert(
        0,
        {
            "priority_code": (
                "STABILIZE_CASH_FLOW"
                if target_type == "CASH_FLOW"
                else "REDUCE_DEBT_BURDEN"
            ),
            "priority_rank": 1,
            "bucket_type": "PROTECTED_CAPITAL",
            "target_type": target_type,
            "target_id": 77 if target_type == "LIABILITY" else None,
            "target_name": "Origem canônica",
            "ownership_scope": scope,
            "user_id": owner_user_id,
            "requested_amount": Decimal("200.00"),
            "allocated_amount": Decimal("125.00"),
            "remaining_need": Decimal("75.00"),
            "status": "PARTIALLY_FUNDED",
            "reason": "Valor decidido pela Allocation.",
            "evidence_refs": ["UPSTREAM_VALUE"],
        },
    )
    allocation["decision_fingerprint"] = allocation_fingerprint(allocation)
    orchestration = _run(allocation=allocation)

    result = calculate_action_plan(state, policy, allocation, orchestration)
    item = next(
        action for action in result["financial_actions"]
        if action["action_type"] == action_type
    )

    assert item["amount"] == Decimal("125.00")
    assert item["remaining_need"] == Decimal("75.00")
    assert item["ownership_scope"] == scope
    assert item["owner_user_id"] == owner_user_id


def test_investment_actions_do_not_invent_household_ownership() -> None:
    state, policy, allocation = _chain()
    orchestration = _run()
    result = calculate_action_plan(state, policy, allocation, orchestration)
    assert allocation["allocations"][-1]["target_type"] == "INVESTMENT"
    assert allocation["allocations"][-1]["ownership_scope"] is None
    assert result["investment_actions"][0]["ownership_scope"] is None
    assert result["investment_actions"][0]["owner_user_id"] is None


def test_equal_upstream_ranks_keep_source_order_in_all_views() -> None:
    state, policy, allocation = _chain()
    allocation = deepcopy(allocation)
    allocation["allocations"] = [
        {
            "priority_code": "FUND_PRIORITY_GOAL",
            "priority_rank": 1,
            "bucket_type": "GOAL_CAPITAL",
            "target_type": "GOAL",
            "target_id": 3,
            "target_name": "Primeiro objetivo",
            "ownership_scope": "PERSONAL",
            "user_id": 1,
            "requested_amount": Decimal("100.00"),
            "allocated_amount": Decimal("0.00"),
            "remaining_need": Decimal("100.00"),
            "status": "UNFUNDED",
            "reason": "Primeiro na ordem canônica.",
            "evidence_refs": [],
        },
        {
            "priority_code": "FUND_PRIORITY_GOAL",
            "priority_rank": 1,
            "bucket_type": "GOAL_CAPITAL",
            "target_type": "GOAL",
            "target_id": 20,
            "target_name": "Segundo objetivo",
            "ownership_scope": "HOUSEHOLD",
            "user_id": None,
            "requested_amount": Decimal("100.00"),
            "allocated_amount": Decimal("0.00"),
            "remaining_need": Decimal("100.00"),
            "status": "UNFUNDED",
            "reason": "Segundo na ordem canônica.",
            "evidence_refs": [],
        },
        allocation["allocations"][-1],
    ]
    allocation["decision_fingerprint"] = allocation_fingerprint(allocation)
    orchestration = _run(allocation=allocation)
    result = calculate_action_plan(state, policy, allocation, orchestration)
    goal_titles = [
        item["title"]
        for item in result["financial_actions"]
        if item["action_type"] == "GOAL_CONTRIBUTION"
    ]
    assert goal_titles == ["Primeiro objetivo", "Segundo objetivo"]
    assert [item["priority_rank"] for item in result["financial_actions"]] == [1, 2]


def test_hold_cash_is_explicit_and_price_reference_is_frozen() -> None:
    state, policy, allocation = _chain()
    orchestration = deepcopy(_run())
    orchestration["ranked_opportunities"][0]["action"] = "WAIT"
    orchestration["ranked_opportunities"][0]["guardrail_status"] = "WARNING"
    orchestration["ranked_opportunities"][0]["capital_committed"] = Decimal("0.00")
    orchestration["suggested_capital"] = Decimal("0.00")
    orchestration["remaining_investment_cash"] = orchestration["investment_budget"]
    orchestration["decision_fingerprint"] = orchestration_fingerprint(orchestration)
    result = calculate_action_plan(state, policy, allocation, orchestration)
    assert result["total_hold_cash"] == orchestration["remaining_investment_cash"]
    assert result["hold_actions"][0]["action_type"] == "HOLD_CASH"
    wait = result["investment_actions"][0]
    assert wait["price_reference"] == Decimal("100.00")
    assert wait["price_timestamp"] is not None


def test_chain_and_fingerprint_tampering_block_the_plan() -> None:
    state, policy, allocation = _chain()
    orchestration = deepcopy(_run())
    orchestration["household_id"] = 999
    result = calculate_action_plan(state, policy, allocation, orchestration)
    assert result["status"] == "BLOCKED"
    assert result["actions"] == []
    assert any(item["code"] == "HOUSEHOLD_CHAIN_MISMATCH" for item in result["blockers"])

    orchestration = deepcopy(_run())
    orchestration["decision_fingerprint"] = "0" * 64
    result = calculate_action_plan(state, policy, allocation, orchestration)
    assert result["status"] == "BLOCKED"
    assert any(item["code"] == "ORCHESTRATION_FINGERPRINT_INVALID" for item in result["blockers"])

    orchestration = deepcopy(_run())
    orchestration["household_id"] = None
    orchestration["decision_fingerprint"] = orchestration_fingerprint(orchestration)
    result = calculate_action_plan(state, policy, allocation, orchestration)
    assert result["status"] == "BLOCKED"
    assert any(item["code"] == "HOUSEHOLD_CHAIN_MISMATCH" for item in result["blockers"])


def test_ruleset_tampering_and_missing_fingerprint_block_the_plan() -> None:
    state, policy, allocation = _chain()
    orchestration = deepcopy(_run())
    orchestration["rules_version"] = "evil-rules-v99"
    orchestration["decision_fingerprint"] = orchestration_fingerprint(orchestration)
    result = calculate_action_plan(state, policy, allocation, orchestration)
    assert result["status"] == "BLOCKED"
    assert any(
        item["code"] == "ORCHESTRATION_RULES_VERSION_INVALID"
        for item in result["blockers"]
    )

    orchestration = deepcopy(_run())
    orchestration.pop("decision_fingerprint")
    result = calculate_action_plan(state, policy, allocation, orchestration)
    assert result["status"] == "BLOCKED"
    assert result["orchestration_fingerprint"] is None
    assert any(
        item["code"] == "ORCHESTRATION_FINGERPRINT_REQUIRED"
        for item in result["blockers"]
    )


def test_period_ownership_and_persistence_mode_mismatches_block() -> None:
    state, policy, allocation = _chain()

    weekly = deepcopy(allocation)
    weekly["allocation_period"] = "WEEKLY"
    weekly["decision_fingerprint"] = allocation_fingerprint(weekly)
    weekly_orchestration = _run(allocation=weekly)
    result = calculate_action_plan(state, policy, weekly, weekly_orchestration)
    assert result["status"] == "BLOCKED"
    assert result["period"] is None
    assert any(
        item["code"] == "ALLOCATION_PERIOD_MISMATCH"
        for item in result["blockers"]
    )

    ownerless = deepcopy(allocation)
    ownerless["allocations"][-1]["ownership_scope"] = "PERSONAL"
    ownerless["allocations"][-1]["user_id"] = None
    ownerless["decision_fingerprint"] = allocation_fingerprint(ownerless)
    ownerless_orchestration = _run(allocation=ownerless)
    result = calculate_action_plan(state, policy, ownerless, ownerless_orchestration)
    assert result["status"] == "BLOCKED"
    assert any(item["code"] == "PERSONAL_OWNER_REQUIRED" for item in result["blockers"])

    mixed_state = deepcopy(state)
    mixed_policy = deepcopy(policy)
    mixed_allocation = deepcopy(allocation)
    mixed_orchestration = deepcopy(_run())
    mixed_policy["policy_id"] = 10
    mixed_allocation["financial_policy_id"] = 10
    mixed_allocation["allocation_id"] = 20
    mixed_orchestration["financial_policy_decision_id"] = 10
    mixed_orchestration["capital_allocation_decision_id"] = 20
    mixed_orchestration["orchestration_id"] = 30
    mixed_policy["decision_fingerprint"] = policy_fingerprint(mixed_policy)
    mixed_allocation["policy_fingerprint"] = mixed_policy["decision_fingerprint"]
    mixed_allocation["decision_fingerprint"] = allocation_fingerprint(mixed_allocation)
    mixed_orchestration["policy_fingerprint"] = mixed_policy["decision_fingerprint"]
    mixed_orchestration["allocation_fingerprint"] = mixed_allocation[
        "decision_fingerprint"
    ]
    mixed_orchestration["decision_fingerprint"] = orchestration_fingerprint(
        mixed_orchestration
    )
    result = calculate_action_plan(
        mixed_state,
        mixed_policy,
        mixed_allocation,
        mixed_orchestration,
    )
    assert result["status"] == "BLOCKED"
    assert any(
        item["code"] == "CHAIN_PERSISTENCE_MODE_MISMATCH"
        for item in result["blockers"]
    )


def test_missing_money_and_currency_remain_unknown_in_blocked_output() -> None:
    state, policy, allocation = _chain()
    allocation = deepcopy(allocation)
    allocation["currency"] = None
    allocation["decision_fingerprint"] = allocation_fingerprint(allocation)
    orchestration = deepcopy(_run())
    orchestration["currency"] = None
    orchestration["investment_budget"] = None
    orchestration["suggested_capital"] = None
    orchestration["remaining_investment_cash"] = None
    orchestration["allocation_fingerprint"] = allocation["decision_fingerprint"]
    orchestration["decision_fingerprint"] = orchestration_fingerprint(orchestration)

    result = calculate_action_plan(state, policy, allocation, orchestration)

    assert result["status"] == "BLOCKED"
    assert result["currency"] is None
    assert result["summary"]["authorized_investment_capital"] is None
    ActionPlanRead.model_validate(result)


def test_critical_upstream_gate_without_actions_is_blocked_not_no_action(
    monkeypatch,
) -> None:
    state, policy, allocation = _chain()
    allocation = deepcopy(allocation)
    allocation["investment_bucket_amount"] = Decimal("0.00")
    allocation["allocated_capital"] = Decimal("0.00")
    allocation["remaining_capital"] = allocation["allocatable_capital"]
    allocation["bucket_totals"]["investment_capital"] = Decimal("0.00")
    allocation["allocations"] = []
    allocation["decision_fingerprint"] = allocation_fingerprint(allocation)
    orchestration = deepcopy(_run(allocation=allocation))
    orchestration["ranked_opportunities"] = []
    orchestration["suggested_capital"] = Decimal("0.00")
    orchestration["remaining_investment_cash"] = orchestration["investment_budget"]
    orchestration["blockers"] = [
        {
            "code": "CRITICAL_GATE",
            "message": "A cadeia anterior bloqueou novas ações.",
            "fields": ["investment_orchestration.status"],
            "rule_ids": ["IOV1-GATE-001"],
        }
    ]
    orchestration["decision_fingerprint"] = orchestration_fingerprint(orchestration)
    monkeypatch.setattr(
        "backend.app.action_plan.engine._information_actions",
        lambda *_args, **_kwargs: [],
    )
    monkeypatch.setattr(
        "backend.app.action_plan.engine._investment_actions",
        lambda *_args, **_kwargs: [],
    )

    result = calculate_action_plan(state, policy, allocation, orchestration)

    assert orchestration["status"] == "BLOCKED"
    assert result["status"] == "BLOCKED"
    assert result["actions"] == []


def test_missing_information_is_not_converted_to_zero() -> None:
    state, policy, allocation = _chain()
    orchestration = deepcopy(_run())
    orchestration["missing_information"] = [
        {
            "code": "INVESTMENT_HORIZON_REQUIRED",
            "message": "Informe o horizonte.",
            "fields": ["financial_profiles.investment_horizon"],
            "rule_ids": ["IOV1-PROFILE-001"],
        }
    ]
    orchestration["decision_fingerprint"] = orchestration_fingerprint(orchestration)

    result = calculate_action_plan(state, policy, allocation, orchestration)

    assert result["status"] == "PARTIAL"
    info = result["information_actions"][0]
    assert info["action_type"] == "COMPLETE_INFORMATION"
    assert info["amount"] is None


def test_same_frozen_chain_produces_same_fingerprint() -> None:
    first = _plan()
    second = _plan()
    assert first["decision_fingerprint"] == second["decision_fingerprint"]
