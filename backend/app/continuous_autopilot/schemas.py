from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


ContinuousStatus = Literal[
    "UP_TO_DATE",
    "REEVALUATION_REQUIRED",
    "EVALUATING",
    "CHANGED",
    "UNCHANGED",
    "BLOCKED",
    "FAILED",
]
Materiality = Literal["NONE", "LOW", "MEDIUM", "HIGH", "CRITICAL"]
AlertDecision = Literal[
    "NO_ALERT", "INFORMATIONAL", "ACTION_RECOMMENDED", "IMPORTANT", "CRITICAL"
]
ChangeCategory = Literal[
    "FINANCIAL_DATA",
    "MARKET_DATA",
    "PROFILE",
    "GOALS",
    "DEBT",
    "ASSETS",
    "HOUSEHOLD",
    "POLICY",
    "ALLOCATION",
    "INVESTMENT_OPPORTUNITY",
    "DATA_QUALITY",
    "FRESHNESS",
]
ReevaluationScope = Literal["NONE", "FULL_CHAIN", "INVESTMENT_CHAIN"]


class ContinuousMessage(BaseModel):
    code: str
    message: str
    fields: list[str] = Field(default_factory=list)
    rule_ids: list[str] = Field(default_factory=list)


class DetectedChange(BaseModel):
    change_id: str
    change_type: str
    category: ChangeCategory
    entity_type: str
    entity_id: int | str | None = None
    previous_value: Any = None
    current_value: Any = None
    delta: Decimal | None = None
    delta_percent: Decimal | None = None
    severity: Literal["INFO", "WARNING", "IMPORTANT", "CRITICAL"]
    materiality: Materiality
    reason: str
    source: str
    observed_at: datetime
    as_of: datetime
    previous_fingerprint: str | None = None
    current_fingerprint: str | None = None
    ownership_scope: Literal["PERSONAL", "HOUSEHOLD"] | None = None
    owner_user_id: int | str | None = None


class ActionPlanDiff(BaseModel):
    previous_action_plan_id: int | None
    current_action_plan_id: int | None
    added_actions: list[dict[str, Any]]
    removed_actions: list[dict[str, Any]]
    changed_actions: list[dict[str, Any]]
    unchanged_actions: list[str]
    financial_delta: Decimal | None
    investment_delta: Decimal | None
    hold_cash_delta: Decimal | None
    priority_changes: list[dict[str, Any]]
    status_change: dict[str, Any] | None
    materiality: Materiality
    summary: str


class ContinuousAlertPayload(BaseModel):
    severity: AlertDecision
    category: ChangeCategory | None = None
    title: str
    summary: str
    what_changed: list[str]
    why_it_matters: str
    recommended_action: str
    previous_reference: dict[str, Any]
    current_reference: dict[str, Any]
    dedupe_key: str = Field(min_length=64, max_length=64)


class ContinuousAutopilotRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    continuous_decision_id: int | None = None
    household_id: int
    previous_action_plan_id: int | None = None
    current_action_plan_id: int | None = None
    engine_version: str
    rules_version: str
    status: ContinuousStatus
    materiality: Materiality
    alert_decision: AlertDecision
    reevaluation_scope: ReevaluationScope
    change_categories: list[ChangeCategory]
    detected_changes: list[DetectedChange]
    plan_diff: ActionPlanDiff
    alert: ContinuousAlertPayload | None = None
    blockers: list[ContinuousMessage]
    warnings: list[ContinuousMessage]
    missing_information: list[ContinuousMessage]
    evidence: list[dict[str, Any]]
    rule_traces: list[dict[str, Any]]
    ruleset: dict[str, Any]
    previous_fingerprint: str | None = Field(default=None, min_length=64, max_length=64)
    current_fingerprint: str | None = Field(default=None, min_length=64, max_length=64)
    ruleset_fingerprint: str = Field(min_length=64, max_length=64)
    decision_fingerprint: str = Field(min_length=64, max_length=64)
    dedupe_key: str = Field(min_length=64, max_length=64)
    generated_at: datetime
    observed_at: datetime
    created_at: datetime | None = None
    operational_status: ContinuousStatus | None = None
    pending_categories: list[ChangeCategory] = Field(default_factory=list)
    last_evaluated_at: datetime | None = None
    last_successful_at: datetime | None = None
    operational_warnings: list[ContinuousMessage] = Field(default_factory=list)


class ContinuousAutopilotSummary(BaseModel):
    continuous_decision_id: int
    household_id: int
    previous_action_plan_id: int | None
    current_action_plan_id: int
    status: ContinuousStatus
    materiality: Materiality
    alert_decision: AlertDecision
    title: str
    summary: str
    change_count: int = Field(ge=0)
    decision_fingerprint: str = Field(min_length=64, max_length=64)
    observed_at: datetime
    generated_at: datetime
    created_at: datetime


class ContinuousAutopilotHistory(BaseModel):
    items: list[ContinuousAutopilotSummary]
    total: int = Field(ge=0)


class ContinuousEvaluationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
