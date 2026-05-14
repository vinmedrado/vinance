from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

RiskProfile = Literal["conservative", "moderate", "aggressive"]
Experience = Literal["beginner", "intermediate", "advanced"]
Preference = Literal["low", "medium", "high"]
Horizon = Literal["short_term", "medium_term", "long_term"]
Market = Literal["equities", "fiis", "etfs", "bdrs", "crypto", "fixed_income", "cash"]


class FinancialProfileIn(BaseModel):
    monthly_income: float = Field(ge=0)
    monthly_expenses: float = Field(ge=0)
    available_to_invest: float | None = Field(default=None, ge=0)
    emergency_reserve_months: float = Field(default=0, ge=0)
    risk_profile: RiskProfile = "moderate"
    investment_experience: Experience = "beginner"
    financial_goal: str | None = None
    target_amount: float | None = Field(default=None, ge=0)
    target_date: date | None = None
    preferred_markets: list[Market] = Field(default_factory=lambda: ["etfs", "fiis", "fixed_income", "cash"])
    liquidity_preference: Preference = "medium"
    dividend_preference: Preference = "medium"
    volatility_tolerance: Preference = "medium"
    investment_horizon: Horizon = "medium_term"
    monthly_investment_capacity: float | None = Field(default=None, ge=0)
    onboarding_completed: bool = True


class FinancialProfileOut(FinancialProfileIn):
    id: int
    organization_id: str
    user_id: str
    available_to_invest: float
    monthly_investment_capacity: float
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class CapacityOut(BaseModel):
    monthly_surplus: float
    expenses_ratio_pct: float
    investable_ratio_pct: float
    recommended_emergency_reserve: float
    healthy_investment_limit: float
    financial_risk: str
    safety_margin: float
    monthly_contribution_capacity: float
    plain_language_summary: str
    alerts: list[str] = Field(default_factory=list)


class AllocationItem(BaseModel):
    market: str
    percentage: float
    rationale: str


class AllocationOut(BaseModel):
    risk_profile: str
    suggested_allocation: list[AllocationItem]
    estimated_risk: str
    goal_compatibility: str
    plain_language_summary: str


class BacktestScenario(BaseModel):
    name: str
    estimated_final_amount: float
    estimated_gain: float
    chance_to_reach_goal_pct: float | None = None


class PersonalizedBacktestOut(BaseModel):
    monthly_contribution: float
    horizon_months: int
    simulated_historical_return: float
    worst_simulated_drop_pct: float
    estimated_goal_success_chance_pct: float | None = None
    risk_label: str
    benchmark_comparison: dict[str, float]
    scenarios: list[BacktestScenario]
    plain_language_summary: str
    disclaimer: str


class AssetScoreIn(BaseModel):
    symbol: str
    market: Market
    volatility: float | None = None
    liquidity: float | None = None
    trend: float | None = None
    drawdown: float | None = None
    dividend_yield: float | None = None
    vacancy: float | None = None
    quality: float | None = None
    consistency: float | None = None
    tracking_error: float | None = None


class AssetScoreOut(BaseModel):
    symbol: str
    market: str
    score: float
    profile_compatibility: str
    risk: str
    recommendation_context: str


class RecommendationOut(BaseModel):
    recommendation: str
    recommended_monthly_contribution: float
    suggested_allocation: list[AllocationItem]
    risk: str
    goal_estimate: str
    benchmark_comparison: dict[str, float]
    scenarios: list[BacktestScenario]
    explanations: list[str]
    asset_scores: list[AssetScoreOut] = Field(default_factory=list)
    disclaimer: str


class RecommendationRequest(BaseModel):
    assets: list[AssetScoreIn] = Field(default_factory=list)
    save_snapshot: bool = False


GoalType = Literal["emergency_reserve", "retirement", "home", "car", "travel", "financial_freedom", "passive_income", "education", "custom"]

class FinancialGoalEngineIn(BaseModel):
    goal_type: GoalType = "custom"
    target_amount: float = Field(ge=0)
    current_amount: float = Field(default=0, ge=0)
    target_date: date | None = None
    monthly_contribution: float = Field(default=0, ge=0)
    risk_profile: RiskProfile = "moderate"
    investment_horizon: Horizon = "medium_term"

class FinancialGoalEngineOut(FinancialGoalEngineIn):
    id: int | None = None
    organization_id: str | None = None
    user_id: str | None = None
    inflation_adjusted_target: float
    success_probability: float
    estimated_completion_date: date | None = None
    amount_remaining: float
    required_monthly_contribution: float
    months_to_goal: int
    delay_months: int
    scenarios: list[BacktestScenario]
    plain_language_summary: str
    explanations: list[str] = Field(default_factory=list)

    model_config = {"from_attributes": True}

class AdvancedBacktestRequest(BaseModel):
    monthly_contribution: float | None = Field(default=None, ge=0)
    horizon_months: int | None = Field(default=None, ge=1)
    rebalance_frequency: Literal["monthly", "quarterly", "semiannual", "annual"] = "quarterly"
    transaction_cost_bps: float = Field(default=10, ge=0)
    tax_rate: float = Field(default=0.15, ge=0, le=1)
    slippage_bps: float = Field(default=5, ge=0)
    seed: int = 42

class AdvancedBacktestOut(BaseModel):
    internal_metrics: dict[str, float]
    benchmark_comparison: dict[str, float]
    walk_forward: dict[str, float]
    rolling_windows: list[dict[str, float]]
    scenarios: list[BacktestScenario]
    user_summary: str
    risk_label: str
    disclaimer: str

class PortfolioEngineOut(BaseModel):
    allocation: list[AllocationItem]
    risk_controls: dict[str, float | str]
    rebalance_actions: list[str]
    diversification_score: float
    user_summary: str

class ContextualMLAssetIn(BaseModel):
    symbol: str
    market: Market
    returns: list[float] = Field(default_factory=list)
    liquidity: float | None = None
    quality: float | None = None
    dividend_yield: float | None = None

class ContextualMLAssetOut(BaseModel):
    symbol: str
    market: str
    contextual_score: float
    regime: str
    risk_adjusted_label: str
    user_fit: str
    explanation: str

class RiskEngineOut(BaseModel):
    risk_label: str
    concentration_risk: str
    liquidity_risk: str
    expected_drawdown_pct: float
    volatility_estimate_pct: float
    alerts: list[str]
    user_summary: str

class ScenarioSimulationOut(BaseModel):
    scenarios: list[BacktestScenario]
    impacts: dict[str, str]
    user_summary: str

class HumanizedRecommendationOut(BaseModel):
    main_recommendation: str
    why: list[str]
    risks: list[str]
    goal_impact: str
    contribution_impact: str
    deadline_impact: str
    simple_strategy_comparison: str
    disclaimer: str

class BudgetAdvisorInputSchema(BaseModel):
    monthly_income: float = Field(default=0, ge=0)
    total_expenses: float = Field(default=0, ge=0)
    fixed_expenses: float = Field(default=0, ge=0)
    variable_expenses: float = Field(default=0, ge=0)
    debt_payments: float = Field(default=0, ge=0)
    overdue_bills: float = Field(default=0, ge=0)
    available_balance: float = 0
    emergency_reserve: float = Field(default=0, ge=0)
    savings_rate: float = 0
    expense_ratio: float = 0
    debt_ratio: float = 0
    goal_priority: str | None = None
    risk_profile: str = "moderate"

class BudgetAdvisorOut(BaseModel):
    recommended_model: str
    model_label: str
    confidence_score: float
    financial_phase: str
    reason: str
    action_plan: list[str]
    suggested_limits: dict[str, float]
    warnings: list[str]
    investment_capacity: float
    health_score: int
    investment_gate: dict[str, Any]
    input_summary: dict[str, Any]
    disclaimer: str

class FinancialPlanOut(BaseModel):
    year: int
    month: int
    model_advisor: BudgetAdvisorOut
    monthly_plan: dict[str, Any]
    next_steps: list[str]
    investment_message: str

class FinancialHealthOut(BaseModel):
    health_score: int
    risk_level: str
    financial_phase: str
    evolution_trend: str
    metrics: dict[str, Any]
    plain_language_summary: str
    input_summary: dict[str, Any] = Field(default_factory=dict)

class AdaptiveBudgetModelOut(BaseModel):
    recommended_model: str
    model_label: str
    changed: bool
    change_reason: str
    confidence_score: float
    comparison: dict[str, Any]
    health: FinancialHealthOut
    advisor: BudgetAdvisorOut

class BehavioralFinanceOut(BaseModel):
    patterns: list[str]
    discipline_score: int
    stability: str
    risk_of_slippage: str
    insights: list[str]

class FinancialCoachingOut(BaseModel):
    messages: list[str]
    alerts: list[dict[str, str]]
    next_steps: list[str]
    tone: str

class FinancialForecastOut(BaseModel):
    months: int
    scenarios: list[dict[str, Any]]
    plain_language_summary: str
    disclaimer: str

class FinancialTimelineOut(BaseModel):
    events: list[dict[str, Any]]
    summary: str

class FinancialCoachDashboardOut(BaseModel):
    year: int
    month: int
    health: FinancialHealthOut
    adaptive_model: AdaptiveBudgetModelOut
    behavior: BehavioralFinanceOut
    coaching: FinancialCoachingOut
    forecast: FinancialForecastOut
    timeline: FinancialTimelineOut
    main_recommendation: str
    next_best_action: str
    disclaimer: str

class FinancialMemoryOut(BaseModel):
    organization_id: str | None = None
    user_id: str | None = None
    memory_strength: str
    patterns: list[str]
    critical_months: list[dict[str, Any]]
    seasonality: dict[str, Any]
    critical_categories: list[dict[str, Any]]
    trend: str
    average_expense_ratio: float | None = None
    stability_index: int | None = None
    insights: list[str]
    disclaimer: str

class BehavioralIntelligenceOut(BaseModel):
    behavioral_score: int
    stability_score: int
    discipline_score: int
    risk_behavior_score: int
    signals: list[str]
    plain_language_summary: str

class AdvancedFinancialCoachingOut(BaseModel):
    messages: list[str]
    tips: list[str]
    alerts: list[dict[str, str]]
    tone: str

class DynamicGoalsOut(BaseModel):
    goals: list[dict[str, Any]]
    available_goal_capacity: float
    behavior_adjustment: float

class FinancialDecisionAdvisorOut(BaseModel):
    decision_type: str
    title: str
    recommendation: str
    reasons: list[str]
    next_steps: list[str]
    confidence: float
    disclaimer: str

class RetentionEngagementOut(BaseModel):
    milestones: list[dict[str, str]]
    progress_summary: str
    recurring_insights: list[str]

class AIFinancialAdvisorDashboardOut(BaseModel):
    year: int
    month: int
    health: FinancialHealthOut
    memory: FinancialMemoryOut
    behavioral_intelligence: BehavioralIntelligenceOut
    coaching: AdvancedFinancialCoachingOut
    dynamic_goals: DynamicGoalsOut
    forecast: FinancialForecastOut
    decision_advisor: FinancialDecisionAdvisorOut
    retention: RetentionEngagementOut
    timeline: FinancialTimelineOut
    advisor_main_message: str
    next_best_action: str
    disclaimer: str


class AdvisorQuestionIn(BaseModel):
    question: str = Field(min_length=2, max_length=600)
    year: int | None = None
    month: int | None = None

class AdvisorAnswerOut(BaseModel):
    intent: str
    answer: str
    used_real_data: bool = True
    confidence: float
    recommended_action: str
    context_cards: list[dict[str, Any]] = Field(default_factory=list)
    quick_actions: list[str] = Field(default_factory=list)
    safety_warnings: list[str] = Field(default_factory=list)
    disclaimer: str
    premium_advisor: dict[str, Any] = Field(default_factory=dict)
    conversation_memory: dict[str, Any] = Field(default_factory=dict)
    rag_context: list[dict[str, Any]] = Field(default_factory=list)
    ai_analytics: dict[str, Any] = Field(default_factory=dict)
    provider: str = "local_fallback"

class FinancialContextOut(BaseModel):
    organization_id: str
    user_id: str
    year: int
    month: int
    current_financial_situation: dict[str, Any]
    recommended_model: str
    health: dict[str, Any]
    financial_phase: str | None = None
    goals: list[dict[str, Any]] = Field(default_factory=list)
    investment_capacity: float
    alerts: list[Any] = Field(default_factory=list)
    behavior: dict[str, Any] = Field(default_factory=dict)
    memory: dict[str, Any] = Field(default_factory=dict)
    forecast: dict[str, Any] = Field(default_factory=dict)
    next_steps: list[str] = Field(default_factory=list)

class CopilotEventOut(BaseModel):
    type: str
    severity: str
    message: str
    impact: str
    suggested_action: str
    related_entity: str | None = None
    created_at: str

class UserLearningProfileOut(BaseModel):
    organization_id: str
    user_id: str
    financial_literacy_level: str
    preferred_tone: str
    preferred_detail_level: str
    observed_risk_behavior: str
    recurring_challenges: list[str] = Field(default_factory=list)
    engagement_score: int
    last_updated_at: datetime | None = None

class ConversationalAdvisorDashboardOut(BaseModel):
    context_summary: FinancialContextOut
    copilot_events: list[CopilotEventOut]
    suggested_questions: list[str]
    main_message: str
    next_step: str
    disclaimer: str
