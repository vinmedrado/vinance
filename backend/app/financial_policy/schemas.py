from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field


PolicyState = Literal[
    "DATA_BLOCKED",
    "CASHFLOW_RECOVERY",
    "DEBT_PRIORITY",
    "EMERGENCY_RESERVE_PRIORITY",
    "GOAL_PRIORITY",
    "BALANCED_BUILD",
    "INVESTMENT_READY",
]
InvestmentReadiness = Literal["BLOCKED", "LIMITED", "READY"]
PolicyGateStatus = Literal["BLOCKED", "LIMITED", "PASS"]
PriorityStatus = Literal["ACTIVE", "NEXT", "CONDITIONAL", "BLOCKED"]
RuleOutcome = Literal["TRIGGERED", "NOT_TRIGGERED", "NOT_EVALUATED"]


class PolicyMessage(BaseModel):
    code: str
    message: str
    fields: list[str]
    rule_ids: list[str]


class FinancialPriority(BaseModel):
    rank: int = Field(ge=1)
    code: str
    title: str
    explanation: str
    status: PriorityStatus
    evidence_refs: list[str]


class PolicyEvidence(BaseModel):
    code: str
    label: str
    value: Any
    unit: str
    source: str


class PolicyExplanation(BaseModel):
    code: str
    decision: str
    reason: str
    evidence_refs: list[str]
    rule_ids: list[str]
    blocked_alternatives: list[str]


class MemberPolicyView(BaseModel):
    user_id: int
    full_name: str | None
    scope: Literal["PERSONAL_ONLY"]
    policy_state: PolicyState
    investment_readiness: InvestmentReadiness
    priority_signals: list[str]
    metrics: dict[str, Any]
    goals: list[dict[str, Any]]
    missing_information: list[str]
    inconsistencies: list[str]
    explanation: str


class RuleEvaluation(BaseModel):
    rule_id: str
    rule_version: str
    description: str
    outcome: RuleOutcome
    observed_values: dict[str, Any]
    thresholds: dict[str, Any]
    explanation: str


class FinancialPolicyDataGate(BaseModel):
    status: PolicyGateStatus
    critical_missing_fields: list[str]
    readiness_missing_fields: list[str]
    critical_stale_fields: list[str]
    currencies: list[str]
    missing_currency_fields: list[str]
    readiness_limiters: list[str]


class DebtAssessment(BaseModel):
    id: int | str | None
    name: str | None
    ownership_scope: Literal["PERSONAL", "HOUSEHOLD"] | None
    user_id: int | str | None
    status: str | None
    current_balance: Decimal | None
    monthly_payment: Decimal | None
    monthly_payment_share_pct: Decimal | None
    annual_interest_rate_pct: Decimal | None
    due_date: date | None
    days_remaining: int | None
    due_assessment: Literal[
        "UNKNOWN_DUE_DATE",
        "DATE_PASSED_STATUS_ACTIVE",
        "DUE_SOON",
        "SCHEDULED",
    ]
    assessment: Literal[
        "STANDARD_KNOWN_COST",
        "DEFAULTED",
        "UNKNOWN_COST",
        "HIGH_COST",
    ]


class DebtPolicy(BaseModel):
    total_liabilities: Decimal | None
    debt_service_ratio: Decimal | None
    debt_to_income: Decimal | None
    net_worth: Decimal | None
    priority_required: bool
    investment_blocking: bool
    unknown_rate_debt_ids: list[int | str | None]
    zero_balance_payment_debt_ids: list[int | str | None]
    due_priority_debt_ids: list[int | str | None]
    due_soon_debt_ids: list[int | str | None]
    debts: list[DebtAssessment]


class ReserveModifier(BaseModel):
    code: str
    months: Decimal
    observed_pct: Decimal


class ReservePolicy(BaseModel):
    status: Literal[
        "UNKNOWN",
        "ABSENT",
        "BUILDING",
        "ADEQUATE_FOR_KNOWN_CONTEXT",
        "ADEQUATE",
    ]
    current_amount: Decimal | None
    current_months: Decimal | None
    target_months: Decimal
    target_amount: Decimal | None
    gap_amount: Decimal | None
    modifiers: list[ReserveModifier]
    target_method: Literal["PRUDENTIAL_FLOOR_PLUS_KNOWN_CONTEXT"]
    universal_target_applied: Literal[False]
    unmodeled_context: list[str]
    target_completeness: Literal["PARTIAL", "COMPLETE"]
    target_missing_context: list[str]


class GoalAssessment(BaseModel):
    id: int | str | None
    name: str | None
    ownership_scope: Literal["PERSONAL", "HOUSEHOLD"] | None
    user_id: int | str | None
    priority: str
    target_amount: Decimal | None
    current_amount: Decimal | None
    funding_gap: Decimal | None
    deadline: date | None
    days_remaining: int | None
    required_monthly_funding: Decimal | None
    available_monthly_capacity: Decimal | None
    funding_feasibility: Literal[
        "NOT_APPLICABLE",
        "UNKNOWN_GAP",
        "FUNDED",
        "UNKNOWN_DEADLINE",
        "UNKNOWN_CAPACITY",
        "EXCEEDS_CAPACITY",
        "WITHIN_CAPACITY",
    ]
    requires_priority: bool


class GoalPolicy(BaseModel):
    priority_required: bool
    priority_goal_ids: list[int | str | None]
    unknown_gap_goal_ids: list[int | str | None]
    unknown_deadline_goal_ids: list[int | str | None]
    unknown_deadline_unfunded_goal_ids: list[int | str | None]
    capacity_exceeded_goal_ids: list[int | str | None]
    unknown_funding_plan_goal_ids: list[int | str | None]
    available_monthly_capacity: Decimal | None
    goals: list[GoalAssessment]


class PolicyRuleset(BaseModel):
    version: str
    thresholds: dict[str, Any]


class SourceFinancialState(BaseModel):
    engine_version: str
    evaluated_at: datetime
    data_quality: str
    confidence: int
    snapshot_id: int | None


class PreviousFinancialState(BaseModel):
    available: bool
    comparable: bool
    evaluated_at: datetime | None
    boundary_crossings: list[str]
    snapshot_id: int | None


class FinancialPolicyRead(BaseModel):
    policy_id: int | None = None
    household_id: int
    financial_state_snapshot_id: int | None = None
    engine_version: str
    rules_version: str
    evaluated_at: datetime
    generated_at: datetime
    created_at: datetime | None = None
    input_fingerprint: str = Field(min_length=64, max_length=64)
    ruleset_fingerprint: str = Field(min_length=64, max_length=64)
    decision_fingerprint: str = Field(min_length=64, max_length=64)
    policy_state: PolicyState
    investment_readiness: InvestmentReadiness
    summary: str
    priority_stack: list[FinancialPriority]
    data_gate: FinancialPolicyDataGate
    debt_policy: DebtPolicy
    reserve_policy: ReservePolicy
    goal_policy: GoalPolicy
    blockers: list[PolicyMessage]
    warnings: list[PolicyMessage]
    limitations: list[PolicyMessage]
    missing_information: list[PolicyMessage]
    explanations: list[PolicyExplanation]
    evidence: list[PolicyEvidence]
    member_policy_views: list[MemberPolicyView]
    rules_evaluated: list[RuleEvaluation]
    ruleset: PolicyRuleset
    source_financial_state: SourceFinancialState
    previous_financial_state: PreviousFinancialState


class FinancialPolicyDecisionSummary(BaseModel):
    policy_id: int
    household_id: int
    financial_state_snapshot_id: int
    engine_version: str
    rules_version: str
    policy_state: PolicyState
    investment_readiness: InvestmentReadiness
    decision_fingerprint: str = Field(min_length=64, max_length=64)
    generated_at: datetime
    created_at: datetime


class FinancialPolicyHistory(BaseModel):
    items: list[FinancialPolicyDecisionSummary]
    total: int = Field(ge=0)
