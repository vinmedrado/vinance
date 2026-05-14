from backend.app.intelligence.financial_health_engine import FinancialHealthEngine
from backend.app.intelligence.adaptive_budget_model_service import AdaptiveBudgetModelService
from backend.app.intelligence.behavioral_finance_service import BehavioralFinanceService
from backend.app.intelligence.financial_coaching_service import FinancialCoachingService
from backend.app.intelligence.financial_forecast_service import FinancialForecastService
from backend.app.intelligence.financial_timeline_service import FinancialTimelineService
from backend.app.intelligence.budget_model_advisor_service import BudgetModelAdvisorService


def test_financial_health_score_and_phase():
    out = FinancialHealthEngine.calculate({
        "monthly_income": 5000,
        "total_expenses": 3000,
        "debt_payments": 200,
        "emergency_reserve": 9000,
        "investment_capacity": 800,
    })
    assert 0 <= out["health_score"] <= 100
    assert out["financial_phase"] in {"estabilização", "crescimento", "construção patrimonial", "expansão financeira"}
    assert out["risk_level"] in {"baixo", "moderado"}


def test_adaptive_model_changes_when_finances_improve():
    current = {
        "monthly_income": 5000,
        "total_expenses": 3200,
        "fixed_expenses": 2400,
        "variable_expenses": 800,
        "debt_payments": 0,
        "overdue_bills": 0,
        "emergency_reserve": 6000,
    }
    result = AdaptiveBudgetModelService.evaluate(current, {"recommended_model": "base_zero", "health_score": 35})
    assert result["changed"] is True
    assert result["recommended_model"] in {"50_30_20", "60_30_10"}
    assert result["health"]["health_score"] > 35


def test_behavioral_finance_detects_patterns():
    history = [
        {"income": 5000, "expenses": 3600, "reserve": 1000, "contribution": 200},
        {"income": 5000, "expenses": 3800, "reserve": 1400, "contribution": 250},
        {"income": 5000, "expenses": 4300, "reserve": 1800, "contribution": 300},
    ]
    out = BehavioralFinanceService.analyze(history)
    assert "aumento recorrente de gastos" in out["patterns"]
    assert "evolução da reserva" in out["patterns"]
    assert out["discipline_score"] >= 0


def test_financial_coaching_generates_human_messages():
    advisor = BudgetModelAdvisorService.recommend({"monthly_income": 5000, "total_expenses": 4200, "debt_payments": 300, "overdue_bills": 0, "emergency_reserve": 1000})
    health = FinancialHealthEngine.calculate({**advisor["input_summary"], "investment_capacity": advisor["investment_capacity"]})
    behavior = BehavioralFinanceService.analyze([{"income": 5000, "expenses": 4200, "reserve": 1000, "contribution": 0}])
    out = FinancialCoachingService.generate(health, advisor, behavior)
    assert out["messages"]
    assert out["next_steps"]
    assert all("Sharpe" not in m for m in out["messages"])


def test_financial_forecast_has_three_scenarios_and_non_negative_values():
    out = FinancialForecastService.project(6000, 4200, current_net_worth=5000, emergency_reserve=3000, months=12)
    assert {s["name"] for s in out["scenarios"]} == {"pessimista", "base", "otimista"}
    assert all(s["projected_net_worth"] >= 0 for s in out["scenarios"])


def test_timeline_builds_journey_events():
    out = FinancialTimelineService.build([
        {"year": 2026, "month": 1, "recommended_model": "base_zero", "health_score": 35, "investment_capacity": 0},
        {"year": 2026, "month": 2, "recommended_model": "60_30_10", "health_score": 48, "investment_capacity": 300},
    ])
    assert out["events"]
    assert any(e["type"] == "model_change" for e in out["events"])
