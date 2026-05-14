from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from backend.app.enterprise.context import TenantContext
from backend.app.intelligence.budget_model_advisor_service import BudgetModelAdvisorService
from backend.app.intelligence.financial_health_engine import FinancialHealthEngine
from backend.app.intelligence.financial_memory_service import FinancialMemoryService
from backend.app.intelligence.behavioral_intelligence_service import BehavioralIntelligenceService
from backend.app.intelligence.financial_forecast_service import FinancialForecastService
from backend.app.intelligence.financial_timeline_service import FinancialTimelineService
from backend.app.intelligence.dynamic_goals_service import DynamicGoalsService
from backend.app.intelligence.financial_decision_advisor import FinancialDecisionAdvisor
from backend.app.intelligence.models import BudgetAdvisorSnapshot, FinancialGoalEngine, FinancialProfile
from backend.app.intelligence.user_learning_profile_service import UserLearningProfileService
from backend.app.intelligence.contextual_financial_memory import ContextualFinancialMemory


def _history(db: Session, ctx: TenantContext) -> list[dict[str, Any]]:
    rows = db.query(BudgetAdvisorSnapshot).filter(
        BudgetAdvisorSnapshot.organization_id == ctx.organization_id,
        BudgetAdvisorSnapshot.user_id == ctx.user_id,
    ).order_by(BudgetAdvisorSnapshot.year.asc(), BudgetAdvisorSnapshot.month.asc(), BudgetAdvisorSnapshot.created_at.asc()).limit(12).all()
    data: list[dict[str, Any]] = []
    import json
    for row in rows:
        summary = {}
        try:
            payload = json.loads(row.payload_json or "{}")
            for key in ("model_advisor", "financial_coach", "ai_financial_advisor"):
                block = payload.get(key, {})
                summary = block.get("model_advisor", {}).get("input_summary", {}) or block.get("health", {}).get("input_summary", {}) or summary
        except Exception:
            pass
        data.append({
            "year": row.year,
            "month": row.month,
            "income": summary.get("monthly_income", 0),
            "expenses": summary.get("total_expenses", 0),
            "reserve": summary.get("emergency_reserve", 0),
            "contribution": row.investment_capacity,
            "recommended_model": row.recommended_model,
            "health_score": row.health_score,
            "investment_capacity": row.investment_capacity,
        })
    return data


class FinancialContextBuilder:
    """Monta um contexto único e tenant-safe para advisor, dashboard e coaching."""

    @classmethod
    def build(cls, db: Session, ctx: TenantContext, *, year: int | None = None, month: int | None = None) -> dict[str, Any]:
        today = date.today()
        year = year or today.year
        month = month or today.month
        collected = BudgetModelAdvisorService.collect_from_erp(db, ctx.organization_id, year, month)
        advisor = BudgetModelAdvisorService.recommend(collected)
        history = _history(db, ctx)
        if not history:
            history = [{"year": year, "month": month, "income": collected.monthly_income, "expenses": collected.total_expenses, "reserve": collected.emergency_reserve, "contribution": advisor["investment_capacity"], "recommended_model": advisor["recommended_model"], "health_score": advisor["health_score"]}]
        health = FinancialHealthEngine.calculate({**advisor["input_summary"], "investment_capacity": advisor["investment_capacity"]})
        memory = FinancialMemoryService.analyze(history, organization_id=ctx.organization_id, user_id=ctx.user_id)
        behavior = BehavioralIntelligenceService.analyze(history, memory)
        forecast = FinancialForecastService.project(collected.monthly_income, collected.total_expenses, current_net_worth=collected.emergency_reserve, emergency_reserve=collected.emergency_reserve, months=24, debt_payment=collected.debt_payments, include_advanced=True)
        timeline = FinancialTimelineService.build(history)
        rows = db.query(FinancialGoalEngine).filter(FinancialGoalEngine.organization_id == ctx.organization_id, FinancialGoalEngine.user_id == ctx.user_id, FinancialGoalEngine.deleted_at.is_(None)).all()
        goals = [{"id": r.id, "goal_type": r.goal_type, "target_amount": r.target_amount, "current_amount": r.current_amount, "target_date": r.target_date, "success_probability": r.success_probability} for r in rows]
        dynamic_goals = DynamicGoalsService.recalculate(goals, monthly_capacity=advisor["investment_capacity"], behavior=behavior)
        decision = FinancialDecisionAdvisor.advise("debt_vs_invest", health=health, memory=memory, behavior=behavior, context={"investment_capacity": advisor["investment_capacity"], "debt_ratio": advisor["input_summary"].get("debt_ratio", 0), "reserve_months": health.get("metrics", {}).get("reserve_months", 0)})
        profile = db.query(FinancialProfile).filter(FinancialProfile.organization_id == ctx.organization_id, FinancialProfile.user_id == ctx.user_id, FinancialProfile.deleted_at.is_(None)).first()
        learning = UserLearningProfileService.to_dict(UserLearningProfileService.get_or_create(db, organization_id=ctx.organization_id, user_id=ctx.user_id))
        base_context = {
            "organization_id": ctx.organization_id,
            "user_id": ctx.user_id,
            "year": year,
            "month": month,
            "current_financial_situation": advisor["input_summary"],
            "budget_advisor": advisor,
            "recommended_model": advisor["recommended_model"],
            "health": health,
            "financial_phase": health.get("financial_phase"),
            "goals": goals,
            "dynamic_goals": dynamic_goals,
            "investment_capacity": advisor.get("investment_capacity", 0),
            "alerts": advisor.get("warnings", []),
            "behavior": behavior,
            "memory": memory,
            "timeline": timeline,
            "forecast": forecast,
            "decision_advisor": decision,
            "profile": {"risk_profile": getattr(profile, "risk_profile", None), "experience": getattr(profile, "investment_experience", None)} if profile else {},
            "learning_profile": learning,
            "next_steps": advisor.get("action_plan", []),
        }
        base_context["contextual_memory"] = ContextualFinancialMemory.summarize(base_context)
        base_context["ai_context_summary"] = {
            "phase": base_context.get("financial_phase"),
            "recommended_model": base_context.get("recommended_model"),
            "investment_capacity": base_context.get("investment_capacity", 0),
            "priority_now": base_context["contextual_memory"].get("priority_now"),
            "recurring_patterns": base_context["contextual_memory"].get("recurring_patterns", []),
        }
        return base_context
