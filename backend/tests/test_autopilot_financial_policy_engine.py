from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from backend.app.financial_policy.engine import calculate_financial_policy
from backend.app.financial_policy.rules import ENGINE_VERSION, RULES_VERSION
from backend.app.financial_state.engine import calculate_financial_state


NOW = datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc)


def _owned(record_id: int, user_id: int = 1, scope: str = "PERSONAL") -> dict:
    return {
        "id": record_id,
        "household_id": 10,
        "user_id": user_id,
        "ownership_scope": scope,
        "updated_at": NOW,
    }


def _complete_inputs() -> dict:
    return {
        "household": {"id": 10, "name": "Casa", "household_type": "PERSONAL"},
        "members": [{"user_id": 1, "full_name": "Ana", "status": "ACTIVE"}],
        "incomes": [
            {
                **_owned(1),
                "amount": Decimal("8000"),
                "is_recurring": True,
                "received_at": "2026-09-05",
            },
            {
                **_owned(2),
                "amount": Decimal("500"),
                "is_recurring": False,
                "received_at": "2026-09-06",
            },
        ],
        "expenses": [
            {
                **_owned(1),
                "amount": Decimal("2000"),
                "expense_nature": "FIXED",
                "due_date": "2026-09-05",
            },
            {
                **_owned(2),
                "amount": Decimal("1000"),
                "expense_nature": "VARIABLE",
                "due_date": "2026-09-06",
            },
        ],
        "assets": [
            {
                **_owned(1),
                "asset_class": "EMERGENCY_RESERVE",
                "current_value": Decimal("9000"),
                "value_as_of": "2026-09-08",
                "currency": "BRL",
                "status": "ACTIVE",
            },
            {
                **_owned(2),
                "asset_class": "INVESTMENTS",
                "current_value": Decimal("1000"),
                "value_as_of": "2026-09-08",
                "currency": "BRL",
                "status": "ACTIVE",
            },
        ],
        "liabilities": [
            {
                **_owned(1),
                "name": "Quitada",
                "current_balance": Decimal("0"),
                "monthly_payment": Decimal("0"),
                "annual_interest_rate_pct": Decimal("0"),
                "due_date": None,
                "balance_as_of": "2026-09-08",
                "currency": "BRL",
                "status": "PAID",
            }
        ],
        "goals": [
            {
                **_owned(1),
                "name": "Objetivo concluído",
                "target_amount": Decimal("1000"),
                "current_amount": Decimal("1000"),
                "deadline": None,
                "priority": "LOW",
                "currency": "BRL",
                "status": "ACTIVE",
            }
        ],
        "financial_profiles": [],
    }


def _policy(inputs: dict) -> dict:
    state = calculate_financial_state(inputs, evaluated_at=NOW)
    return calculate_financial_policy(state, normalized_inputs=inputs)


def _active_debt(
    *,
    rate: Decimal | None = Decimal("1"),
    payment: Decimal = Decimal("100"),
    balance: Decimal = Decimal("1000"),
    status: str = "ACTIVE",
    due_date: str | None = None,
) -> dict:
    return {
        **_owned(1),
        "name": "Dívida",
        "current_balance": balance,
        "monthly_payment": payment,
        "annual_interest_rate_pct": rate,
        "due_date": due_date,
        "balance_as_of": "2026-09-08",
        "currency": "BRL",
        "status": status,
    }


def test_complete_safe_state_is_investment_ready_without_selecting_assets() -> None:
    result = _policy(_complete_inputs())

    assert result["engine_version"] == ENGINE_VERSION == "financial-policy-v1"
    assert result["rules_version"] == RULES_VERSION == "financial-policy-rules-v1"
    assert result["policy_state"] == "INVESTMENT_READY"
    assert result["investment_readiness"] == "READY"
    assert result["data_gate"]["status"] == "PASS"
    assert result["priority_stack"] == [
        {
            "code": "INVEST_SURPLUS_CAPITAL",
            "title": "Investir somente o capital excedente",
            "explanation": (
                "Esta etapa indica apenas prontidão financeira; ativos, mercados e "
                "quantidades não são escolhidos aqui."
            ),
            "status": "ACTIVE",
            "evidence_refs": ["INVESTMENT_CAPACITY"],
            "rank": 1,
        }
    ]


def test_engine_is_deterministic_and_does_not_mutate_either_input() -> None:
    inputs = _complete_inputs()
    state = calculate_financial_state(inputs, evaluated_at=NOW)
    original_inputs = deepcopy(inputs)
    original_state = deepcopy(state)

    first = calculate_financial_policy(state, normalized_inputs=inputs)
    second = calculate_financial_policy(state, normalized_inputs=inputs)

    assert first == second
    assert first["input_fingerprint"] == second["input_fingerprint"]
    assert inputs == original_inputs
    assert state == original_state


@pytest.mark.parametrize(
    ("rate", "expected_state", "expected_readiness"),
    [
        (Decimal("14.999999"), "INVESTMENT_READY", "READY"),
        (Decimal("15.000000"), "DEBT_PRIORITY", "BLOCKED"),
    ],
)
def test_known_high_cost_debt_threshold_is_exact(
    rate: Decimal, expected_state: str, expected_readiness: str
) -> None:
    inputs = _complete_inputs()
    inputs["liabilities"] = [_active_debt(rate=rate)]

    result = _policy(inputs)

    assert result["policy_state"] == expected_state
    assert result["investment_readiness"] == expected_readiness
    if rate >= Decimal("15"):
        assert result["explanations"][0]["rule_ids"] == ["FPV1-DEBT-002"]


@pytest.mark.parametrize(
    ("payment", "expected_state", "expected_readiness"),
    [
        (Decimal("1599.20"), "INVESTMENT_READY", "READY"),
        (Decimal("1600.00"), "DEBT_PRIORITY", "LIMITED"),
        (Decimal("2400.00"), "DEBT_PRIORITY", "BLOCKED"),
    ],
)
def test_debt_service_boundaries_are_versioned(
    payment: Decimal, expected_state: str, expected_readiness: str
) -> None:
    inputs = _complete_inputs()
    inputs["liabilities"] = [_active_debt(payment=payment)]
    inputs["assets"][0]["current_value"] = Decimal("18000")

    result = _policy(inputs)

    assert result["policy_state"] == expected_state
    assert result["investment_readiness"] == expected_readiness


def test_unknown_debt_rate_limits_readiness_without_inventing_cost() -> None:
    inputs = _complete_inputs()
    inputs["liabilities"] = [_active_debt(rate=None)]

    result = _policy(inputs)

    assert result["policy_state"] == "BALANCED_BUILD"
    assert result["investment_readiness"] == "LIMITED"
    assert result["debt_policy"]["debts"][0]["assessment"] == "UNKNOWN_COST"
    assert "ACTIVE_DEBT_RATE_UNKNOWN" in result["data_gate"].get(
        "readiness_limiters", []
    ) or any(item["code"] == "DEBT_RATE_UNKNOWN" for item in result["warnings"])
    assert "COMPLETE_READINESS_DATA" in {
        item["code"] for item in result["priority_stack"]
    }


def test_debt_order_uses_individual_monthly_pressure_before_identifier() -> None:
    inputs = _complete_inputs()
    low_payment = {**_active_debt(payment=Decimal("100")), "id": 1}
    high_payment = {**_active_debt(payment=Decimal("700")), "id": 99}
    inputs["liabilities"] = [low_payment, high_payment]
    inputs["assets"][0]["current_value"] = Decimal("18000")

    result = _policy(inputs)

    assert [item["id"] for item in result["debt_policy"]["debts"]] == [99, 1]
    assert result["debt_policy"]["debts"][0][
        "monthly_payment_share_pct"
    ] == Decimal("8.75")


def test_past_due_date_does_not_imply_default_or_high_cost() -> None:
    inputs = _complete_inputs()
    inputs["liabilities"] = [
        _active_debt(rate=Decimal("2"), due_date="2026-01-01")
    ]

    result = _policy(inputs)

    assert result["debt_policy"]["debts"][0]["assessment"] == "STANDARD_KNOWN_COST"
    assert result["debt_policy"]["debts"][0]["due_assessment"] == "DATE_PASSED_STATUS_ACTIVE"
    assert result["policy_state"] == "DEBT_PRIORITY"
    assert result["investment_readiness"] == "LIMITED"
    assert not result["debt_policy"]["investment_blocking"]


@pytest.mark.parametrize(("days", "prioritized"), [(90, True), (91, False)])
def test_debt_due_date_priority_boundary_is_exact(days: int, prioritized: bool) -> None:
    inputs = _complete_inputs()
    inputs["liabilities"] = [
        _active_debt(
            rate=Decimal("2"),
            due_date=(NOW.date() + timedelta(days=days)).isoformat(),
        )
    ]

    result = _policy(inputs)

    assert bool(result["debt_policy"]["due_priority_debt_ids"]) is prioritized


def test_explicit_zero_cash_capacity_is_not_missing_and_forces_recovery() -> None:
    inputs = _complete_inputs()
    inputs["incomes"][0]["amount"] = Decimal("3000")

    result = _policy(inputs)

    assert result["policy_state"] == "CASHFLOW_RECOVERY"
    assert result["investment_readiness"] == "BLOCKED"
    assert result["data_gate"]["critical_missing_fields"] == []
    assert any(item["code"] == "NO_INVESTMENT_CAPACITY" for item in result["blockers"])


def test_negative_consolidated_cashflow_and_disposable_income_force_recovery() -> None:
    inputs = _complete_inputs()
    inputs["incomes"][0]["amount"] = Decimal("2000")

    state = calculate_financial_state(inputs, evaluated_at=NOW)
    result = calculate_financial_policy(state, normalized_inputs=inputs)

    assert state["metrics"]["cash_flow"] == Decimal("-500.00")
    assert state["metrics"]["disposable_income"] == Decimal("-1000.00")
    assert result["policy_state"] == "CASHFLOW_RECOVERY"
    assert result["investment_readiness"] == "BLOCKED"
    assert result["explanations"][0]["rule_ids"] == ["FPV1-CASH-001"]


def test_missing_reserve_stays_unknown_while_real_zero_is_absent() -> None:
    missing = _complete_inputs()
    missing["assets"] = [missing["assets"][1]]
    explicit_zero = _complete_inputs()
    explicit_zero["assets"][0]["current_value"] = Decimal("0")

    unknown_policy = _policy(missing)
    zero_policy = _policy(explicit_zero)

    assert unknown_policy["reserve_policy"]["status"] == "UNKNOWN"
    assert unknown_policy["investment_readiness"] == "LIMITED"
    assert zero_policy["reserve_policy"]["status"] == "ABSENT"
    assert zero_policy["policy_state"] == "EMERGENCY_RESERVE_PRIORITY"
    assert zero_policy["investment_readiness"] == "BLOCKED"


def test_reserve_target_uses_only_known_context_and_caps_at_six_months() -> None:
    inputs = _complete_inputs()
    inputs["expenses"][0]["amount"] = Decimal("2100")
    inputs["expenses"][1]["amount"] = Decimal("900")
    inputs["incomes"][1]["amount"] = Decimal("2000")
    inputs["liabilities"] = [_active_debt(payment=Decimal("1600"))]
    inputs["assets"][0]["current_value"] = Decimal("18000")

    result = _policy(inputs)

    assert result["reserve_policy"]["target_months"] == Decimal("6.00")
    assert result["reserve_policy"]["target_method"] == (
        "PRUDENTIAL_FLOOR_PLUS_KNOWN_CONTEXT"
    )
    assert result["reserve_policy"]["universal_target_applied"] is False
    assert [item["code"] for item in result["reserve_policy"]["modifiers"]] == [
        "FIXED_EXPENSE_PRESSURE",
        "DEBT_SERVICE_PRESSURE",
        "NON_RECURRING_INCOME_DEPENDENCY",
    ]


@pytest.mark.parametrize(
    ("fixed", "variable", "target_months"),
    [
        (Decimal("2099.70"), Decimal("900.30"), Decimal("3.00")),
        (Decimal("2100.00"), Decimal("900.00"), Decimal("4.00")),
    ],
)
def test_fixed_expense_reserve_modifier_boundary_is_exact(
    fixed: Decimal, variable: Decimal, target_months: Decimal
) -> None:
    inputs = _complete_inputs()
    inputs["expenses"][0]["amount"] = fixed
    inputs["expenses"][1]["amount"] = variable
    inputs["assets"][0]["current_value"] = Decimal("30000")

    result = _policy(inputs)

    assert result["reserve_policy"]["target_months"] == target_months


@pytest.mark.parametrize(
    ("recurring", "non_recurring", "target_months"),
    [
        (Decimal("8001"), Decimal("1999"), Decimal("3.00")),
        (Decimal("8000"), Decimal("2000"), Decimal("4.00")),
    ],
)
def test_non_recurring_income_modifier_boundary_is_exact(
    recurring: Decimal, non_recurring: Decimal, target_months: Decimal
) -> None:
    inputs = _complete_inputs()
    inputs["incomes"][0]["amount"] = recurring
    inputs["incomes"][1]["amount"] = non_recurring
    inputs["assets"][0]["current_value"] = Decimal("30000")

    result = _policy(inputs)

    assert result["reserve_policy"]["target_months"] == target_months


def test_reserve_can_only_be_adequate_for_known_context_when_modifier_data_is_missing() -> None:
    inputs = _complete_inputs()
    inputs["liabilities"] = []

    result = _policy(inputs)

    assert result["reserve_policy"]["status"] == "ADEQUATE_FOR_KNOWN_CONTEXT"
    assert result["reserve_policy"]["target_completeness"] == "PARTIAL"
    assert result["investment_readiness"] == "BLOCKED"
    assert any(
        item["code"] == "INVESTMENT_CAPACITY_UNKNOWN"
        for item in result["blockers"]
    )


def test_high_priority_goal_without_deadline_is_prioritized_without_fake_date() -> None:
    inputs = _complete_inputs()
    inputs["goals"][0].update(
        {"current_amount": Decimal("0"), "priority": "HIGH", "deadline": None}
    )

    result = _policy(inputs)

    assert result["policy_state"] == "GOAL_PRIORITY"
    assert result["goal_policy"]["goals"][0]["deadline"] is None
    assert result["goal_policy"]["goals"][0]["days_remaining"] is None
    assert result["goal_policy"]["goals"][0]["requires_priority"] is True
    assert any(item["code"] == "GOAL_DEADLINE_UNKNOWN" for item in result["limitations"])


def test_goal_funding_pressure_uses_known_deadline_and_capacity() -> None:
    inputs = _complete_inputs()
    inputs["goals"][0].update(
        {
            "target_amount": Decimal("12000"),
            "current_amount": Decimal("0"),
            "priority": "MEDIUM",
            "deadline": (NOW.date() + timedelta(days=30)).isoformat(),
        }
    )

    result = _policy(inputs)
    goal = result["goal_policy"]["goals"][0]

    assert goal["required_monthly_funding"] == Decimal("12000.00")
    assert goal["available_monthly_capacity"] == Decimal("5000.00")
    assert goal["funding_feasibility"] == "EXCEEDS_CAPACITY"
    assert result["goal_policy"]["capacity_exceeded_goal_ids"] == [1]
    assert any(
        item["code"] == "GOAL_FUNDING_EXCEEDS_CAPACITY"
        for item in result["warnings"]
    )


def test_undeclared_goals_are_not_reported_as_evaluated() -> None:
    inputs = _complete_inputs()
    inputs["goals"] = []

    result = _policy(inputs)
    goal_traces = {
        item["rule_id"]: item["outcome"]
        for item in result["rules_evaluated"]
        if item["rule_id"].startswith("FPV1-GOAL")
    }

    assert goal_traces == {
        "FPV1-GOAL-001": "NOT_EVALUATED",
        "FPV1-GOAL-002": "NOT_EVALUATED",
    }
    assert "COMPLETE_READINESS_DATA" in {
        item["code"] for item in result["priority_stack"]
    }


@pytest.mark.parametrize(("days", "prioritized"), [(90, True), (91, False)])
def test_low_priority_goal_urgent_boundary_is_exact(days: int, prioritized: bool) -> None:
    inputs = _complete_inputs()
    inputs["goals"][0].update(
        {
            "current_amount": Decimal("0"),
            "priority": "LOW",
            "deadline": (NOW.date() + timedelta(days=days)).isoformat(),
        }
    )

    result = _policy(inputs)

    assert result["goal_policy"]["goals"][0]["requires_priority"] is prioritized


@pytest.mark.parametrize(("days", "prioritized"), [(365, True), (366, False)])
def test_medium_priority_goal_near_term_boundary_is_exact(
    days: int, prioritized: bool
) -> None:
    inputs = _complete_inputs()
    inputs["goals"][0].update(
        {
            "current_amount": Decimal("0"),
            "priority": "MEDIUM",
            "deadline": (NOW.date() + timedelta(days=days)).isoformat(),
        }
    )

    result = _policy(inputs)

    assert result["goal_policy"]["goals"][0]["requires_priority"] is prioritized


def test_unfunded_goal_without_deadline_limits_but_funded_goal_does_not() -> None:
    unfunded = _complete_inputs()
    unfunded["goals"][0]["current_amount"] = Decimal("0")

    unfunded_result = _policy(unfunded)
    funded_result = _policy(_complete_inputs())

    assert unfunded_result["investment_readiness"] == "LIMITED"
    assert "GOAL_DEADLINE_UNKNOWN" in unfunded_result["data_gate"][
        "readiness_limiters"
    ]
    assert "GOAL_DEADLINE_UNKNOWN" not in funded_result["data_gate"][
        "readiness_limiters"
    ]


def test_partially_funded_household_goal_is_prioritized_and_completed_goal_is_ignored() -> None:
    inputs = _complete_inputs()
    inputs["household"]["household_type"] = "SHARED"
    inputs["goals"] = [
        {
            **_owned(2, scope="HOUSEHOLD"),
            "name": "Entrada do imóvel",
            "target_amount": Decimal("10000"),
            "current_amount": Decimal("4000"),
            "deadline": (NOW.date() + timedelta(days=60)).isoformat(),
            "priority": "HIGH",
            "currency": "BRL",
            "status": "ACTIVE",
        },
        {
            **_owned(3),
            "name": "Objetivo arquivado",
            "target_amount": Decimal("1000"),
            "current_amount": Decimal("200"),
            "deadline": None,
            "priority": "HIGH",
            "currency": "BRL",
            "status": "COMPLETED",
        },
    ]

    result = _policy(inputs)

    assert result["policy_state"] == "GOAL_PRIORITY"
    assert result["goal_policy"]["priority_goal_ids"] == [2]
    assert result["goal_policy"]["goals"][0]["ownership_scope"] == "HOUSEHOLD"
    assert result["goal_policy"]["goals"][0]["current_amount"] == Decimal("4000")
    assert result["goal_policy"]["goals"][0]["funding_gap"] == Decimal("6000.00")
    assert all(goal["id"] != 3 for goal in result["goal_policy"]["goals"])


def test_removed_member_personal_context_is_excluded_but_household_context_remains() -> None:
    personal = _complete_inputs()
    personal["members"].append({"user_id": 2, "status": "REMOVED"})
    removed_debt = {
        **_active_debt(rate=Decimal("99"), status="DEFAULTED"),
        "id": 20,
        "user_id": 2,
        "currency": "USD",
    }
    personal["liabilities"].append(removed_debt)

    personal_result = _policy(personal)
    shared = deepcopy(personal)
    shared["liabilities"][-1]["ownership_scope"] = "HOUSEHOLD"
    shared_result = _policy(shared)

    assert personal_result["policy_state"] == "INVESTMENT_READY"
    assert personal_result["data_gate"]["currencies"] == ["BRL"]
    assert personal_result["debt_policy"]["debts"] == []
    assert shared_result["policy_state"] == "DATA_BLOCKED"
    assert shared_result["debt_policy"]["debts"][0]["ownership_scope"] == "HOUSEHOLD"


def test_shared_household_keeps_each_debt_owner_explicit() -> None:
    inputs = _complete_inputs()
    inputs["household"]["household_type"] = "SHARED"
    inputs["members"].append(
        {"user_id": 2, "full_name": "Bia", "status": "ACTIVE"}
    )
    personal_debt = {
        **_active_debt(rate=Decimal("2"), payment=Decimal("100")),
        "id": 20,
        "user_id": 2,
        "name": "Dívida pessoal de Bia",
    }
    household_debt = {
        **_active_debt(rate=Decimal("2"), payment=Decimal("200")),
        "id": 30,
        "user_id": 1,
        "ownership_scope": "HOUSEHOLD",
        "name": "Dívida compartilhada",
    }
    inputs["liabilities"] = [personal_debt, household_debt]

    result = _policy(inputs)

    assert {
        (item["id"], item["user_id"], item["ownership_scope"])
        for item in result["debt_policy"]["debts"]
    } == {(20, 2, "PERSONAL"), (30, 1, "HOUSEHOLD")}


def test_context_from_another_household_is_data_blocked() -> None:
    inputs = _complete_inputs()
    state = calculate_financial_state(inputs, evaluated_at=NOW)
    mismatched = deepcopy(inputs)
    mismatched["household"]["id"] = 99

    result = calculate_financial_policy(state, normalized_inputs=mismatched)

    assert result["policy_state"] == "DATA_BLOCKED"
    assert any(
        item["code"] == "FINANCIAL_STATE_CONTEXT_MISMATCH"
        for item in result["blockers"]
    )


def test_missing_normalized_context_blocks_instead_of_hiding_debt_details() -> None:
    inputs = _complete_inputs()
    inputs["liabilities"] = [_active_debt(rate=Decimal("20"))]
    state = calculate_financial_state(inputs, evaluated_at=NOW)

    result = calculate_financial_policy(state, normalized_inputs={})

    assert result["policy_state"] == "DATA_BLOCKED"
    assert any(item["code"] == "POLICY_CONTEXT_MISSING" for item in result["blockers"])


@pytest.mark.parametrize("confidence", [-1, 101])
def test_invalid_confidence_range_is_defensively_blocked(confidence: int) -> None:
    inputs = _complete_inputs()
    state = calculate_financial_state(inputs, evaluated_at=NOW)
    state["confidence"] = confidence

    result = calculate_financial_policy(state, normalized_inputs=inputs)

    assert result["policy_state"] == "DATA_BLOCKED"
    assert any(item["code"] == "CONFIDENCE_OUT_OF_RANGE" for item in result["blockers"])


def test_explicit_inconsistency_blocks_even_if_quality_label_is_malformed_as_complete() -> None:
    inputs = _complete_inputs()
    state = calculate_financial_state(inputs, evaluated_at=NOW)
    state["data_quality"] = "COMPLETE"
    state["inconsistencies"] = ["liabilities.1.invalid_owner"]

    result = calculate_financial_policy(state, normalized_inputs=inputs)

    assert result["policy_state"] == "DATA_BLOCKED"
    assert any(item["code"] == "UNSAFE_DATA_QUALITY" for item in result["blockers"])


def test_foreign_currency_blocks_aggregation_without_assuming_exchange_rate() -> None:
    inputs = _complete_inputs()
    inputs["assets"][1]["currency"] = "USD"

    result = _policy(inputs)

    assert result["policy_state"] == "DATA_BLOCKED"
    assert result["data_gate"]["currencies"] == ["BRL", "USD"]
    assert any(
        item["code"] == "UNSUPPORTED_CURRENCY_AGGREGATION"
        for item in result["blockers"]
    )


def test_missing_asset_currency_is_not_silently_treated_as_brl() -> None:
    inputs = _complete_inputs()
    inputs["assets"][1]["currency"] = None

    result = _policy(inputs)

    assert result["policy_state"] == "DATA_BLOCKED"
    assert result["data_gate"]["missing_currency_fields"] == ["assets.2.currency"]
    assert any(item["code"] == "CURRENCY_MISSING" for item in result["blockers"])


def test_negative_net_worth_prioritizes_debt_without_fabricating_a_hard_block() -> None:
    inputs = _complete_inputs()
    inputs["liabilities"] = [
        _active_debt(rate=Decimal("1"), payment=Decimal("100"), balance=Decimal("20000"))
    ]

    result = _policy(inputs)

    assert result["debt_policy"]["net_worth"] == Decimal("-10000.00")
    assert result["policy_state"] == "DEBT_PRIORITY"
    assert result["investment_readiness"] == "LIMITED"
    assert any(item["code"] == "NEGATIVE_NET_WORTH" for item in result["warnings"])


def test_prior_snapshot_makes_cashflow_deterioration_explicit() -> None:
    previous_inputs = _complete_inputs()
    previous_state = calculate_financial_state(
        previous_inputs, evaluated_at=NOW - timedelta(days=1)
    )
    current_inputs = _complete_inputs()
    current_inputs["incomes"][0]["amount"] = Decimal("3000")
    current_state = calculate_financial_state(current_inputs, evaluated_at=NOW)

    result = calculate_financial_policy(
        current_state,
        normalized_inputs=current_inputs,
        previous_financial_state=previous_state,
    )

    assert result["previous_financial_state"]["comparable"] is True
    assert result["previous_financial_state"]["boundary_crossings"] == [
        "disposable_income",
        "savings_capacity",
    ]
    assert any(
        item["code"] == "CASHFLOW_DETERIORATION_DETECTED"
        for item in result["warnings"]
    )


def test_trace_outcomes_and_rule_fingerprints_are_stable_and_auditable() -> None:
    result = _policy(_complete_inputs())

    assert {item["outcome"] for item in result["rules_evaluated"]} <= {
        "TRIGGERED",
        "NOT_TRIGGERED",
        "NOT_EVALUATED",
    }
    assert len(result["input_fingerprint"]) == 64
    assert len(result["ruleset_fingerprint"]) == 64
    assert len(result["decision_fingerprint"]) == 64


def test_snapshot_identity_is_audit_metadata_not_decision_input() -> None:
    inputs = _complete_inputs()
    first_state = calculate_financial_state(inputs, evaluated_at=NOW)
    second_state = deepcopy(first_state)
    first_state["snapshot_id"] = 7
    second_state["snapshot_id"] = 8

    first = calculate_financial_policy(first_state, normalized_inputs=inputs)
    second = calculate_financial_policy(second_state, normalized_inputs=inputs)

    assert first["source_financial_state"]["snapshot_id"] == 7
    assert second["source_financial_state"]["snapshot_id"] == 8
    assert first["input_fingerprint"] == second["input_fingerprint"]
    assert first["decision_fingerprint"] == second["decision_fingerprint"]


def test_active_zero_balance_with_positive_payment_remains_visible_and_limited() -> None:
    inputs = _complete_inputs()
    inputs["liabilities"] = [
        _active_debt(rate=Decimal("0"), payment=Decimal("100"), balance=Decimal("0"))
    ]

    result = _policy(inputs)

    assert result["debt_policy"]["debts"][0]["annual_interest_rate_pct"] == Decimal("0")
    assert result["debt_policy"]["zero_balance_payment_debt_ids"] == [1]
    assert result["investment_readiness"] == "LIMITED"


def test_stale_cashflow_blocks_while_noncritical_staleness_only_limits() -> None:
    inputs = _complete_inputs()
    state = calculate_financial_state(inputs, evaluated_at=NOW)
    state["data_quality"] = "STALE"
    state["confidence"] = 85
    state["stale_fields"] = ["assets.2"]

    noncritical = calculate_financial_policy(state, normalized_inputs=inputs)
    state["stale_fields"] = ["incomes"]
    critical = calculate_financial_policy(state, normalized_inputs=inputs)

    assert noncritical["policy_state"] == "BALANCED_BUILD"
    assert noncritical["investment_readiness"] == "LIMITED"
    assert critical["policy_state"] == "DATA_BLOCKED"


def test_priority_stack_keeps_formal_precedence_and_contiguous_ranks() -> None:
    inputs = _complete_inputs()
    inputs["incomes"][0]["amount"] = Decimal("3000")
    inputs["liabilities"] = [
        _active_debt(rate=Decimal("20"), payment=Decimal("1000"))
    ]
    inputs["assets"][0]["current_value"] = Decimal("0")
    inputs["goals"][0].update({"current_amount": Decimal("0"), "priority": "HIGH"})

    result = _policy(inputs)

    assert [item["code"] for item in result["priority_stack"]] == [
        "STABILIZE_CASH_FLOW",
        "REDUCE_DEBT_BURDEN",
        "BUILD_EMERGENCY_RESERVE",
        "FUND_PRIORITY_GOAL",
        "COMPLETE_READINESS_DATA",
        "INVEST_SURPLUS_CAPITAL",
    ]
    assert [item["rank"] for item in result["priority_stack"]] == [1, 2, 3, 4, 5, 6]


def test_policy_output_exposes_audit_identity_and_structured_explanations() -> None:
    inputs = _complete_inputs()
    state = calculate_financial_state(inputs, evaluated_at=NOW)
    state["snapshot_id"] = 71

    result = calculate_financial_policy(state, normalized_inputs=inputs)

    assert result["policy_id"] is None
    assert result["financial_state_snapshot_id"] == 71
    assert result["generated_at"] == NOW
    assert result["created_at"] is None
    assert result["explanations"][0] == {
        "code": "PRIMARY_POLICY_DECISION",
        "decision": "Investir somente o capital excedente",
        "reason": (
            "As prioridades prudenciais conhecidas foram atendidas; capacidade de "
            "investimento observada: 5000.00."
        ),
        "evidence_refs": ["INVESTMENT_CAPACITY"],
        "rule_ids": ["FPV1-READY-001"],
        "blocked_alternatives": [],
    }


def test_missing_information_identifies_inputs_that_can_change_the_decision() -> None:
    inputs = _complete_inputs()
    inputs["liabilities"] = [_active_debt(rate=None)]

    result = _policy(inputs)
    missing_codes = {item["code"] for item in result["missing_information"]}

    assert "DEBT_RATE_UNKNOWN" in missing_codes
    debt_rate = next(
        item for item in result["missing_information"] if item["code"] == "DEBT_RATE_UNKNOWN"
    )
    assert debt_rate["fields"] == ["liabilities.1.annual_interest_rate_pct"]
    assert result["investment_readiness"] == "LIMITED"


def test_shared_household_keeps_member_policy_distinct_from_consolidated_policy() -> None:
    inputs = _complete_inputs()
    inputs["household"]["household_type"] = "SHARED"
    inputs["members"].extend(
        [
            {"user_id": 2, "full_name": "Bia", "status": "ACTIVE"},
            {"user_id": 3, "full_name": "Removida", "status": "REMOVED"},
        ]
    )
    inputs["incomes"].append(
        {
            **_owned(20, user_id=2),
            "amount": Decimal("1000"),
            "is_recurring": True,
            "received_at": "2026-09-05",
        }
    )
    inputs["expenses"].append(
        {
            **_owned(20, user_id=2),
            "amount": Decimal("2000"),
            "expense_nature": "FIXED",
            "due_date": "2026-09-05",
        }
    )
    inputs["expenses"].append(
        {
            **_owned(30, scope="HOUSEHOLD"),
            "amount": Decimal("500"),
            "expense_nature": "VARIABLE",
            "due_date": "2026-09-05",
        }
    )

    result = _policy(inputs)
    views = {item["user_id"]: item for item in result["member_policy_views"]}

    assert set(views) == {1, 2}
    assert result["policy_state"] == "EMERGENCY_RESERVE_PRIORITY"
    assert views[2]["policy_state"] == "CASHFLOW_RECOVERY"
    assert views[2]["investment_readiness"] == "BLOCKED"
    assert views[2]["metrics"]["disposable_income"] == Decimal("-1000.00")
    assert (
        "household.shared_values_excluded_from_personal_view"
        in views[2]["missing_information"]
    )


def test_household_debt_never_becomes_the_recording_members_personal_debt() -> None:
    inputs = _complete_inputs()
    inputs["household"]["household_type"] = "SHARED"
    inputs["liabilities"] = [
        {
            **_active_debt(rate=Decimal("30")),
            "ownership_scope": "HOUSEHOLD",
        }
    ]

    result = _policy(inputs)
    member = result["member_policy_views"][0]

    assert result["policy_state"] == "DEBT_PRIORITY"
    assert member["policy_state"] == "BALANCED_BUILD"
    assert member["investment_readiness"] == "LIMITED"
    assert "REDUCE_DEBT_BURDEN" not in member["priority_signals"]
    assert member["metrics"]["total_liabilities"] is None


def test_personal_debt_due_soon_is_preserved_in_the_members_policy_view() -> None:
    inputs = _complete_inputs()
    inputs["household"]["household_type"] = "SHARED"
    inputs["liabilities"] = [
        _active_debt(
            rate=Decimal("1"),
            payment=Decimal("100"),
            due_date=(NOW.date() + timedelta(days=1)).isoformat(),
        )
    ]

    result = _policy(inputs)
    member = result["member_policy_views"][0]

    assert result["policy_state"] == "DEBT_PRIORITY"
    assert result["explanations"][0]["rule_ids"] == ["FPV1-DEBT-005"]
    assert member["policy_state"] == "DEBT_PRIORITY"
    assert "REDUCE_DEBT_BURDEN" in member["priority_signals"]
