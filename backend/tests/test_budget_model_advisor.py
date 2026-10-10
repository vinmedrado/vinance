from backend.app.intelligence.budget_model_advisor_service import BudgetModelAdvisorService


def recommend(**kwargs):
    base = dict(
        monthly_income=5000,
        total_expenses=2500,
        fixed_expenses=1800,
        variable_expenses=700,
        debt_payments=0,
        overdue_bills=0,
        available_balance=2500,
        emergency_reserve=3000,
        savings_rate=0.5,
        expense_ratio=0.5,
        debt_ratio=0,
        goal_priority="reserva",
        risk_profile="moderate",
    )
    base.update(kwargs)
    return BudgetModelAdvisorService.recommend(base)


def test_high_commitment_recommends_base_zero_or_70_20_10():
    result = recommend(total_expenses=4500, debt_payments=200, available_balance=300)
    assert result["recommended_model"] in {"base_zero", "70_20_10"}
    assert result["investment_capacity"] >= 0
    assert result["investment_gate"]["status"] in {"organize_first", "conservative", "blocked"}


def test_eighty_percent_recommends_reorganization_model():
    result = recommend(total_expenses=4000, debt_payments=0, available_balance=1000)
    assert result["recommended_model"] in {"60_30_10", "70_20_10"}
    assert "reorganiz" in result["financial_phase"] or result["recommended_model"] == "70_20_10"


def test_balanced_user_recommends_50_30_20():
    result = recommend(total_expenses=3000, available_balance=2000)
    assert result["recommended_model"] == "50_30_20"
    assert result["investment_capacity"] > 0


def test_low_expense_user_recommends_custom_aggressive():
    result = recommend(total_expenses=2000, available_balance=3000, emergency_reserve=15000)
    assert result["recommended_model"] == "custom_aggressive"
    assert result["investment_gate"]["status"] == "enabled"


def test_overdue_bills_prioritize_recovery():
    result = recommend(total_expenses=2800, overdue_bills=600, available_balance=1600)
    assert result["recommended_model"] == "recovery"
    assert result["investment_capacity"] == 0
    assert result["investment_gate"]["status"] == "blocked"


def test_investment_capacity_never_negative():
    result = recommend(total_expenses=7000, debt_payments=1000, available_balance=-3000)
    assert result["investment_capacity"] >= 0


def test_output_contains_human_plan_fields():
    result = recommend(total_expenses=3200)
    assert result["reason"]
    assert isinstance(result["action_plan"], list)
    assert {"needs", "wants", "debts", "emergency_reserve", "investments"}.issubset(result["suggested_limits"].keys())
