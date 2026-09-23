from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


OrchestrationStatus = Literal[
    "BLOCKED", "LIMITED", "ACTIVE", "NO_SUITABLE_OPPORTUNITY"
]
Eligibility = Literal["ELIGIBLE", "LIMITED", "INELIGIBLE", "UNKNOWN"]
OpportunityAction = Literal["BUY", "WAIT", "AVOID", "NO_RECOMMENDATION"]


class OrchestrationMessage(BaseModel):
    code: str
    message: str
    fields: list[str]
    rule_ids: list[str]


class OrchestrationEvidence(BaseModel):
    code: str
    label: str
    value: Any
    unit: str
    source: str


class OrchestrationRuleTrace(BaseModel):
    rule_id: str
    rule_version: str
    description: str
    outcome: Literal["TRIGGERED", "NOT_TRIGGERED", "NOT_EVALUATED"]
    observed_values: dict[str, Any]
    rule_parameters: dict[str, Any]
    explanation: str


class AssetClassDecision(BaseModel):
    asset_class: str
    market: str | None
    eligibility: Eligibility
    reason: str
    risk_fit: str
    liquidity_fit: str
    data_quality: str
    constraints: list[str]
    opportunity_count: int = Field(ge=0)
    eligible_opportunity_count: int = Field(ge=0)


class ClassAllocation(BaseModel):
    asset_class: str
    market: str
    signal_score: Decimal = Field(ge=0)
    allocated_amount: Decimal = Field(ge=0)
    suggested_capital: Decimal = Field(ge=0)
    remaining_cash: Decimal = Field(ge=0)
    method: str


class RankedOpportunity(BaseModel):
    model_config = ConfigDict(extra="allow")

    asset_id: int | None = None
    symbol: str
    ticker: str | None = None
    asset_class: str
    market: str
    action: OpportunityAction
    rank: int | None = Field(default=None, ge=1)
    price_reference: Decimal | None = Field(default=None, ge=0)
    quantity_candidate: int = Field(default=0, ge=0)
    quantity_suggested: int = Field(default=0, ge=0)
    capital_required: Decimal = Field(default=Decimal("0.00"), ge=0)
    capital_committed: Decimal = Field(default=Decimal("0.00"), ge=0)
    recommendation_score: Decimal | None = None
    risk_level: str
    trend_label: str | None = None
    momentum_score: Decimal | None = None
    confidence: Decimal | None = None
    guardrail_status: str
    reasons: list[Any]
    warnings: list[Any]
    reason: str


class InvestmentOrchestrationRead(BaseModel):
    orchestration_id: int | None = None
    household_id: int
    financial_state_snapshot_id: int | None
    financial_policy_decision_id: int | None
    capital_allocation_decision_id: int | None
    engine_version: str
    rules_version: str
    status: OrchestrationStatus
    currency: str
    investment_budget: Decimal = Field(ge=0)
    profile_context: dict[str, Any]
    portfolio_context: dict[str, Any]
    market_context: dict[str, Any]
    asset_class_decisions: list[AssetClassDecision]
    class_allocations: list[ClassAllocation]
    ranked_opportunities: list[RankedOpportunity]
    suggested_capital: Decimal = Field(ge=0)
    remaining_investment_cash: Decimal = Field(ge=0)
    speculative_capital: Decimal = Field(ge=0, le=0)
    trading_dispatch: Literal[False]
    blockers: list[OrchestrationMessage]
    warnings: list[OrchestrationMessage]
    missing_information: list[OrchestrationMessage]
    evidence: list[OrchestrationEvidence]
    rule_traces: list[OrchestrationRuleTrace]
    state_fingerprint: str = Field(min_length=64, max_length=64)
    policy_fingerprint: str = Field(min_length=64, max_length=64)
    allocation_fingerprint: str = Field(min_length=64, max_length=64)
    market_context_fingerprint: str = Field(min_length=64, max_length=64)
    ruleset_fingerprint: str = Field(min_length=64, max_length=64)
    decision_fingerprint: str = Field(min_length=64, max_length=64)
    generated_at: datetime
    created_at: datetime | None = None


class InvestmentOrchestrationDecisionSummary(BaseModel):
    orchestration_id: int
    household_id: int
    financial_state_snapshot_id: int
    financial_policy_decision_id: int
    capital_allocation_decision_id: int
    engine_version: str
    rules_version: str
    status: OrchestrationStatus
    currency: str
    investment_budget: Decimal = Field(ge=0)
    suggested_capital: Decimal = Field(ge=0)
    remaining_investment_cash: Decimal = Field(ge=0)
    decision_fingerprint: str = Field(min_length=64, max_length=64)
    generated_at: datetime
    created_at: datetime


class InvestmentOrchestrationHistory(BaseModel):
    items: list[InvestmentOrchestrationDecisionSummary]
    total: int = Field(ge=0)
