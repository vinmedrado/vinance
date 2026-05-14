from backend.app.intelligence.financial_memory_service import FinancialMemoryService
from backend.app.intelligence.advanced_financial_coaching_service import AdvancedFinancialCoachingService
from backend.app.intelligence.behavioral_intelligence_service import BehavioralIntelligenceService
from backend.app.intelligence.dynamic_goals_service import DynamicGoalsService
from backend.app.intelligence.financial_forecast_service import FinancialForecastService
from backend.app.intelligence.financial_decision_advisor import FinancialDecisionAdvisor
from backend.app.intelligence.humanization_engine import HumanizationEngine
from backend.app.intelligence.retention_engagement_service import RetentionEngagementService
from backend.app.intelligence.financial_health_engine import FinancialHealthEngine


def sample_history():
    return [
        {"organization_id": "org-a", "user_id": "u1", "year": 2026, "month": 1, "income": 5000, "expenses": 4500, "reserve": 500, "contribution": 0, "overdue_bills": 1, "categories": {"lazer": 700, "mercado": 1200}},
        {"organization_id": "org-a", "user_id": "u1", "year": 2026, "month": 2, "income": 5200, "expenses": 4200, "reserve": 900, "contribution": 150, "overdue_bills": 0, "categories": {"lazer": 500, "mercado": 1150}},
        {"organization_id": "org-a", "user_id": "u1", "year": 2026, "month": 3, "income": 5200, "expenses": 3900, "reserve": 1400, "contribution": 250, "overdue_bills": 0, "categories": {"lazer": 420, "mercado": 1100}},
    ]


def test_financial_memory_detects_trend_and_keeps_tenant_identity():
    out = FinancialMemoryService.analyze(sample_history(), organization_id="org-a", user_id="u1")
    assert out["organization_id"] == "org-a"
    assert out["user_id"] == "u1"
    assert out["trend"] == "melhorando"
    assert out["critical_months"]
    assert out["critical_categories"][0]["category"] in {"mercado", "lazer"}


def test_behavioral_intelligence_scores_are_bounded():
    memory = FinancialMemoryService.analyze(sample_history(), organization_id="org-a", user_id="u1")
    out = BehavioralIntelligenceService.analyze(sample_history(), memory)
    assert 0 <= out["behavioral_score"] <= 100
    assert 0 <= out["discipline_score"] <= 100
    assert out["signals"]


def test_advanced_coaching_is_human_and_actionable():
    memory = FinancialMemoryService.analyze(sample_history(), organization_id="org-a", user_id="u1")
    behavior = BehavioralIntelligenceService.analyze(sample_history(), memory)
    health = FinancialHealthEngine.calculate({"monthly_income": 5200, "total_expenses": 3900, "debt_payments": 0, "emergency_reserve": 1400, "investment_capacity": 250})
    out = AdvancedFinancialCoachingService.generate(health=health, memory=memory, behavior=behavior)
    assert out["messages"]
    assert out["tips"]
    assert "Sharpe" not in " ".join(out["messages"])


def test_dynamic_goals_recalculate_contribution_and_probability():
    behavior = {"discipline_score": 80}
    out = DynamicGoalsService.recalculate([
        {"goal_type": "reserva de emergência", "target_amount": 12000, "current_amount": 3000}
    ], monthly_capacity=800, behavior=behavior)
    assert out["goals"][0]["remaining_amount"] > 0
    assert out["goals"][0]["suggested_monthly_contribution"] > 0
    assert 0 <= out["goals"][0]["success_probability"] <= 100


def test_advanced_forecast_includes_crisis_and_inflation_scenarios():
    out = FinancialForecastService.project(6000, 4200, current_net_worth=5000, emergency_reserve=3000, months=24, debt_payment=300, include_advanced=True)
    names = {s["name"] for s in out["scenarios"]}
    assert {"crise", "inflação alta", "juros altos", "moderado"}.issubset(names)
    assert all(s["projected_net_worth"] >= 0 for s in out["scenarios"])


def test_decision_advisor_prioritizes_debt_when_pressure_is_high():
    health = FinancialHealthEngine.calculate({"monthly_income": 5000, "total_expenses": 4700, "debt_payments": 1100, "emergency_reserve": 300, "investment_capacity": 0})
    memory = FinancialMemoryService.analyze(sample_history(), organization_id="org-a", user_id="u1")
    behavior = BehavioralIntelligenceService.analyze(sample_history(), memory)
    out = FinancialDecisionAdvisor.advise("debt_vs_invest", health=health, memory=memory, behavior=behavior, context={"debt_ratio": 0.22, "reserve_months": 0.1, "investment_capacity": 0})
    assert "dívida" in out["recommendation"].lower() or "dívidas" in out["recommendation"].lower()
    assert out["next_steps"]


def test_humanization_and_retention_outputs_premium_language():
    msg = HumanizationEngine.refine("risco alto: você falhou", phase="recuperação")
    assert "falhou" not in msg.lower()
    memory = FinancialMemoryService.analyze(sample_history(), organization_id="org-a", user_id="u1")
    health = FinancialHealthEngine.calculate({"monthly_income": 5200, "total_expenses": 3900, "emergency_reserve": 1400, "investment_capacity": 250})
    out = RetentionEngagementService.build(sample_history(), health, memory)
    assert out["milestones"]
    assert out["progress_summary"]
