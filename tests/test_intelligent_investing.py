from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace

from backend.app.intelligence.asset_scoring_service import AssetScoringService
from backend.app.intelligence.financial_capacity_service import FinancialCapacityService
from backend.app.intelligence.intelligent_allocation_service import IntelligentAllocationService
from backend.app.intelligence.investment_recommendation_service import InvestmentRecommendationService
from backend.app.intelligence.personalized_backtest_service import PersonalizedBacktestService
from backend.app.intelligence.schemas import AssetScoreIn


def _profile(**overrides):
    data = dict(
        id=1,
        organization_id="org-a",
        user_id="user-a",
        monthly_income=5000.0,
        monthly_expenses=4200.0,
        available_to_invest=0.0,
        emergency_reserve_months=6.0,
        risk_profile="moderate",
        investment_experience="beginner",
        financial_goal="comprar imóvel",
        target_amount=50000.0,
        target_date=date.today() + timedelta(days=365 * 5),
        preferred_markets=["etfs", "fiis", "fixed_income"],
        liquidity_preference="medium",
        dividend_preference="medium",
        volatility_tolerance="medium",
        investment_horizon="long_term",
        monthly_investment_capacity=0.0,
    )
    data.update(overrides)
    return SimpleNamespace(**data)


def test_financial_capacity_plain_language_and_safe_margin():
    result = FinancialCapacityService.calculate(monthly_income=5000, monthly_expenses=4200, emergency_reserve_months=6, risk_profile="moderate")
    assert result.monthly_surplus == 800
    assert result.monthly_contribution_capacity == 520
    assert "R$ 520,00/mês" in result.plain_language_summary
    assert result.financial_risk in {"baixo", "médio", "alto"}


def test_intelligent_allocation_respects_profile_and_preferences():
    result = IntelligentAllocationService.suggest(_profile(risk_profile="conservative", preferred_markets=["etfs", "fixed_income", "cash"]))
    total = sum(item.percentage for item in result.suggested_allocation)
    assert 99.0 <= total <= 101.0
    markets = {item.market for item in result.suggested_allocation}
    assert "cripto" not in markets
    assert result.estimated_risk == "baixo"


def test_personalized_backtest_generates_scenarios_and_benchmarks():
    profile = _profile()
    capacity = FinancialCapacityService.calculate(monthly_income=5000, monthly_expenses=4200, emergency_reserve_months=6, risk_profile="moderate")
    allocation = IntelligentAllocationService.suggest(profile)
    result = PersonalizedBacktestService.simulate(profile=profile, allocation=allocation, capacity=capacity)
    assert result.monthly_contribution > 0
    assert len(result.scenarios) == 3
    assert "CDI" in result.benchmark_comparison
    assert result.disclaimer.startswith("O Vinance fornece simulações")


def test_asset_scoring_does_not_break_with_sparse_data():
    scores = AssetScoringService.score_assets([AssetScoreIn(symbol="ETF11", market="etfs")], risk_profile="moderate")
    assert len(scores) == 1
    assert 0 <= scores[0].score <= 100
    assert scores[0].profile_compatibility in {"alta", "média", "baixa"}


def test_contextual_recommendation_is_user_friendly():
    result = InvestmentRecommendationService.generate(profile=_profile(), assets=[AssetScoreIn(symbol="FII11", market="fiis", dividend_yield=0.09, liquidity=0.7)])
    assert "Vinance sugere" in result.recommendation
    assert result.recommended_monthly_contribution > 0
    assert result.suggested_allocation
    assert result.asset_scores
    assert "não constitui recomendação financeira" in result.disclaimer


def test_low_cashflow_profile_blocks_aggressive_language():
    result = InvestmentRecommendationService.generate(profile=_profile(monthly_income=3000, monthly_expenses=3100, risk_profile="aggressive"), assets=[])
    assert result.recommended_monthly_contribution == 0
    assert any("reduzir despesas" in item.lower() or "não há margem" in item.lower() for item in result.explanations)
