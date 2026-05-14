from datetime import date, timedelta

from backend.app.intelligence.advanced_backtest_service import AdvancedBacktestService
from backend.app.intelligence.contextual_ml_engine import ContextualMLEngine
from backend.app.intelligence.financial_goals_engine_service import FinancialGoalsEngineService
from backend.app.intelligence.humanized_recommendation_engine import HumanizedRecommendationEngine
from backend.app.intelligence.intelligent_allocation_service import IntelligentAllocationService
from backend.app.intelligence.portfolio_engine_service import PortfolioEngineService
from backend.app.intelligence.risk_engine_service import RiskEngineService
from backend.app.intelligence.scenario_simulation_service import ScenarioSimulationService
from backend.app.intelligence.schemas import AdvancedBacktestRequest, ContextualMLAssetIn, FinancialGoalEngineIn, FinancialProfileOut


def profile():
    return FinancialProfileOut(id=1, organization_id='org-a', user_id='user-a', monthly_income=7000, monthly_expenses=4800, available_to_invest=1200, emergency_reserve_months=6, risk_profile='moderate', investment_experience='intermediate', financial_goal='Comprar imóvel', target_amount=150000, target_date=date.today()+timedelta(days=365*8), preferred_markets=['etfs','fiis','fixed_income','cash'], liquidity_preference='medium', dividend_preference='medium', volatility_tolerance='medium', investment_horizon='long_term', monthly_investment_capacity=900, onboarding_completed=True)


def test_goals_engine_calculates_probability_and_required_contribution():
    payload=FinancialGoalEngineIn(goal_type='home', target_amount=150000, current_amount=15000, target_date=date.today()+timedelta(days=365*8), monthly_contribution=900, risk_profile='moderate', investment_horizon='long_term')
    out=FinancialGoalsEngineService.evaluate(payload, organization_id='org-a', user_id='user-a')
    assert out.organization_id == 'org-a'
    assert out.inflation_adjusted_target > out.target_amount
    assert 1 <= out.success_probability <= 99
    assert len(out.scenarios) == 3


def test_advanced_backtest_is_reproducible_and_has_metrics():
    p=profile(); alloc=IntelligentAllocationService.suggest(p)
    req=AdvancedBacktestRequest(monthly_contribution=900, horizon_months=96, seed=123)
    a=AdvancedBacktestService.run(profile=p, allocation=alloc, request=req)
    b=AdvancedBacktestService.run(profile=p, allocation=alloc, request=req)
    assert a.internal_metrics['CAGR'] == b.internal_metrics['CAGR']
    assert 'Sharpe' in a.internal_metrics
    assert len(a.rolling_windows) > 0


def test_portfolio_engine_and_risk_engine_translate_risk():
    p=profile(); alloc=IntelligentAllocationService.suggest(p)
    portfolio=PortfolioEngineService.build(profile=p, allocation=alloc)
    risk=RiskEngineService.assess(alloc, risk_profile=p.risk_profile)
    assert portfolio.diversification_score >= 0
    assert risk.risk_label in {'baixo','moderado','elevado'}


def test_contextual_ml_scores_assets_for_user_profile():
    assets=[ContextualMLAssetIn(symbol='ETF11', market='etfs', returns=[0.01,0.02,-0.005,0.012], liquidity=0.9, quality=0.8), ContextualMLAssetIn(symbol='CRYPTO', market='crypto', returns=[0.1,-0.2,0.15,-0.05], liquidity=0.7, quality=0.5)]
    scored=ContextualMLEngine.score_assets(assets, risk_profile='conservative')
    assert len(scored)==2
    assert scored[0].contextual_score >= scored[-1].contextual_score


def test_scenarios_and_humanized_recommendation():
    p=profile(); alloc=IntelligentAllocationService.suggest(p); risk=RiskEngineService.assess(alloc, risk_profile=p.risk_profile)
    scenarios=ScenarioSimulationService.simulate(monthly_contribution=900, months=96, target_amount=150000)
    human=HumanizedRecommendationEngine.explain(risk=risk, monthly_contribution=900)
    assert len(scenarios.scenarios) >= 8
    assert 'não constitui recomendação financeira' in human.disclaimer.lower()
