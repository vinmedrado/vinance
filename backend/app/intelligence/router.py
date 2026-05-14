from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.enterprise.audit import record_event
from backend.app.enterprise.context import TenantContext, require_permission
from backend.app.intelligence.asset_scoring_service import AssetScoringService
from backend.app.intelligence.financial_capacity_service import FinancialCapacityService
from backend.app.intelligence.intelligent_allocation_service import IntelligentAllocationService
from backend.app.intelligence.models import FinancialProfile, FinancialGoalEngine, IntelligentRecommendationSnapshot, BudgetAdvisorSnapshot
from backend.app.intelligence.personalized_backtest_service import PersonalizedBacktestService
from backend.app.intelligence.investment_recommendation_service import InvestmentRecommendationService
from backend.app.intelligence.advanced_backtest_service import AdvancedBacktestService
from backend.app.intelligence.contextual_ml_engine import ContextualMLEngine
from backend.app.intelligence.financial_goals_engine_service import FinancialGoalsEngineService
from backend.app.intelligence.humanized_recommendation_engine import HumanizedRecommendationEngine
from backend.app.intelligence.portfolio_engine_service import PortfolioEngineService
from backend.app.intelligence.risk_engine_service import RiskEngineService
from backend.app.intelligence.scenario_simulation_service import ScenarioSimulationService
from backend.app.intelligence.budget_model_advisor_service import BudgetModelAdvisorService, BudgetAdvisorInput
from backend.app.intelligence.financial_health_engine import FinancialHealthEngine
from backend.app.intelligence.adaptive_budget_model_service import AdaptiveBudgetModelService
from backend.app.intelligence.behavioral_finance_service import BehavioralFinanceService
from backend.app.intelligence.financial_coaching_service import FinancialCoachingService
from backend.app.intelligence.financial_forecast_service import FinancialForecastService
from backend.app.intelligence.financial_timeline_service import FinancialTimelineService
from backend.app.intelligence.financial_memory_service import FinancialMemoryService
from backend.app.intelligence.advanced_financial_coaching_service import AdvancedFinancialCoachingService
from backend.app.intelligence.behavioral_intelligence_service import BehavioralIntelligenceService
from backend.app.intelligence.dynamic_goals_service import DynamicGoalsService
from backend.app.intelligence.financial_decision_advisor import FinancialDecisionAdvisor
from backend.app.intelligence.humanization_engine import HumanizationEngine
from backend.app.intelligence.retention_engagement_service import RetentionEngagementService
from backend.app.intelligence.financial_context_builder import FinancialContextBuilder
from backend.app.intelligence.conversational_financial_advisor import ConversationalFinancialAdvisor
from backend.app.intelligence.financial_ai_orchestrator import FinancialAIOrchestrator
from backend.app.intelligence.contextual_financial_memory import ContextualFinancialMemory
from backend.app.intelligence.financial_safety_guardrails import FinancialSafetyGuardrails
from backend.app.intelligence.continuous_financial_copilot import ContinuousFinancialCopilot
from backend.app.intelligence.user_learning_profile_service import UserLearningProfileService
from backend.app.intelligence.financial_safety_service import FinancialSafetyService
from backend.app.intelligence.schemas import (
    AllocationOut,
    AssetScoreIn,
    AssetScoreOut,
    CapacityOut,
    FinancialProfileIn,
    FinancialProfileOut,
    PersonalizedBacktestOut,
    RecommendationOut,
    RecommendationRequest,
    AdvancedBacktestRequest,
    AdvancedBacktestOut,
    ContextualMLAssetIn,
    ContextualMLAssetOut,
    FinancialGoalEngineIn,
    FinancialGoalEngineOut,
    HumanizedRecommendationOut,
    PortfolioEngineOut,
    RiskEngineOut,
    ScenarioSimulationOut,
    BudgetAdvisorInputSchema,
    BudgetAdvisorOut,
    FinancialPlanOut,
    FinancialHealthOut,
    AdaptiveBudgetModelOut,
    BehavioralFinanceOut,
    FinancialCoachingOut,
    FinancialForecastOut,
    FinancialTimelineOut,
    FinancialCoachDashboardOut,
    FinancialMemoryOut,
    BehavioralIntelligenceOut,
    AdvancedFinancialCoachingOut,
    DynamicGoalsOut,
    FinancialDecisionAdvisorOut,
    RetentionEngagementOut,
    AIFinancialAdvisorDashboardOut,
    AdvisorQuestionIn,
    AdvisorAnswerOut,
    FinancialContextOut,
    CopilotEventOut,
    UserLearningProfileOut,
    ConversationalAdvisorDashboardOut,
)
from backend.app.services.plan_limits_service import PlanLimitExceeded, ensure_feature_allowed

router = APIRouter(prefix="/api/intelligence", tags=["Inteligência Financeira"])


def _markets_to_text(markets: list[str] | str | None) -> str:
    if isinstance(markets, str):
        return markets
    return json.dumps(markets or [], ensure_ascii=False)


def _markets_from_text(markets: str | None) -> list[str]:
    if not markets:
        return []
    try:
        parsed = json.loads(markets)
        return parsed if isinstance(parsed, list) else []
    except Exception:
        return [m.strip() for m in markets.split(",") if m.strip()]


def _profile_out(row: FinancialProfile) -> FinancialProfileOut:
    return FinancialProfileOut(
        id=row.id,
        organization_id=row.organization_id,
        user_id=row.user_id,
        monthly_income=row.monthly_income,
        monthly_expenses=row.monthly_expenses,
        available_to_invest=row.available_to_invest,
        emergency_reserve_months=row.emergency_reserve_months,
        risk_profile=row.risk_profile,
        investment_experience=row.investment_experience,
        financial_goal=row.financial_goal,
        target_amount=row.target_amount,
        target_date=row.target_date,
        preferred_markets=_markets_from_text(row.preferred_markets),
        liquidity_preference=row.liquidity_preference,
        dividend_preference=row.dividend_preference,
        volatility_tolerance=row.volatility_tolerance,
        investment_horizon=row.investment_horizon,
        monthly_investment_capacity=row.monthly_investment_capacity,
        onboarding_completed=row.onboarding_completed,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _get_profile(db: Session, ctx: TenantContext) -> FinancialProfile:
    row = db.query(FinancialProfile).filter(
        FinancialProfile.organization_id == ctx.organization_id,
        FinancialProfile.user_id == ctx.user_id,
        FinancialProfile.deleted_at.is_(None),
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Perfil financeiro ainda não preenchido")
    return row


def _limit_error(exc: Exception, ctx: TenantContext, feature: str) -> HTTPException:
    return HTTPException(status_code=403, detail={"detail": "Plan limit reached", "limit": feature, "plan": ctx.plan, "upgrade_required": True, "message": str(exc)})


def _audit(db: Session, request: Request, ctx: TenantContext, action: str, entity_type: str, entity_id: str | None = None, before: Any = None, after: Any = None) -> None:
    record_event(
        db,
        organization_id=ctx.organization_id,
        user_id=ctx.user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        before=before,
        after=after,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        request_id=getattr(request.state, "request_id", None),
    )




def _behavior_history_from_snapshots(db: Session, ctx: TenantContext) -> list[dict[str, Any]]:
    rows = db.query(BudgetAdvisorSnapshot).filter(
        BudgetAdvisorSnapshot.organization_id == ctx.organization_id,
        BudgetAdvisorSnapshot.user_id == ctx.user_id,
    ).order_by(BudgetAdvisorSnapshot.year.asc(), BudgetAdvisorSnapshot.month.asc(), BudgetAdvisorSnapshot.created_at.asc()).limit(12).all()
    history: list[dict[str, Any]] = []
    for row in rows:
        try:
            payload = json.loads(row.payload_json or '{}')
            summary = payload.get('model_advisor', {}).get('input_summary', {})
        except Exception:
            summary = {}
        history.append({
            'year': row.year,
            'month': row.month,
            'income': summary.get('monthly_income', 0),
            'expenses': summary.get('total_expenses', 0),
            'reserve': summary.get('emergency_reserve', 0),
            'contribution': row.investment_capacity,
            'recommended_model': row.recommended_model,
            'health_score': row.health_score,
            'investment_capacity': row.investment_capacity,
        })
    return history


def _latest_budget_snapshot(db: Session, ctx: TenantContext) -> dict[str, Any] | None:
    row = db.query(BudgetAdvisorSnapshot).filter(
        BudgetAdvisorSnapshot.organization_id == ctx.organization_id,
        BudgetAdvisorSnapshot.user_id == ctx.user_id,
    ).order_by(BudgetAdvisorSnapshot.created_at.desc()).first()
    if not row:
        return None
    return {'recommended_model': row.recommended_model, 'health_score': row.health_score, 'investment_capacity': row.investment_capacity, 'year': row.year, 'month': row.month}


def _timeline_from_snapshots(db: Session, ctx: TenantContext) -> dict[str, Any]:
    return FinancialTimelineService.build(_behavior_history_from_snapshots(db, ctx))


@router.post("/budget-advisor", response_model=BudgetAdvisorOut)
def budget_advisor_preview(payload: BudgetAdvisorInputSchema, ctx: TenantContext = Depends(require_permission("diagnosis.view"))):
    # Preview calculado a partir de payload explícito; não persiste dados e não usa outro tenant.
    return BudgetModelAdvisorService.recommend(payload.model_dump())


def _build_monthly_plan(advisor: dict[str, Any]) -> dict[str, Any]:
    limits = advisor.get("suggested_limits", {})
    return {
        "recommended_model": advisor.get("model_label"),
        "needs_limit": limits.get("needs", 0),
        "wants_limit": limits.get("wants", 0),
        "debt_limit": limits.get("debts", 0),
        "reserve_limit": limits.get("emergency_reserve", 0),
        "investment_limit": limits.get("investments", 0),
        "safe_to_invest": advisor.get("investment_capacity", 0),
        "risk_alert": "; ".join(advisor.get("warnings", [])) or "Plano dentro de uma faixa saudável para este mês.",
    }


@router.get("/financial-plan", response_model=FinancialPlanOut)
def get_financial_plan(request: Request, year: int | None = None, month: int | None = None, save_snapshot: bool = False, db: Session = Depends(get_db), ctx: TenantContext = Depends(require_permission("diagnosis.view"))):
    from datetime import date
    today = date.today()
    year = year or today.year
    month = month or today.month
    collected = BudgetModelAdvisorService.collect_from_erp(db, ctx.organization_id, year, month)
    advisor = BudgetModelAdvisorService.recommend(collected)
    plan = {
        "year": year,
        "month": month,
        "model_advisor": advisor,
        "monthly_plan": _build_monthly_plan(advisor),
        "next_steps": advisor.get("action_plan", []),
        "investment_message": advisor.get("investment_gate", {}).get("message", "Cadastre renda e despesas para liberar a análise."),
    }
    if save_snapshot:
        row = BudgetAdvisorSnapshot(
            organization_id=ctx.organization_id,
            user_id=ctx.user_id,
            year=year,
            month=month,
            recommended_model=advisor["recommended_model"],
            health_score=advisor["health_score"],
            investment_capacity=advisor["investment_capacity"],
            payload_json=json.dumps(plan, ensure_ascii=False, default=str),
            created_by=ctx.user_id,
        )
        db.add(row)
        _audit(db, request, ctx, "budget_advisor.recalculated", "financial_plan", f"{year}-{month:02d}", after=plan)
        db.commit()
    return plan


@router.get("/financial-coach/dashboard", response_model=FinancialCoachDashboardOut)
def get_financial_coach_dashboard(request: Request, year: int | None = None, month: int | None = None, save_snapshot: bool = True, db: Session = Depends(get_db), ctx: TenantContext = Depends(require_permission("diagnosis.view"))):
    from datetime import date
    today = date.today()
    year = year or today.year
    month = month or today.month
    collected = BudgetModelAdvisorService.collect_from_erp(db, ctx.organization_id, year, month)
    advisor = BudgetModelAdvisorService.recommend(collected)
    previous = _latest_budget_snapshot(db, ctx)
    adaptive = AdaptiveBudgetModelService.evaluate(advisor["input_summary"], previous)
    health = adaptive["health"]
    history = _behavior_history_from_snapshots(db, ctx)
    if not history:
        history = [{"year": year, "month": month, "income": collected.monthly_income, "expenses": collected.total_expenses, "reserve": collected.emergency_reserve, "contribution": advisor["investment_capacity"], "recommended_model": advisor["recommended_model"], "health_score": advisor["health_score"]}]
    behavior = BehavioralFinanceService.analyze(history)
    coaching = FinancialCoachingService.generate(health, advisor, behavior)
    forecast = FinancialForecastService.project(
        monthly_income=collected.monthly_income,
        total_expenses=collected.total_expenses,
        current_net_worth=collected.emergency_reserve,
        emergency_reserve=collected.emergency_reserve,
        months=12,
    )
    timeline = FinancialTimelineService.build(history)
    main = coaching["messages"][0] if coaching.get("messages") else advisor["reason"]
    next_best = coaching["next_steps"][0] if coaching.get("next_steps") else "Cadastre renda e despesas para o Vinance acompanhar sua evolução."
    payload = {
        "year": year,
        "month": month,
        "health": health,
        "adaptive_model": adaptive,
        "behavior": behavior,
        "coaching": coaching,
        "forecast": forecast,
        "timeline": timeline,
        "main_recommendation": main,
        "next_best_action": next_best,
        "disclaimer": "O Vinance fornece análises e simulações educacionais baseadas em dados históricos e modelos quantitativos. Isso não constitui recomendação financeira.",
    }
    if save_snapshot:
        row = BudgetAdvisorSnapshot(
            organization_id=ctx.organization_id, user_id=ctx.user_id, year=year, month=month,
            recommended_model=advisor["recommended_model"], health_score=health["health_score"],
            investment_capacity=advisor["investment_capacity"], payload_json=json.dumps({"model_advisor": advisor, "financial_coach": payload}, ensure_ascii=False, default=str), created_by=ctx.user_id,
        )
        db.add(row)
        _audit(db, request, ctx, "financial_coach.dashboard_generated", "financial_coach", f"{year}-{month:02d}", after={"health_score": health["health_score"], "model": advisor["recommended_model"]})
        db.commit()
    return payload


@router.get("/financial-health", response_model=FinancialHealthOut)
def get_financial_health(year: int | None = None, month: int | None = None, db: Session = Depends(get_db), ctx: TenantContext = Depends(require_permission("diagnosis.view"))):
    from datetime import date
    today = date.today(); year = year or today.year; month = month or today.month
    collected = BudgetModelAdvisorService.collect_from_erp(db, ctx.organization_id, year, month)
    advisor = BudgetModelAdvisorService.recommend(collected)
    previous = _latest_budget_snapshot(db, ctx)
    return FinancialHealthEngine.calculate({**advisor["input_summary"], "investment_capacity": advisor["investment_capacity"], "previous_health_score": previous.get("health_score") if previous else None})


@router.get("/financial-timeline", response_model=FinancialTimelineOut)
def get_financial_timeline(db: Session = Depends(get_db), ctx: TenantContext = Depends(require_permission("diagnosis.view"))):
    return _timeline_from_snapshots(db, ctx)


@router.get("/financial-forecast", response_model=FinancialForecastOut)
def get_financial_forecast(year: int | None = None, month: int | None = None, db: Session = Depends(get_db), ctx: TenantContext = Depends(require_permission("diagnosis.view"))):
    from datetime import date
    today = date.today(); year = year or today.year; month = month or today.month
    collected = BudgetModelAdvisorService.collect_from_erp(db, ctx.organization_id, year, month)
    return FinancialForecastService.project(collected.monthly_income, collected.total_expenses, collected.emergency_reserve, collected.emergency_reserve, months=12)


@router.get("/financial-memory", response_model=FinancialMemoryOut)
def get_financial_memory(db: Session = Depends(get_db), ctx: TenantContext = Depends(require_permission("diagnosis.view"))):
    history = _behavior_history_from_snapshots(db, ctx)
    return FinancialMemoryService.analyze(history, organization_id=ctx.organization_id, user_id=ctx.user_id)


@router.get("/behavioral-intelligence", response_model=BehavioralIntelligenceOut)
def get_behavioral_intelligence(db: Session = Depends(get_db), ctx: TenantContext = Depends(require_permission("diagnosis.view"))):
    history = _behavior_history_from_snapshots(db, ctx)
    memory = FinancialMemoryService.analyze(history, organization_id=ctx.organization_id, user_id=ctx.user_id)
    return BehavioralIntelligenceService.analyze(history, memory)


@router.get("/dynamic-goals", response_model=DynamicGoalsOut)
def get_dynamic_goals(db: Session = Depends(get_db), ctx: TenantContext = Depends(require_permission("goals.view"))):
    history = _behavior_history_from_snapshots(db, ctx)
    memory = FinancialMemoryService.analyze(history, organization_id=ctx.organization_id, user_id=ctx.user_id)
    behavior = BehavioralIntelligenceService.analyze(history, memory)
    profile = None
    try:
        profile = _profile_out(_get_profile(db, ctx))
        capacity = profile.monthly_investment_capacity
    except Exception:
        latest = _latest_budget_snapshot(db, ctx) or {}
        capacity = latest.get("investment_capacity", 0)
    rows = db.query(FinancialGoalEngine).filter(FinancialGoalEngine.organization_id == ctx.organization_id, FinancialGoalEngine.user_id == ctx.user_id, FinancialGoalEngine.deleted_at.is_(None)).all()
    goals = [{"goal_type": r.goal_type, "target_amount": r.target_amount, "current_amount": r.current_amount, "target_date": r.target_date} for r in rows]
    if not goals and profile and profile.target_amount:
        goals = [{"goal_type": profile.financial_goal or "personalizado", "target_amount": profile.target_amount, "current_amount": 0, "target_date": profile.target_date}]
    return DynamicGoalsService.recalculate(goals, monthly_capacity=capacity or 0, behavior=behavior)


@router.get("/decision-advisor", response_model=FinancialDecisionAdvisorOut)
def get_decision_advisor(decision_type: str = "debt_vs_invest", year: int | None = None, month: int | None = None, db: Session = Depends(get_db), ctx: TenantContext = Depends(require_permission("diagnosis.view"))):
    from datetime import date
    today = date.today(); year = year or today.year; month = month or today.month
    collected = BudgetModelAdvisorService.collect_from_erp(db, ctx.organization_id, year, month)
    advisor = BudgetModelAdvisorService.recommend(collected)
    health = FinancialHealthEngine.calculate({**advisor["input_summary"], "investment_capacity": advisor["investment_capacity"]})
    history = _behavior_history_from_snapshots(db, ctx)
    memory = FinancialMemoryService.analyze(history, organization_id=ctx.organization_id, user_id=ctx.user_id)
    behavior = BehavioralIntelligenceService.analyze(history, memory)
    context = {"investment_capacity": advisor["investment_capacity"], "debt_ratio": advisor["input_summary"].get("debt_ratio", 0), "reserve_months": health.get("metrics", {}).get("reserve_months", 0)}
    return FinancialDecisionAdvisor.advise(decision_type, health=health, memory=memory, behavior=behavior, context=context)


@router.get("/ai-financial-advisor", response_model=AIFinancialAdvisorDashboardOut)
def get_ai_financial_advisor(request: Request, year: int | None = None, month: int | None = None, save_snapshot: bool = True, db: Session = Depends(get_db), ctx: TenantContext = Depends(require_permission("diagnosis.view"))):
    from datetime import date
    today = date.today(); year = year or today.year; month = month or today.month
    collected = BudgetModelAdvisorService.collect_from_erp(db, ctx.organization_id, year, month)
    advisor = BudgetModelAdvisorService.recommend(collected)
    previous = _latest_budget_snapshot(db, ctx)
    health = FinancialHealthEngine.calculate({**advisor["input_summary"], "investment_capacity": advisor["investment_capacity"], "previous_health_score": previous.get("health_score") if previous else None})
    history = _behavior_history_from_snapshots(db, ctx)
    if not history:
        history = [{"year": year, "month": month, "income": collected.monthly_income, "expenses": collected.total_expenses, "reserve": collected.emergency_reserve, "contribution": advisor["investment_capacity"], "recommended_model": advisor["recommended_model"], "health_score": health["health_score"], "overdue_bills": collected.overdue_bills}]
    memory = FinancialMemoryService.analyze(history, organization_id=ctx.organization_id, user_id=ctx.user_id)
    behavior = BehavioralIntelligenceService.analyze(history, memory)
    forecast = FinancialForecastService.project(collected.monthly_income, collected.total_expenses, current_net_worth=collected.emergency_reserve, emergency_reserve=collected.emergency_reserve, months=24, debt_payment=collected.debt_payments, include_advanced=True)
    rows = db.query(FinancialGoalEngine).filter(FinancialGoalEngine.organization_id == ctx.organization_id, FinancialGoalEngine.user_id == ctx.user_id, FinancialGoalEngine.deleted_at.is_(None)).all()
    goals = [{"goal_type": r.goal_type, "target_amount": r.target_amount, "current_amount": r.current_amount, "target_date": r.target_date} for r in rows]
    dynamic_goals = DynamicGoalsService.recalculate(goals, monthly_capacity=advisor["investment_capacity"], behavior=behavior)
    coaching = AdvancedFinancialCoachingService.generate(health=health, memory=memory, behavior=behavior, forecast=forecast)
    decision = FinancialDecisionAdvisor.advise("debt_vs_invest", health=health, memory=memory, behavior=behavior, context={"investment_capacity": advisor["investment_capacity"], "debt_ratio": advisor["input_summary"].get("debt_ratio", 0), "reserve_months": health.get("metrics", {}).get("reserve_months", 0)})
    retention = RetentionEngagementService.build(history, health, memory)
    timeline = FinancialTimelineService.build(history)
    advisor_main = HumanizationEngine.refine(coaching["messages"][0] if coaching.get("messages") else advisor["reason"], phase=health.get("financial_phase"))
    next_best = HumanizationEngine.next_best_action({"health_score": health["health_score"], "investment_capacity": advisor["investment_capacity"], "reserve_months": health.get("metrics", {}).get("reserve_months", 0)})
    payload = {
        "year": year,
        "month": month,
        "health": health,
        "memory": memory,
        "behavioral_intelligence": behavior,
        "coaching": coaching,
        "dynamic_goals": dynamic_goals,
        "forecast": forecast,
        "decision_advisor": decision,
        "retention": retention,
        "timeline": timeline,
        "advisor_main_message": advisor_main,
        "next_best_action": next_best,
        "disclaimer": "O Vinance fornece análises e simulações educacionais baseadas em dados históricos e modelos quantitativos. Isso não constitui recomendação financeira.",
    }
    if save_snapshot:
        row = BudgetAdvisorSnapshot(organization_id=ctx.organization_id, user_id=ctx.user_id, year=year, month=month, recommended_model=advisor["recommended_model"], health_score=health["health_score"], investment_capacity=advisor["investment_capacity"], payload_json=json.dumps({"ai_financial_advisor": payload}, ensure_ascii=False, default=str), created_by=ctx.user_id)
        db.add(row)
        _audit(db, request, ctx, "ai_financial_advisor.generated", "ai_financial_advisor", f"{year}-{month:02d}", after={"health_score": health["health_score"], "behavioral_score": behavior["behavioral_score"]})
        db.commit()
    return payload


@router.get("/advisor-context", response_model=FinancialContextOut)
def get_advisor_context(year: int | None = None, month: int | None = None, db: Session = Depends(get_db), ctx: TenantContext = Depends(require_permission("diagnosis.view"))):
    """Contexto consolidado para o advisor, sempre filtrado por organization_id/user_id."""
    context = FinancialContextBuilder.build(db, ctx, year=year, month=month)
    return {
        "organization_id": context["organization_id"],
        "user_id": context["user_id"],
        "year": context["year"],
        "month": context["month"],
        "current_financial_situation": context["current_financial_situation"],
        "recommended_model": context["recommended_model"],
        "health": context["health"],
        "financial_phase": context.get("financial_phase"),
        "goals": context.get("goals", []),
        "investment_capacity": context.get("investment_capacity", 0),
        "alerts": context.get("alerts", []),
        "behavior": context.get("behavior", {}),
        "memory": context.get("memory", {}),
        "forecast": context.get("forecast", {}),
        "next_steps": context.get("next_steps", []),
    }


@router.post("/advisor/chat", response_model=AdvisorAnswerOut)
def chat_with_financial_advisor(payload: AdvisorQuestionIn, request: Request, db: Session = Depends(get_db), ctx: TenantContext = Depends(require_permission("diagnosis.view"))):
    """Advisor conversacional real: contexto do ERP + memória + personalização + guardrails."""
    answer = FinancialAIOrchestrator.answer_from_db(db, ctx, payload.question, year=payload.year, month=payload.month)
    _audit(db, request, ctx, "advisor.chat_answered", "ai_financial_copilot", None, after={"intent": answer.get("intent"), "question_length": len(payload.question), "used_real_data": answer.get("used_real_data", True)})
    db.commit()
    return answer


@router.get("/copilot/events", response_model=list[CopilotEventOut])
def get_copilot_events(year: int | None = None, month: int | None = None, db: Session = Depends(get_db), ctx: TenantContext = Depends(require_permission("diagnosis.view"))):
    context = FinancialContextBuilder.build(db, ctx, year=year, month=month)
    return ContinuousFinancialCopilot.monitor(context)


@router.get("/user-learning-profile", response_model=UserLearningProfileOut)
def get_user_learning_profile(db: Session = Depends(get_db), ctx: TenantContext = Depends(require_permission("diagnosis.view"))):
    row = UserLearningProfileService.get_or_create(db, organization_id=ctx.organization_id, user_id=ctx.user_id)
    db.commit()
    return UserLearningProfileService.to_dict(row)


@router.get("/conversational-advisor/dashboard", response_model=ConversationalAdvisorDashboardOut)
def get_conversational_advisor_dashboard(year: int | None = None, month: int | None = None, db: Session = Depends(get_db), ctx: TenantContext = Depends(require_permission("diagnosis.view"))):
    context = FinancialContextBuilder.build(db, ctx, year=year, month=month)
    events = ContinuousFinancialCopilot.monitor(context)
    learning = context.get("learning_profile", {})
    contextual_memory = ContextualFinancialMemory.summarize(context)
    suggested_questions = FinancialAIOrchestrator.suggest_questions(context, contextual_memory)
    main = FinancialAIOrchestrator.answer("qual meu próximo passo financeiro?", context, learning)
    context_summary = {
        "organization_id": context["organization_id"], "user_id": context["user_id"], "year": context["year"], "month": context["month"],
        "current_financial_situation": context["current_financial_situation"], "recommended_model": context["recommended_model"],
        "health": context["health"], "financial_phase": context.get("financial_phase"), "goals": context.get("goals", []),
        "investment_capacity": context.get("investment_capacity", 0), "alerts": context.get("alerts", []), "behavior": context.get("behavior", {}),
        "memory": context.get("contextual_memory", context.get("memory", {})), "forecast": context.get("forecast", {}), "next_steps": context.get("next_steps", []),
    }
    return {
        "context_summary": context_summary,
        "copilot_events": events,
        "suggested_questions": suggested_questions,
        "main_message": main["answer"],
        "next_step": main.get("recommended_action", "Revisar plano financeiro"),
        "disclaimer": FinancialSafetyGuardrails.disclaimer(),
    }


@router.get("/profile", response_model=FinancialProfileOut)
def get_financial_profile(db: Session = Depends(get_db), ctx: TenantContext = Depends(require_permission("investments.view"))):
    return _profile_out(_get_profile(db, ctx))


@router.post("/profile", response_model=FinancialProfileOut)
def upsert_financial_profile(payload: FinancialProfileIn, request: Request, db: Session = Depends(get_db), ctx: TenantContext = Depends(require_permission("investments.manage"))):
    row = db.query(FinancialProfile).filter(FinancialProfile.organization_id == ctx.organization_id, FinancialProfile.user_id == ctx.user_id, FinancialProfile.deleted_at.is_(None)).first()
    capacity = FinancialCapacityService.calculate(
        monthly_income=payload.monthly_income,
        monthly_expenses=payload.monthly_expenses,
        available_to_invest=payload.available_to_invest,
        emergency_reserve_months=payload.emergency_reserve_months,
        risk_profile=payload.risk_profile,
    )
    data = payload.model_dump()
    data["available_to_invest"] = payload.available_to_invest if payload.available_to_invest is not None else capacity.monthly_surplus
    data["monthly_investment_capacity"] = payload.monthly_investment_capacity if payload.monthly_investment_capacity is not None else capacity.monthly_contribution_capacity
    data["preferred_markets"] = _markets_to_text(data.get("preferred_markets"))
    before = None
    if row:
        before = _profile_out(row).model_dump(mode="json")
        for key, value in data.items():
            setattr(row, key, value)
        row.updated_by = ctx.user_id
        action = "financial_profile.updated"
    else:
        row = FinancialProfile(organization_id=ctx.organization_id, user_id=ctx.user_id, created_by=ctx.user_id, updated_by=ctx.user_id, **data)
        db.add(row)
        action = "financial_profile.created"
    db.flush()
    out = _profile_out(row)
    _audit(db, request, ctx, action, "financial_profile", str(row.id), before=before, after=out.model_dump(mode="json"))
    db.commit(); db.refresh(row)
    return _profile_out(row)


@router.get("/capacity", response_model=CapacityOut)
def get_capacity(db: Session = Depends(get_db), ctx: TenantContext = Depends(require_permission("investments.view"))):
    profile = _profile_out(_get_profile(db, ctx))
    return FinancialCapacityService.calculate(**profile.model_dump(include={"monthly_income", "monthly_expenses", "available_to_invest", "emergency_reserve_months", "risk_profile"}))


@router.get("/allocation", response_model=AllocationOut)
def get_allocation(db: Session = Depends(get_db), ctx: TenantContext = Depends(require_permission("investments.view"))):
    profile = _profile_out(_get_profile(db, ctx))
    return IntelligentAllocationService.suggest(profile)


@router.get("/backtest", response_model=PersonalizedBacktestOut)
def personalized_backtest(request: Request, db: Session = Depends(get_db), ctx: TenantContext = Depends(require_permission("jobs.run"))):
    try:
        ensure_feature_allowed(db, organization_id=ctx.organization_id, plan=ctx.plan, feature="backtests_per_month")
    except PlanLimitExceeded as exc:
        raise _limit_error(exc, ctx, "backtests_per_month")
    profile = _profile_out(_get_profile(db, ctx))
    capacity = FinancialCapacityService.calculate(**profile.model_dump(include={"monthly_income", "monthly_expenses", "available_to_invest", "emergency_reserve_months", "risk_profile"}))
    allocation = IntelligentAllocationService.suggest(profile)
    result = PersonalizedBacktestService.simulate(profile=profile, allocation=allocation, capacity=capacity)
    try:
        db.execute(text("INSERT INTO enterprise_jobs (organization_id, created_by, job_type, status, parameters_json, result_json) VALUES (:org, :user, 'backtest', 'completed', :params, :result)"), {"org": ctx.organization_id, "user": ctx.user_id, "params": json.dumps({"profile_id": profile.id}), "result": result.model_dump_json()})
    except Exception:
        pass
    _audit(db, request, ctx, "job.completed", "personalized_backtest", str(profile.id), after=result.model_dump(mode="json"))
    db.commit()
    return result


@router.post("/asset-scoring", response_model=list[AssetScoreOut])
def score_assets(payload: list[AssetScoreIn], db: Session = Depends(get_db), ctx: TenantContext = Depends(require_permission("investments.view"))):
    profile = _profile_out(_get_profile(db, ctx))
    return AssetScoringService.score_assets(payload, risk_profile=profile.risk_profile)


@router.post("/recommendation", response_model=RecommendationOut)
def recommendation(payload: RecommendationRequest, request: Request, db: Session = Depends(get_db), ctx: TenantContext = Depends(require_permission("diagnosis.view"))):
    try:
        ensure_feature_allowed(db, organization_id=ctx.organization_id, plan=ctx.plan, feature="advanced_ai")
    except PlanLimitExceeded as exc:
        raise _limit_error(exc, ctx, "advanced_ai")
    profile = _profile_out(_get_profile(db, ctx))
    result = InvestmentRecommendationService.generate(profile=profile, assets=payload.assets)
    if payload.save_snapshot:
        row = IntelligentRecommendationSnapshot(
            organization_id=ctx.organization_id,
            user_id=ctx.user_id,
            financial_profile_id=profile.id,
            recommendation_json=result.model_dump_json(),
            disclaimer=result.disclaimer,
            created_by=ctx.user_id,
        )
        db.add(row); db.flush()
        _audit(db, request, ctx, "recommendation.generated", "intelligent_recommendation", str(row.id), after=result.model_dump(mode="json"))
    else:
        _audit(db, request, ctx, "recommendation.generated", "intelligent_recommendation", str(profile.id), after={"saved": False})
    db.commit()
    return result


@router.post("/goals", response_model=FinancialGoalEngineOut)
def create_financial_goal(payload: FinancialGoalEngineIn, request: Request, db: Session = Depends(get_db), ctx: TenantContext = Depends(require_permission("goals.create"))):
    evaluated = FinancialGoalsEngineService.evaluate(payload, organization_id=ctx.organization_id, user_id=ctx.user_id)
    row = FinancialGoalEngine(
        organization_id=ctx.organization_id,
        user_id=ctx.user_id,
        goal_type=payload.goal_type,
        target_amount=payload.target_amount,
        current_amount=payload.current_amount,
        target_date=payload.target_date,
        monthly_contribution=payload.monthly_contribution,
        inflation_adjusted_target=evaluated.inflation_adjusted_target,
        risk_profile=payload.risk_profile,
        investment_horizon=payload.investment_horizon,
        success_probability=evaluated.success_probability,
        estimated_completion_date=evaluated.estimated_completion_date,
        created_by=ctx.user_id,
        updated_by=ctx.user_id,
    )
    db.add(row); db.flush()
    out = FinancialGoalsEngineService.evaluate(payload, organization_id=ctx.organization_id, user_id=ctx.user_id, goal_id=row.id)
    _audit(db, request, ctx, "goal.created", "financial_goal", str(row.id), after=out.model_dump(mode="json"))
    db.commit()
    return out

@router.get("/goals", response_model=list[FinancialGoalEngineOut])
def list_financial_goals(db: Session = Depends(get_db), ctx: TenantContext = Depends(require_permission("goals.view"))):
    rows = db.query(FinancialGoalEngine).filter(FinancialGoalEngine.organization_id == ctx.organization_id, FinancialGoalEngine.user_id == ctx.user_id, FinancialGoalEngine.deleted_at.is_(None)).all()
    result = []
    for row in rows:
        payload = FinancialGoalEngineIn(goal_type=row.goal_type, target_amount=row.target_amount, current_amount=row.current_amount, target_date=row.target_date, monthly_contribution=row.monthly_contribution, risk_profile=row.risk_profile, investment_horizon=row.investment_horizon)
        result.append(FinancialGoalsEngineService.evaluate(payload, organization_id=ctx.organization_id, user_id=ctx.user_id, goal_id=row.id))
    return result

@router.post("/advanced-backtest", response_model=AdvancedBacktestOut)
def advanced_backtest(payload: AdvancedBacktestRequest, request: Request, db: Session = Depends(get_db), ctx: TenantContext = Depends(require_permission("jobs.run"))):
    profile = _profile_out(_get_profile(db, ctx))
    allocation = IntelligentAllocationService.suggest(profile)
    result = AdvancedBacktestService.run(profile=profile, allocation=allocation, request=payload)
    _audit(db, request, ctx, "advanced_backtest.completed", "advanced_backtest", str(profile.id), after={"risk": result.risk_label, "metrics": result.internal_metrics})
    db.commit()
    return result

@router.get("/portfolio-engine", response_model=PortfolioEngineOut)
def portfolio_engine(db: Session = Depends(get_db), ctx: TenantContext = Depends(require_permission("investments.view"))):
    profile = _profile_out(_get_profile(db, ctx))
    allocation = IntelligentAllocationService.suggest(profile)
    return PortfolioEngineService.build(profile=profile, allocation=allocation)

@router.post("/contextual-ml", response_model=list[ContextualMLAssetOut])
def contextual_ml(payload: list[ContextualMLAssetIn], db: Session = Depends(get_db), ctx: TenantContext = Depends(require_permission("investments.view"))):
    profile = _profile_out(_get_profile(db, ctx))
    return ContextualMLEngine.score_assets(payload, risk_profile=profile.risk_profile)

@router.get("/risk", response_model=RiskEngineOut)
def risk_engine(db: Session = Depends(get_db), ctx: TenantContext = Depends(require_permission("investments.view"))):
    profile = _profile_out(_get_profile(db, ctx))
    allocation = IntelligentAllocationService.suggest(profile)
    return RiskEngineService.assess(allocation, risk_profile=profile.risk_profile)

@router.get("/scenarios", response_model=ScenarioSimulationOut)
def scenarios(db: Session = Depends(get_db), ctx: TenantContext = Depends(require_permission("investments.view"))):
    profile = _profile_out(_get_profile(db, ctx))
    months = 120
    return ScenarioSimulationService.simulate(current_amount=0, monthly_contribution=profile.monthly_investment_capacity, months=months, target_amount=profile.target_amount)

@router.get("/humanized-recommendation", response_model=HumanizedRecommendationOut)
def humanized_recommendation(db: Session = Depends(get_db), ctx: TenantContext = Depends(require_permission("diagnosis.view"))):
    profile = _profile_out(_get_profile(db, ctx))
    allocation = IntelligentAllocationService.suggest(profile)
    risk = RiskEngineService.assess(allocation, risk_profile=profile.risk_profile)
    goal = None
    if profile.target_amount:
        goal_payload = FinancialGoalEngineIn(goal_type="custom", target_amount=profile.target_amount, current_amount=0, target_date=profile.target_date, monthly_contribution=profile.monthly_investment_capacity, risk_profile=profile.risk_profile, investment_horizon=profile.investment_horizon)
        goal = FinancialGoalsEngineService.evaluate(goal_payload, organization_id=ctx.organization_id, user_id=ctx.user_id)
    return HumanizedRecommendationEngine.explain(goal=goal, risk=risk, monthly_contribution=profile.monthly_investment_capacity)
