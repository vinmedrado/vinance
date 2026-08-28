from decimal import Decimal

from backend.app.financial.budget_engine import calculate_budget_strategy
from backend.app.financial.scoring import calculate_financial_score


def test_budget_80_15_5_when_ratio_above_60_percent():
    result = calculate_budget_strategy(
        monthly_salary=Decimal("10000"),
        total_expenses_30d=Decimal("6500"),
        emergency_reserve=Decimal("30000"),
        has_debt_default=False,
        financial_score=80,
    )
    assert result["method"] == "80/15/5"
    assert result["investment_percentage"] == Decimal("0.05")


def test_budget_70_20_10_when_ratio_above_40_percent():
    result = calculate_budget_strategy(
        monthly_salary=Decimal("10000"),
        total_expenses_30d=Decimal("4500"),
        emergency_reserve=Decimal("30000"),
        has_debt_default=False,
        financial_score=80,
    )
    assert result["method"] == "70/20/10"
    assert result["investment_percentage"] == Decimal("0.10")


def test_budget_50_30_20_when_ratio_below_or_equal_40_percent():
    result = calculate_budget_strategy(
        monthly_salary=Decimal("10000"),
        total_expenses_30d=Decimal("4000"),
        emergency_reserve=Decimal("30000"),
        has_debt_default=False,
        financial_score=80,
    )
    assert result["method"] == "50/30/20"
    assert result["investment_percentage"] == Decimal("0.20")


def test_debt_default_forces_80_15_5():
    result = calculate_budget_strategy(
        monthly_salary=Decimal("10000"),
        total_expenses_30d=Decimal("2000"),
        emergency_reserve=Decimal("30000"),
        has_debt_default=True,
        financial_score=80,
    )
    assert result["method"] == "80/15/5"
    assert result["high_risk_allowed"] is False


def test_score_below_40_blocks_high_risk():
    result = calculate_budget_strategy(
        monthly_salary=Decimal("10000"),
        total_expenses_30d=Decimal("8000"),
        emergency_reserve=Decimal("0"),
        has_debt_default=True,
        financial_score=35,
    )
    assert result["high_risk_allowed"] is False


def test_low_emergency_reserve_prioritizes_reserve_and_reduces_investment():
    result = calculate_budget_strategy(
        monthly_salary=Decimal("10000"),
        total_expenses_30d=Decimal("3000"),
        emergency_reserve=Decimal("1000"),
        has_debt_default=False,
        financial_score=80,
    )
    assert result["method"] == "50/30/20"
    assert result["emergency_reserve_priority"] is True
    assert result["investment_percentage"] == Decimal("0.1000")


def test_scoring_penalizes_financial_risk_without_leaving_0_100_range():
    result = calculate_financial_score(
        monthly_salary=Decimal("10000"),
        total_expenses_30d=Decimal("7500"),
        emergency_reserve=Decimal("0"),
        has_debt_default=True,
    )
    assert 0 <= result["score"] <= 100
    assert result["level"] == "critical"
    assert "inadimplencia_ativa" in result["penalties"]
    assert "despesas_acima_60_porcento_renda" in result["penalties"]
