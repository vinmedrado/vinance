from __future__ import annotations

from copy import deepcopy
from decimal import Decimal

import pytest

from backend.app.capital_allocation.engine import calculate_capital_allocation
from backend.app.capital_allocation.rules import ENGINE_VERSION, RULES_VERSION
from backend.app.capital_allocation.schemas import CapitalAllocationRead
from backend.app.financial_policy.engine import (
    calculate_financial_policy,
    decision_fingerprint_from_payload as financial_policy_fingerprint_from_payload,
)
from backend.app.financial_state.engine import calculate_financial_state
from backend.tests.test_autopilot_financial_policy_engine import (
    NOW,
    _active_debt,
    _complete_inputs,
    _owned,
)


def _chain(inputs: dict) -> tuple[dict, dict, dict]:
    state = calculate_financial_state(inputs, evaluated_at=NOW)
    policy = calculate_financial_policy(state, normalized_inputs=inputs)
    return state, policy, calculate_capital_allocation(state, policy)


def _item(result: dict, code: str) -> dict:
    return next(item for item in result["allocations"] if item["priority_code"] == code)


def _refingerprint_policy(policy: dict) -> None:
    policy["decision_fingerprint"] = financial_policy_fingerprint_from_payload(policy)


def test_ready_state_allocates_only_proven_monthly_residual() -> None:
    state, policy, result = _chain(_complete_inputs())

    assert result["engine_version"] == ENGINE_VERSION == "capital-allocation-v1"
    assert result["rules_version"] == RULES_VERSION == "capital-allocation-rules-v1"
    assert result["allocation_period"] == "MONTHLY"
    assert result["allocation_status"] == "SURPLUS"
    assert result["allocatable_capital"] == state["metrics"]["investment_capacity"]
    assert result["investment_bucket_amount"] == Decimal("5000.00")
    assert result["bucket_totals"]["speculative_capital"] == Decimal("0.00")
    assert policy["investment_readiness"] == "READY"
    CapitalAllocationRead.model_validate(result)


def test_engine_is_deterministic_and_does_not_mutate_inputs() -> None:
    inputs = _complete_inputs()
    state = calculate_financial_state(inputs, evaluated_at=NOW)
    policy = calculate_financial_policy(state, normalized_inputs=inputs)
    original_state = deepcopy(state)
    original_policy = deepcopy(policy)

    first = calculate_capital_allocation(state, policy)
    second = calculate_capital_allocation(state, policy)

    assert first == second
    assert first["decision_fingerprint"] == second["decision_fingerprint"]
    assert state == original_state
    assert policy == original_policy


def test_total_assets_are_evidence_not_allocatable_cash() -> None:
    inputs = _complete_inputs()
    inputs["assets"][1]["current_value"] = Decimal("999999")
    state, _, result = _chain(inputs)

    assert state["metrics"]["total_assets"] > Decimal("900000")
    assert result["allocatable_capital"] == Decimal("5000.00")
    assert next(item for item in result["evidence"] if item["code"] == "TOTAL_ASSETS")[
        "value"
    ] == state["metrics"]["total_assets"]


def test_none_capacity_blocks_while_real_zero_is_constrained() -> None:
    state, policy, _ = _chain(_complete_inputs())
    unknown_state = deepcopy(state)
    unknown_policy = deepcopy(policy)
    unknown_state["metrics"]["investment_capacity"] = None
    for evidence in unknown_policy["evidence"]:
        if evidence["code"] == "INVESTMENT_CAPACITY":
            evidence["value"] = None
    _refingerprint_policy(unknown_policy)
    unknown = calculate_capital_allocation(unknown_state, unknown_policy)

    zero_state = deepcopy(state)
    zero_policy = deepcopy(policy)
    zero_state["metrics"]["investment_capacity"] = Decimal("0")
    for evidence in zero_policy["evidence"]:
        if evidence["code"] == "INVESTMENT_CAPACITY":
            evidence["value"] = Decimal("0")
    zero_policy["investment_readiness"] = "BLOCKED"
    _refingerprint_policy(zero_policy)
    zero = calculate_capital_allocation(zero_state, zero_policy)

    assert unknown["allocation_status"] == "BLOCKED"
    assert unknown["allocatable_capital"] is None
    assert zero["allocation_status"] == "CONSTRAINED"
    assert zero["allocatable_capital"] == Decimal("0.00")
    assert zero["remaining_capital"] == Decimal("0.00")


@pytest.mark.parametrize("quality", ["INSUFFICIENT", "INCONSISTENT"])
def test_unsafe_state_quality_blocks_allocation(quality: str) -> None:
    state, policy, _ = _chain(_complete_inputs())
    state["data_quality"] = quality
    policy["source_financial_state"]["data_quality"] = quality

    result = calculate_capital_allocation(state, policy)

    assert result["allocation_status"] == "BLOCKED"
    assert result["allocatable_capital"] is None
    assert result["allocated_capital"] == Decimal("0.00")


@pytest.mark.parametrize("quality", ["PARTIAL", "STALE"])
def test_noncritical_partial_or_stale_data_is_explicitly_limited(quality: str) -> None:
    state, policy, _ = _chain(_complete_inputs())
    state["data_quality"] = quality
    policy["source_financial_state"]["data_quality"] = quality

    result = calculate_capital_allocation(state, policy)

    assert result["data_gate"]["status"] == "LIMITED"
    assert any(item["code"] == "SOURCE_DATA_LIMITED" for item in result["warnings"])


def test_critical_stale_data_blocks() -> None:
    state, policy, _ = _chain(_complete_inputs())
    policy["data_gate"]["critical_stale_fields"] = ["incomes"]

    result = calculate_capital_allocation(state, policy)

    assert result["allocation_status"] == "BLOCKED"
    assert result["data_gate"]["critical_stale_fields"] == ["incomes"]


def test_incompatible_currency_blocks_without_fx_conversion() -> None:
    state, policy, _ = _chain(_complete_inputs())
    policy["data_gate"]["currencies"] = ["BRL", "USD"]

    result = calculate_capital_allocation(state, policy)

    assert result["allocation_status"] == "BLOCKED"
    assert any(item["code"] == "CURRENCY_CONVERSION_MISSING" for item in result["blockers"])


def test_mismatched_household_or_snapshot_chain_blocks() -> None:
    state, policy, _ = _chain(_complete_inputs())
    state["snapshot_id"] = 1
    policy["financial_state_snapshot_id"] = 2

    result = calculate_capital_allocation(state, policy)

    assert result["allocation_status"] == "BLOCKED"
    assert result["allocatable_capital"] is None
    assert result["remaining_capital"] is None
    assert result["data_gate"]["consistency_checks"]["source_chain_matches"] is False


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("snapshot_id", 99),
        ("evaluated_at", None),
        ("engine_version", None),
        ("data_quality", None),
        ("confidence", None),
    ],
)
def test_incomplete_or_mismatched_policy_source_reference_blocks(
    field: str, value: object
) -> None:
    state, policy, _ = _chain(_complete_inputs())
    policy["source_financial_state"][field] = value

    result = calculate_capital_allocation(state, policy)

    assert result["allocation_status"] == "BLOCKED"
    assert result["data_gate"]["consistency_checks"]["source_chain_matches"] is False


def test_non_hex_policy_fingerprint_blocks_source_chain() -> None:
    state, policy, _ = _chain(_complete_inputs())
    policy["decision_fingerprint"] = "z" * 64

    result = calculate_capital_allocation(state, policy)

    assert result["allocation_status"] == "BLOCKED"
    assert result["data_gate"]["consistency_checks"]["source_chain_matches"] is False


def test_semantically_tampered_policy_with_old_fingerprint_blocks() -> None:
    state, policy, _ = _chain(_complete_inputs())
    policy["summary"] = "Conteúdo adulterado depois da decisão."

    result = calculate_capital_allocation(state, policy)

    assert result["allocation_status"] == "BLOCKED"
    assert result["allocatable_capital"] is None
    assert result["data_gate"]["consistency_checks"]["source_chain_matches"] is False


def test_negative_cashflow_precedes_investment_and_keeps_deficit_positive() -> None:
    inputs = _complete_inputs()
    inputs["expenses"][0]["amount"] = Decimal("9000")
    state, policy, result = _chain(inputs)
    recovery = _item(result, "STABILIZE_CASH_FLOW")

    assert state["metrics"]["disposable_income"] < 0
    assert policy["policy_state"] == "CASHFLOW_RECOVERY"
    assert recovery["requested_amount"] > 0
    assert recovery["allocated_amount"] == 0
    assert result["investment_bucket_amount"] == 0
    assert result["allocation_status"] == "CONSTRAINED"


def test_zero_cashflow_does_not_manufacture_a_recovery_target() -> None:
    inputs = _complete_inputs()
    inputs["expenses"][0]["amount"] = Decimal("7000")
    _, policy, result = _chain(inputs)

    assert policy["policy_state"] == "CASHFLOW_RECOVERY"
    assert _item(result, "STABILIZE_CASH_FLOW")["requested_amount"] == Decimal("0.00")
    assert result["investment_bucket_amount"] == 0


@pytest.mark.parametrize("rate", [None, Decimal("20")])
def test_prioritized_debt_uses_known_balance_without_inventing_rate(rate: Decimal | None) -> None:
    inputs = _complete_inputs()
    inputs["liabilities"] = [
        _active_debt(
            rate=rate,
            payment=Decimal("2000") if rate is None else Decimal("100"),
            balance=Decimal("1000"),
        )
    ]
    _, policy, result = _chain(inputs)
    debt = _item(result, "REDUCE_DEBT_BURDEN")

    assert policy["debt_policy"]["priority_required"] is True
    assert debt["requested_amount"] == Decimal("1000.00")
    assert debt["allocated_amount"] <= result["allocatable_capital"]
    if rate is None:
        assert "taxa é desconhecida" in debt["reason"]


def test_monthly_debt_service_is_not_allocated_twice() -> None:
    inputs = _complete_inputs()
    inputs["liabilities"] = [
        _active_debt(rate=Decimal("20"), payment=Decimal("500"), balance=Decimal("1000"))
    ]
    state, _, result = _chain(inputs)

    assert state["metrics"]["investment_capacity"] == Decimal("4500.00")
    assert _item(result, "REDUCE_DEBT_BURDEN")["requested_amount"] == Decimal("1000.00")


def test_missing_debt_balance_is_not_treated_as_zero() -> None:
    state, policy, _ = _chain(_complete_inputs())
    policy["priority_stack"] = [
        {"rank": 1, "code": "REDUCE_DEBT_BURDEN", "evidence_refs": []},
        {"rank": 2, "code": "INVEST_SURPLUS_CAPITAL", "evidence_refs": []},
    ]
    policy["policy_state"] = "DEBT_PRIORITY"
    policy["investment_readiness"] = "BLOCKED"
    policy["debt_policy"]["debts"] = [
        {
            "id": 9,
            "name": "Saldo desconhecido",
            "ownership_scope": "PERSONAL",
            "user_id": 1,
            "current_balance": None,
            "annual_interest_rate_pct": None,
        }
    ]
    _refingerprint_policy(policy)

    result = calculate_capital_allocation(state, policy)
    debt = _item(result, "REDUCE_DEBT_BURDEN")

    assert debt["requested_amount"] is None
    assert debt["status"] == "NOT_CALCULABLE"
    assert result["investment_bucket_amount"] == 0


def test_reserve_allocation_consumes_policy_gap_not_a_local_month_rule() -> None:
    inputs = _complete_inputs()
    inputs["assets"][0]["current_value"] = Decimal("0")
    state, policy, result = _chain(inputs)
    reserve = _item(result, "BUILD_EMERGENCY_RESERVE")

    assert policy["policy_state"] == "EMERGENCY_RESERVE_PRIORITY"
    assert reserve["requested_amount"] == policy["reserve_policy"]["gap_amount"]
    assert reserve["allocated_amount"] == result["allocatable_capital"]
    assert result["investment_bucket_amount"] == 0
    assert result["member_impacts"][0]["remaining_personal_capacity"] == (
        state["member_views"][0]["metrics"]["investment_capacity"]
        - reserve["allocated_amount"]
    )


def test_unknown_reserve_target_remains_not_calculable() -> None:
    state, policy, _ = _chain(_complete_inputs())
    policy["priority_stack"] = [
        {"rank": 1, "code": "BUILD_EMERGENCY_RESERVE", "evidence_refs": []},
        {"rank": 2, "code": "INVEST_SURPLUS_CAPITAL", "evidence_refs": []},
    ]
    policy["reserve_policy"]["gap_amount"] = None
    policy["investment_readiness"] = "LIMITED"
    _refingerprint_policy(policy)

    result = calculate_capital_allocation(state, policy)

    assert _item(result, "BUILD_EMERGENCY_RESERVE")["status"] == "NOT_CALCULABLE"
    assert result["investment_bucket_amount"] == 0


def _priority_goal(*, scope: str = "PERSONAL", deadline: str | None = "2026-12-08") -> dict:
    return {
        **_owned(30, scope=scope),
        "name": "Meta",
        "target_amount": Decimal("3000"),
        "current_amount": Decimal("0"),
        "deadline": deadline,
        "priority": "HIGH",
        "currency": "BRL",
        "status": "ACTIVE",
    }


@pytest.mark.parametrize("deadline", ["2026-12-08", None])
def test_goal_allocation_preserves_deadline_semantics(deadline: str | None) -> None:
    inputs = _complete_inputs()
    inputs["goals"] = [_priority_goal(deadline=deadline)]
    _, policy, result = _chain(inputs)
    goal = _item(result, "FUND_PRIORITY_GOAL")

    assert goal["ownership_scope"] == "PERSONAL"
    if deadline is None:
        assert goal["requested_amount"] == policy["goal_policy"]["goals"][0]["funding_gap"]
        assert any(item["code"] == "GOAL_PERIOD_UNKNOWN" for item in result["warnings"])
    else:
        assert goal["requested_amount"] == policy["goal_policy"]["goals"][0][
            "required_monthly_funding"
        ]


def test_multiple_goals_follow_policy_order_and_partial_funding() -> None:
    state, policy, _ = _chain(_complete_inputs())
    state["metrics"]["investment_capacity"] = Decimal("100.00")
    for evidence in policy["evidence"]:
        if evidence["code"] == "INVESTMENT_CAPACITY":
            evidence["value"] = Decimal("100.00")
    policy["priority_stack"] = [
        {"rank": 1, "code": "FUND_PRIORITY_GOAL", "evidence_refs": []},
        {"rank": 2, "code": "INVEST_SURPLUS_CAPITAL", "evidence_refs": []},
    ]
    policy["policy_state"] = "GOAL_PRIORITY"
    policy["investment_readiness"] = "LIMITED"
    policy["goal_policy"]["goals"] = [
        {
            "id": 1,
            "name": "Primeira",
            "ownership_scope": "PERSONAL",
            "user_id": 1,
            "deadline": "2026-12-01",
            "funding_gap": Decimal("1000"),
            "required_monthly_funding": Decimal("60"),
            "requires_priority": True,
        },
        {
            "id": 2,
            "name": "Segunda",
            "ownership_scope": "PERSONAL",
            "user_id": 1,
            "deadline": "2026-12-01",
            "funding_gap": Decimal("1000"),
            "required_monthly_funding": Decimal("60"),
            "requires_priority": True,
        },
    ]
    _refingerprint_policy(policy)

    result = calculate_capital_allocation(state, policy)
    goals = [item for item in result["allocations"] if item["target_type"] == "GOAL"]

    assert [item["target_id"] for item in goals] == [1, 2]
    assert [item["allocated_amount"] for item in goals] == [Decimal("60.00"), Decimal("40.00")]
    assert goals[1]["status"] == "PARTIALLY_FUNDED"
    assert result["investment_bucket_amount"] == 0


@pytest.mark.parametrize(
    ("readiness", "expected"),
    [("BLOCKED", Decimal("0.00")), ("LIMITED", Decimal("5000.00")), ("READY", Decimal("5000.00"))],
)
def test_investment_readiness_controls_only_the_residual_bucket(
    readiness: str, expected: Decimal
) -> None:
    state, policy, _ = _chain(_complete_inputs())
    policy["investment_readiness"] = readiness
    _refingerprint_policy(policy)

    result = calculate_capital_allocation(state, policy)

    assert result["investment_bucket_amount"] == expected


def test_decimal_rounding_down_preserves_conservation() -> None:
    state, policy, _ = _chain(_complete_inputs())
    state["metrics"]["investment_capacity"] = Decimal("1.239")
    state["metrics"]["savings_capacity"] = Decimal("2.00")
    for evidence in policy["evidence"]:
        if evidence["code"] == "INVESTMENT_CAPACITY":
            evidence["value"] = Decimal("1.239")
    _refingerprint_policy(policy)

    result = calculate_capital_allocation(state, policy)

    assert result["allocatable_capital"] == Decimal("1.23")
    assert result["allocated_capital"] == Decimal("1.23")
    assert result["remaining_capital"] == Decimal("0.00")


def test_personal_priority_cannot_consume_another_members_capacity() -> None:
    state, policy, _ = _chain(_complete_inputs())
    state["metrics"]["investment_capacity"] = Decimal("1000")
    state["metrics"]["savings_capacity"] = Decimal("1000")
    state["member_views"] = [
        {"user_id": 1, "full_name": "Ana", "metrics": {"investment_capacity": Decimal("100")}},
        {"user_id": 2, "full_name": "Beto", "metrics": {"investment_capacity": Decimal("900")}},
    ]
    for evidence in policy["evidence"]:
        if evidence["code"] == "INVESTMENT_CAPACITY":
            evidence["value"] = Decimal("1000")
    policy["priority_stack"] = [
        {"rank": 1, "code": "REDUCE_DEBT_BURDEN", "evidence_refs": []},
        {"rank": 2, "code": "INVEST_SURPLUS_CAPITAL", "evidence_refs": []},
    ]
    policy["policy_state"] = "DEBT_PRIORITY"
    policy["investment_readiness"] = "BLOCKED"
    policy["debt_policy"]["debts"] = [
        {
            "id": 1,
            "name": "Dívida Ana",
            "ownership_scope": "PERSONAL",
            "user_id": 1,
            "current_balance": Decimal("500"),
            "annual_interest_rate_pct": Decimal("20"),
        }
    ]
    _refingerprint_policy(policy)

    result = calculate_capital_allocation(state, policy)
    debt = _item(result, "REDUCE_DEBT_BURDEN")

    assert debt["allocated_amount"] == Decimal("100.00")
    assert result["remaining_capital"] == Decimal("900.00")
    assert result["member_impacts"][0]["remaining_personal_capacity"] == Decimal("0.00")
    assert result["member_impacts"][1]["remaining_personal_capacity"] == Decimal("900.00")


@pytest.mark.parametrize("beto_capacity", [Decimal("2000"), None])
def test_unreconciled_multi_member_capacities_block_implicit_transfer(
    beto_capacity: Decimal | None,
) -> None:
    state, policy, _ = _chain(_complete_inputs())
    state["metrics"]["investment_capacity"] = Decimal("1000")
    state["metrics"]["savings_capacity"] = Decimal("1000")
    state["member_views"] = [
        {
            "user_id": 1,
            "full_name": "Ana",
            "metrics": {"investment_capacity": Decimal("2000")},
        },
        {
            "user_id": 2,
            "full_name": "Beto",
            "metrics": {"investment_capacity": beto_capacity},
        },
    ]
    for evidence in policy["evidence"]:
        if evidence["code"] == "INVESTMENT_CAPACITY":
            evidence["value"] = Decimal("1000")
    policy["priority_stack"] = [
        {"rank": 1, "code": "REDUCE_DEBT_BURDEN", "evidence_refs": []},
        {"rank": 2, "code": "INVEST_SURPLUS_CAPITAL", "evidence_refs": []},
    ]
    policy["policy_state"] = "DEBT_PRIORITY"
    policy["investment_readiness"] = "BLOCKED"
    policy["debt_policy"]["debts"] = [
        {
            "id": 1,
            "name": "Dívida Ana",
            "ownership_scope": "PERSONAL",
            "user_id": 1,
            "current_balance": Decimal("1500"),
            "annual_interest_rate_pct": Decimal("20"),
        }
    ]
    _refingerprint_policy(policy)

    result = calculate_capital_allocation(state, policy)
    replay = calculate_capital_allocation(state, policy)

    assert result["allocation_status"] == "BLOCKED"
    assert result["data_gate"]["status"] == "BLOCKED"
    assert result["allocatable_capital"] is None
    assert result["allocated_capital"] == Decimal("0.00")
    assert result["remaining_capital"] is None
    assert _item(result, "REDUCE_DEBT_BURDEN")["allocated_amount"] == Decimal("0.00")
    assert any(
        item["code"] == "UNRECONCILED_CAPITAL_OWNERSHIP"
        for item in result["blockers"]
    )
    capital_trace = next(
        item for item in result["rules_evaluated"] if item["rule_id"] == "CAV1-CAPITAL-001"
    )
    ownership_trace = next(
        item for item in result["rules_evaluated"] if item["rule_id"] == "CAV1-OWN-001"
    )
    assert capital_trace["outcome"] == "NOT_EVALUATED"
    assert ownership_trace["outcome"] == "TRIGGERED"
    assert result["data_gate"]["consistency_checks"]["capital_conservation"] is True
    assert result["decision_fingerprint"] == replay["decision_fingerprint"]


def test_unknown_personal_capacity_prevents_implicit_transfer() -> None:
    state, policy, _ = _chain(_complete_inputs())
    state["member_views"][0]["metrics"]["investment_capacity"] = None
    policy["priority_stack"] = [
        {"rank": 1, "code": "FUND_PRIORITY_GOAL", "evidence_refs": []},
        {"rank": 2, "code": "INVEST_SURPLUS_CAPITAL", "evidence_refs": []},
    ]
    policy["investment_readiness"] = "LIMITED"
    policy["goal_policy"]["goals"] = [
        {
            "id": 1,
            "name": "Pessoal",
            "ownership_scope": "PERSONAL",
            "user_id": 1,
            "deadline": None,
            "funding_gap": Decimal("100"),
            "required_monthly_funding": None,
            "requires_priority": True,
        }
    ]

    result = calculate_capital_allocation(state, policy)

    assert _item(result, "FUND_PRIORITY_GOAL")["allocated_amount"] == 0
    assert result["investment_bucket_amount"] == 0


def test_unknown_member_pool_is_never_promoted_to_household_capital() -> None:
    state, policy, _ = _chain(_complete_inputs())
    state["metrics"]["investment_capacity"] = Decimal("1000")
    state["metrics"]["savings_capacity"] = Decimal("1000")
    state["member_views"] = [
        {"user_id": 1, "full_name": "Ana", "metrics": {"investment_capacity": None}},
        {
            "user_id": 2,
            "full_name": "Beto",
            "metrics": {"investment_capacity": Decimal("500")},
        },
    ]
    for evidence in policy["evidence"]:
        if evidence["code"] == "INVESTMENT_CAPACITY":
            evidence["value"] = Decimal("1000")
    policy["priority_stack"] = [
        {"rank": 1, "code": "BUILD_EMERGENCY_RESERVE", "evidence_refs": []},
        {"rank": 2, "code": "INVEST_SURPLUS_CAPITAL", "evidence_refs": []},
    ]
    policy["policy_state"] = "EMERGENCY_RESERVE_PRIORITY"
    policy["investment_readiness"] = "LIMITED"
    policy["reserve_policy"]["gap_amount"] = Decimal("500")
    _refingerprint_policy(policy)

    result = calculate_capital_allocation(state, policy)

    assert _item(result, "BUILD_EMERGENCY_RESERVE")["allocated_amount"] == 0
    assert result["investment_bucket_amount"] == 0
    assert result["remaining_capital"] == Decimal("1000.00")
    assert any(
        item["code"] == "CAPITAL_OWNERSHIP_BREAKDOWN_INCOMPLETE"
        for item in result["missing_information"]
    )


def test_single_member_uses_alias_only_when_aggregate_equals_personal_pool() -> None:
    state, policy, _ = _chain(_complete_inputs())
    state["metrics"]["investment_capacity"] = Decimal("1000")
    state["metrics"]["savings_capacity"] = Decimal("1000")
    state["member_views"] = [
        {
            "user_id": 1,
            "full_name": "Ana",
            "metrics": {"investment_capacity": Decimal("500")},
        }
    ]
    for evidence in policy["evidence"]:
        if evidence["code"] == "INVESTMENT_CAPACITY":
            evidence["value"] = Decimal("1000")
    policy["priority_stack"] = [
        {"rank": 1, "code": "BUILD_EMERGENCY_RESERVE", "evidence_refs": []},
        {"rank": 2, "code": "FUND_PRIORITY_GOAL", "evidence_refs": []},
        {"rank": 3, "code": "INVEST_SURPLUS_CAPITAL", "evidence_refs": []},
    ]
    policy["policy_state"] = "GOAL_PRIORITY"
    policy["investment_readiness"] = "LIMITED"
    policy["reserve_policy"]["gap_amount"] = Decimal("800")
    policy["goal_policy"]["goals"] = [
        {
            "id": 1,
            "name": "Meta pessoal",
            "ownership_scope": "PERSONAL",
            "user_id": 1,
            "deadline": "2026-12-01",
            "funding_gap": Decimal("600"),
            "required_monthly_funding": Decimal("600"),
            "requires_priority": True,
        }
    ]
    _refingerprint_policy(policy)

    result = calculate_capital_allocation(state, policy)
    reserve = _item(result, "BUILD_EMERGENCY_RESERVE")
    goal = next(item for item in result["allocations"] if item["target_type"] == "GOAL")

    assert reserve["allocated_amount"] == Decimal("500.00")
    assert goal["allocated_amount"] == Decimal("500.00")
    assert result["member_impacts"][0]["remaining_personal_capacity"] == Decimal(
        "0.00"
    )
    assert result["allocated_capital"] == result["allocatable_capital"]


def test_removed_member_is_absent_from_allocation_impacts() -> None:
    state, policy, _ = _chain(_complete_inputs())
    state["member_views"] = [state["member_views"][0]]

    result = calculate_capital_allocation(state, policy)

    assert [item["user_id"] for item in result["member_impacts"]] == [1]


def test_invalid_priority_order_blocks_instead_of_reordering_policy() -> None:
    state, policy, _ = _chain(_complete_inputs())
    policy["priority_stack"] = [
        {"rank": 2, "code": "INVEST_SURPLUS_CAPITAL", "evidence_refs": []},
        {"rank": 1, "code": "BUILD_EMERGENCY_RESERVE", "evidence_refs": []},
    ]

    result = calculate_capital_allocation(state, policy)

    assert result["allocation_status"] == "BLOCKED"
    assert result["data_gate"]["consistency_checks"]["priority_order_valid"] is False


def test_duplicate_priority_code_blocks_without_allocating_target_twice() -> None:
    state, policy, _ = _chain(_complete_inputs())
    policy["priority_stack"] = [
        {"rank": 1, "code": "BUILD_EMERGENCY_RESERVE", "evidence_refs": []},
        {"rank": 2, "code": "BUILD_EMERGENCY_RESERVE", "evidence_refs": []},
        {"rank": 3, "code": "INVEST_SURPLUS_CAPITAL", "evidence_refs": []},
    ]

    result = calculate_capital_allocation(state, policy)

    assert result["allocation_status"] == "BLOCKED"
    assert result["allocated_capital"] == 0
    assert result["data_gate"]["consistency_checks"]["priority_order_valid"] is False


def test_missing_investment_priority_blocks_without_synthesizing_policy_item() -> None:
    state, policy, _ = _chain(_complete_inputs())
    policy["priority_stack"] = [
        {"rank": 1, "code": "BUILD_EMERGENCY_RESERVE", "evidence_refs": []}
    ]

    result = calculate_capital_allocation(state, policy)

    assert result["allocation_status"] == "BLOCKED"
    assert all(item["priority_code"] != "INVEST_SURPLUS_CAPITAL" for item in result["allocations"])


def test_missing_policy_capacity_evidence_blocks() -> None:
    state, policy, _ = _chain(_complete_inputs())
    policy["evidence"] = [
        item for item in policy["evidence"] if item["code"] != "INVESTMENT_CAPACITY"
    ]

    result = calculate_capital_allocation(state, policy)

    assert result["allocation_status"] == "BLOCKED"
    assert result["data_gate"]["consistency_checks"]["policy_capacity_matches_state"] is False


def test_invalid_ownership_blocks_instead_of_using_global_capital() -> None:
    state, policy, _ = _chain(_complete_inputs())
    policy["priority_stack"] = [
        {"rank": 1, "code": "REDUCE_DEBT_BURDEN", "evidence_refs": []},
        {"rank": 2, "code": "INVEST_SURPLUS_CAPITAL", "evidence_refs": []},
    ]
    policy["debt_policy"]["debts"] = [
        {
            "id": 1,
            "name": "Sem proprietário",
            "ownership_scope": None,
            "user_id": None,
            "current_balance": Decimal("100"),
            "annual_interest_rate_pct": Decimal("20"),
        }
    ]

    result = calculate_capital_allocation(state, policy)

    assert result["allocation_status"] == "BLOCKED"
    assert result["allocated_capital"] == 0
    assert any(item["code"] == "INVALID_FINANCIAL_OWNERSHIP" for item in result["blockers"])


def test_formal_conservation_invariants_hold_for_every_item() -> None:
    inputs = _complete_inputs()
    inputs["assets"][0]["current_value"] = Decimal("1000")
    _, _, result = _chain(inputs)

    assert all(item["allocated_amount"] >= 0 for item in result["allocations"])
    assert result["remaining_capital"] >= 0
    assert result["allocated_capital"] <= result["allocatable_capital"]
    assert result["allocated_capital"] + result["remaining_capital"] == result[
        "allocatable_capital"
    ]
    assert result["bucket_totals"]["speculative_capital"] == 0
