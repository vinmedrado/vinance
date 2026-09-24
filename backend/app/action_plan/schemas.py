from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


ActionPlanStatus = Literal["BLOCKED", "PARTIAL", "READY", "NO_ACTION_REQUIRED"]
ActionCategory = Literal["INFORMATION", "FINANCIAL", "INVESTMENT", "HOLD"]
ActionType = Literal[
    "COMPLETE_INFORMATION",
    "STABILIZE_CASHFLOW",
    "DEBT_PAYMENT",
    "EMERGENCY_RESERVE_CONTRIBUTION",
    "GOAL_CONTRIBUTION",
    "INVESTMENT_BUY",
    "INVESTMENT_WAIT",
    "INVESTMENT_AVOID",
    "HOLD_CASH",
    "NO_ACTION",
]
ActionStatus = Literal[
    "ACTIONABLE", "INFORMATIONAL", "WAIT", "AVOID", "BLOCKED", "NO_ACTION"
]


class ActionPlanMessage(BaseModel):
    code: str
    message: str
    fields: list[str]
    rule_ids: list[str]


class ActionPlanEvidence(BaseModel):
    code: str
    label: str
    value: Any
    unit: str | None
    source: str


class ActionPlanRuleTrace(BaseModel):
    rule_id: str
    rule_version: str
    description: str
    outcome: Literal["TRIGGERED", "NOT_TRIGGERED", "NOT_EVALUATED"]
    observed_values: dict[str, Any]
    rule_parameters: dict[str, Any]
    explanation: str


class ActionPlanItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_id: str
    category: ActionCategory
    action_type: ActionType
    priority_rank: int = Field(ge=1)
    title: str
    description: str
    ownership_scope: Literal["PERSONAL", "HOUSEHOLD"] | None
    owner_user_id: int | str | None
    household_id: int
    currency: str | None
    amount: Decimal | None = Field(default=None, ge=0)
    target_amount: Decimal | None = Field(default=None, ge=0)
    remaining_need: Decimal | None = Field(default=None, ge=0)
    liability_id: int | str | None = None
    goal_id: int | str | None = None
    asset_id: int | None = None
    symbol: str | None = None
    asset_class: str | None = None
    quantity_candidate: int | None = Field(default=None, ge=0)
    price_reference: Decimal | None = Field(default=None, ge=0)
    price_timestamp: datetime | None = None
    price_source: str | None = None
    freshness_status: str | None = None
    action_status: ActionStatus
    severity: Literal["INFO", "WARNING", "CRITICAL"]
    reason: str
    evidence: list[Any]
    warnings: list[Any]
    blockers: list[Any]
    missing_information: list[Any]
    source_engine: str
    source_decision_id: int | str | None
    source_reference: dict[str, Any]
    generated_at: datetime

    @model_validator(mode="after")
    def validate_ownership(self):
        owner_is_missing = (
            self.owner_user_id is None
            or isinstance(self.owner_user_id, bool)
            or (
                isinstance(self.owner_user_id, int)
                and self.owner_user_id <= 0
            )
            or (
                isinstance(self.owner_user_id, str)
                and not self.owner_user_id.strip()
            )
        )
        if self.ownership_scope == "PERSONAL" and owner_is_missing:
            raise ValueError("PERSONAL actions require owner_user_id")
        if self.ownership_scope is None and not owner_is_missing:
            raise ValueError("owner_user_id requires an explicit ownership_scope")
        return self


class ActionPlanSummary(BaseModel):
    authorized_financial_capital: Decimal | None = Field(default=None, ge=0)
    authorized_investment_capital: Decimal | None = Field(default=None, ge=0)
    financial_actions_total: Decimal = Field(ge=0)
    investment_buy_total: Decimal = Field(ge=0)
    hold_cash_total: Decimal = Field(ge=0)
    action_count: int = Field(ge=0)
    primary_action: str | None


class ActionPlanRead(BaseModel):
    action_plan_id: int | None = None
    household_id: int
    financial_state_snapshot_id: int | None
    financial_policy_decision_id: int | None
    capital_allocation_decision_id: int | None
    investment_orchestration_decision_id: int | None
    engine_version: str
    rules_version: str
    status: ActionPlanStatus
    currency: str | None
    period: Literal["MONTHLY"] | None
    summary: ActionPlanSummary
    actions: list[ActionPlanItem]
    information_actions: list[ActionPlanItem]
    financial_actions: list[ActionPlanItem]
    investment_actions: list[ActionPlanItem]
    hold_actions: list[ActionPlanItem]
    total_financial_actions: Decimal = Field(ge=0)
    total_investment_actions: Decimal = Field(ge=0)
    total_hold_cash: Decimal = Field(ge=0)
    speculative_capital: Decimal = Field(ge=0, le=0)
    trading_dispatch: Literal[False]
    blockers: list[ActionPlanMessage]
    warnings: list[ActionPlanMessage]
    missing_information: list[ActionPlanMessage]
    evidence: list[ActionPlanEvidence]
    rule_traces: list[ActionPlanRuleTrace]
    state_fingerprint: str = Field(min_length=64, max_length=64)
    policy_fingerprint: str | None = Field(default=None, min_length=64, max_length=64)
    allocation_fingerprint: str | None = Field(default=None, min_length=64, max_length=64)
    orchestration_fingerprint: str | None = Field(default=None, min_length=64, max_length=64)
    ruleset_fingerprint: str = Field(min_length=64, max_length=64)
    decision_fingerprint: str = Field(min_length=64, max_length=64)
    generated_at: datetime
    created_at: datetime | None = None


class ActionPlanDecisionSummary(BaseModel):
    action_plan_id: int
    household_id: int
    financial_state_snapshot_id: int
    financial_policy_decision_id: int
    capital_allocation_decision_id: int
    investment_orchestration_decision_id: int
    engine_version: str
    rules_version: str
    status: ActionPlanStatus
    currency: str
    period: Literal["MONTHLY"]
    primary_action: str | None
    action_titles: list[str]
    action_count: int = Field(ge=0)
    investment_budget: Decimal = Field(ge=0)
    total_financial_actions: Decimal = Field(ge=0)
    total_investment_actions: Decimal = Field(ge=0)
    total_hold_cash: Decimal = Field(ge=0)
    decision_fingerprint: str = Field(min_length=64, max_length=64)
    generated_at: datetime
    created_at: datetime


class ActionPlanHistory(BaseModel):
    items: list[ActionPlanDecisionSummary]
    total: int = Field(ge=0)
