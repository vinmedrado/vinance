from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal

from backend.app.financial_state.engine import ENGINE_VERSION, calculate_financial_state


NOW = datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc)


def _record(record_id: int, user_id: int, scope: str = "PERSONAL") -> dict:
    return {
        "id": record_id,
        "household_id": 10,
        "user_id": user_id,
        "ownership_scope": scope,
        "updated_at": NOW,
    }


def _complete_individual() -> dict:
    return {
        "household": {"id": 10, "name": "Casa de Ana", "household_type": "PERSONAL"},
        "members": [{"user_id": 1, "full_name": "Ana", "status": "ACTIVE"}],
        "incomes": [
            {**_record(1, 1), "amount": Decimal("6000"), "is_recurring": True, "received_at": "2026-09-05"},
            {**_record(2, 1), "amount": Decimal("500"), "is_recurring": False, "received_at": "2026-09-06"},
        ],
        "expenses": [
            {**_record(1, 1), "amount": Decimal("2000"), "expense_nature": "FIXED", "due_date": "2026-09-05"},
            {**_record(2, 1), "amount": Decimal("1000"), "expense_nature": "VARIABLE", "due_date": "2026-09-06"},
        ],
        "assets": [
            {**_record(1, 1), "asset_class": "EMERGENCY_RESERVE", "current_value": Decimal("6000"), "value_as_of": "2026-09-07", "status": "ACTIVE"},
            {**_record(2, 1), "asset_class": "INVESTMENTS", "current_value": Decimal("4000"), "value_as_of": "2026-09-07", "status": "ACTIVE"},
        ],
        "liabilities": [
            {**_record(1, 1), "current_balance": Decimal("2000"), "monthly_payment": Decimal("500"), "balance_as_of": "2026-09-07", "status": "ACTIVE"}
        ],
        "goals": [
            {**_record(1, 1), "name": "Reserva", "target_amount": Decimal("10000"), "current_amount": Decimal("2500"), "deadline": None, "priority": "HIGH", "status": "ACTIVE"}
        ],
        "financial_profiles": [],
    }


def test_individual_complete_state_uses_documented_formulas() -> None:
    result = calculate_financial_state(_complete_individual(), evaluated_at=NOW)

    assert result["engine_version"] == ENGINE_VERSION == "household-financial-state-v1"
    assert result["data_quality"] == "COMPLETE"
    assert result["confidence"] == 100
    assert result["missing_fields"] == []
    metrics = result["metrics"]
    assert metrics["recurring_monthly_income"] == Decimal("6000.00")
    assert metrics["non_recurring_income"] == Decimal("500.00")
    assert metrics["fixed_expenses"] == Decimal("2000.00")
    assert metrics["variable_expenses"] == Decimal("1000.00")
    assert metrics["total_expenses"] == Decimal("3000.00")
    assert metrics["cash_flow"] == Decimal("3500.00")
    assert metrics["disposable_income"] == Decimal("3000.00")
    assert metrics["savings_capacity"] == Decimal("3000.00")
    assert metrics["investment_capacity"] == Decimal("2500.00")
    assert metrics["total_assets"] == Decimal("10000.00")
    assert metrics["total_liabilities"] == Decimal("2000.00")
    assert metrics["net_worth"] == Decimal("8000.00")
    assert metrics["emergency_reserve_months"] == Decimal("2.00")
    assert metrics["debt_to_income"] == Decimal("2.78")
    assert metrics["debt_service_ratio"] == Decimal("8.33")
    assert metrics["savings_rate"] == Decimal("50.00")
    assert metrics["asset_distribution"]["EMERGENCY_RESERVE"] == {
        "amount": Decimal("6000.00"),
        "percentage": Decimal("60.00"),
    }
    assert result["goals"][0]["funding_gap"] == Decimal("7500.00")


def test_couple_keeps_member_views_distinct_and_counts_shared_records_once() -> None:
    data = _complete_individual()
    data["household"]["household_type"] = "SHARED"
    data["members"].append({"user_id": 2, "full_name": "Bia", "status": "ACTIVE"})
    data["incomes"] = [
        {**_record(1, 1), "amount": Decimal("5000"), "is_recurring": True, "received_at": "2026-09-05"},
        {**_record(2, 2), "amount": Decimal("3000"), "is_recurring": True, "received_at": "2026-09-05"},
        {**_record(3, 1, "HOUSEHOLD"), "amount": Decimal("1000"), "is_recurring": True, "received_at": "2026-09-05"},
    ]
    data["expenses"] = [
        {**_record(1, 1), "amount": Decimal("1000"), "expense_nature": "FIXED", "due_date": "2026-09-05"},
        {**_record(2, 2), "amount": Decimal("500"), "expense_nature": "VARIABLE", "due_date": "2026-09-05"},
        {**_record(3, 1, "HOUSEHOLD"), "amount": Decimal("2000"), "expense_nature": "FIXED", "due_date": "2026-09-05"},
    ]
    data["assets"].append(
        {**_record(3, 2), "asset_class": "CASH", "current_value": Decimal("2000"), "value_as_of": "2026-09-07", "status": "ACTIVE"}
    )
    data["liabilities"] = [
        {**_record(1, 1, "HOUSEHOLD"), "current_balance": Decimal("0"), "monthly_payment": Decimal("0"), "balance_as_of": "2026-09-07", "status": "PAID"}
    ]
    data["goals"][0]["ownership_scope"] = "HOUSEHOLD"
    data["goals"][0]["current_amount"] = Decimal("0")

    result = calculate_financial_state(data, evaluated_at=NOW)

    assert result["metrics"]["recurring_monthly_income"] == Decimal("9000.00")
    assert result["metrics"]["total_expenses"] == Decimal("3500.00")
    member_metrics = {item["user_id"]: item["metrics"] for item in result["member_views"]}
    assert member_metrics[1]["recurring_monthly_income"] == Decimal("5000.00")
    assert member_metrics[2]["recurring_monthly_income"] == Decimal("3000.00")
    assert member_metrics[1]["total_expenses"] == Decimal("1000.00")
    assert member_metrics[2]["total_expenses"] == Decimal("500.00")


def test_explicit_zero_is_preserved_while_absent_value_stays_none() -> None:
    explicit = _complete_individual()
    explicit["assets"] = [
        {**_record(1, 1), "asset_class": "EMERGENCY_RESERVE", "current_value": Decimal("0"), "value_as_of": "2026-09-07", "status": "ACTIVE"}
    ]
    explicit["liabilities"] = [
        {**_record(1, 1), "current_balance": Decimal("0"), "monthly_payment": Decimal("0"), "status": "PAID"}
    ]
    explicit["goals"][0]["current_amount"] = Decimal("0")
    missing = deepcopy(explicit)
    missing["assets"][0]["current_value"] = None
    missing["liabilities"][0]["current_balance"] = None
    missing["goals"][0]["current_amount"] = None

    zero_state = calculate_financial_state(explicit, evaluated_at=NOW)
    missing_state = calculate_financial_state(missing, evaluated_at=NOW)

    assert zero_state["metrics"]["total_assets"] == Decimal("0.00")
    assert zero_state["metrics"]["total_liabilities"] == Decimal("0.00")
    assert zero_state["goals"][0]["funding_gap"] == Decimal("10000.00")
    assert missing_state["metrics"]["total_assets"] is None
    assert missing_state["goals"][0]["funding_gap"] is None
    assert "assets.1.current_value" in missing_state["missing_fields"]
    assert "goals.1.current_amount" in missing_state["missing_fields"]


def test_absent_income_and_expense_categories_are_not_invented_as_zero() -> None:
    data = _complete_individual()
    data["incomes"] = [item for item in data["incomes"] if item["is_recurring"]]
    data["expenses"] = [item for item in data["expenses"] if item["expense_nature"] == "FIXED"]

    result = calculate_financial_state(data, evaluated_at=NOW)

    assert result["metrics"]["non_recurring_income"] is None
    assert result["metrics"]["variable_expenses"] is None
    assert result["metrics"]["total_expenses"] == Decimal("2000.00")
    assert "income.non_recurring" in result["missing_fields"]
    assert "expenses.variable" in result["missing_fields"]


def test_profile_reserve_fallback_coexists_with_other_owned_assets() -> None:
    data = _complete_individual()
    data["assets"] = [
        {**_record(2, 1), "asset_class": "INVESTMENTS", "current_value": Decimal("4000"), "value_as_of": "2026-09-07", "status": "ACTIVE"}
    ]
    data["financial_profiles"] = [
        {"id": 8, "user_id": "1", "emergency_reserve": Decimal("6000"), "updated_at": NOW}
    ]

    result = calculate_financial_state(data, evaluated_at=NOW)

    assert result["metrics"]["total_assets"] == Decimal("10000.00")
    assert result["metrics"]["emergency_reserve"] == Decimal("6000.00")
    assert result["provenance"]["emergency_reserve"]["financial_profile_fallback_user_ids"] == [1]


def test_removed_household_members_do_not_receive_an_individual_view() -> None:
    data = _complete_individual()
    data["members"].append({"user_id": 2, "full_name": "Ex-membro", "status": "REMOVED"})

    result = calculate_financial_state(data, evaluated_at=NOW)

    assert [item["user_id"] for item in result["member_views"]] == [1]


def test_removed_member_personal_data_is_excluded_but_household_data_remains() -> None:
    data = _complete_individual()
    data["household"]["household_type"] = "SHARED"
    data["members"].append({"user_id": 2, "full_name": "Ex-membro", "status": "REMOVED"})
    data["assets"].extend(
        [
            {
                **_record(20, 2),
                "asset_class": "CASH",
                "current_value": Decimal("9000"),
                "value_as_of": "2026-09-07",
                "status": "ACTIVE",
            },
            {
                **_record(21, 2, "HOUSEHOLD"),
                "asset_class": "CASH",
                "current_value": Decimal("2000"),
                "value_as_of": "2026-09-07",
                "status": "ACTIVE",
            },
        ]
    )

    result = calculate_financial_state(data, evaluated_at=NOW)

    assert result["metrics"]["total_assets"] == Decimal("12000.00")
    assert result["inconsistencies"] == []


def test_inconsistent_owner_and_paid_debt_are_reported_without_fabricating_metrics() -> None:
    data = _complete_individual()
    data["assets"].append(
        {**_record(99, 999), "asset_class": "CASH", "current_value": Decimal("900000"), "status": "ACTIVE"}
    )
    data["liabilities"][0].update({"status": "PAID", "current_balance": Decimal("100")})

    result = calculate_financial_state(data, evaluated_at=NOW)

    assert result["data_quality"] == "INCONSISTENT"
    assert "assets.99.owner_not_member" in result["inconsistencies"]
    assert "liabilities.1.paid_with_balance" in result["inconsistencies"]
    assert result["metrics"]["total_assets"] == Decimal("10000.00")


def test_stale_inputs_are_explicit_and_profile_fallback_is_not_double_counted() -> None:
    data = _complete_individual()
    data["incomes"] = []
    data["expenses"] = []
    data["assets"][0]["value_as_of"] = "2025-01-01"
    data["assets"][1]["value_as_of"] = "2025-01-01"
    data["liabilities"][0]["balance_as_of"] = "2025-01-01"
    data["financial_profiles"] = [
        {"id": 1, "user_id": 1, "monthly_salary": Decimal("6000"), "emergency_reserve": Decimal("999999"), "updated_at": "2025-01-01"}
    ]

    result = calculate_financial_state(data, evaluated_at=NOW)

    assert result["data_quality"] == "STALE"
    assert result["metrics"]["recurring_monthly_income"] == Decimal("6000.00")
    assert result["metrics"]["total_assets"] == Decimal("10000.00")
    assert result["metrics"]["emergency_reserve"] == Decimal("6000.00")
    assert result["stale_fields"]


def test_engine_is_deterministic_and_does_not_mutate_normalized_inputs() -> None:
    data = _complete_individual()
    original = deepcopy(data)

    first = calculate_financial_state(data, evaluated_at=NOW)
    second = calculate_financial_state(data, evaluated_at=NOW)

    assert first == second
    assert data == original


def test_partial_and_insufficient_quality_are_not_http_or_market_predictions() -> None:
    partial = _complete_individual()
    partial["goals"][0]["current_amount"] = None
    insufficient = {
        "household": {"id": 10, "name": "Sem dados", "household_type": "PERSONAL"},
        "members": [{"user_id": 1, "full_name": "Ana", "status": "ACTIVE"}],
        "incomes": [],
        "expenses": [],
        "assets": [],
        "liabilities": [],
        "goals": [],
        "financial_profiles": [],
    }

    partial_state = calculate_financial_state(partial, evaluated_at=NOW)
    insufficient_state = calculate_financial_state(insufficient, evaluated_at=NOW)

    assert partial_state["data_quality"] == "PARTIAL"
    assert 0 < partial_state["confidence"] < 100
    assert insufficient_state["data_quality"] == "INSUFFICIENT"
    assert insufficient_state["confidence"] == 0
    assert insufficient_state["metrics"]["cash_flow"] is None
    assert insufficient_state["metrics"]["net_worth"] is None
