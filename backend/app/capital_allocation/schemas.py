from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field


AllocationStatus = Literal["BLOCKED", "CONSTRAINED", "ACTIVE", "SURPLUS"]
AllocationPeriod = Literal["MONTHLY"]
BucketType = Literal[
    "INFORMATIONAL",
    "PROTECTED_CAPITAL",
    "GOAL_CAPITAL",
    "INVESTMENT_CAPITAL",
    "SPECULATIVE_CAPITAL",
]
AllocationItemStatus = Literal[
    "NOT_CALCULABLE",
    "UNFUNDED",
    "PARTIALLY_FUNDED",
    "FUNDED",
    "ALLOCATED",
    "BLOCKED",
]
AllocationGateStatus = Literal["BLOCKED", "LIMITED", "PASS"]
AllocationRuleOutcome = Literal["TRIGGERED", "NOT_TRIGGERED", "NOT_EVALUATED"]


class AllocationMessage(BaseModel):
    code: str
    message: str
    fields: list[str]
    rule_ids: list[str]


class AllocationEvidence(BaseModel):
    code: str
    label: str
    value: Any
    unit: str
    source: str


class AllocationRuleEvaluation(BaseModel):
    rule_id: str
    rule_version: str
    description: str
    outcome: AllocationRuleOutcome
    observed_values: dict[str, Any]
    rule_parameters: dict[str, Any]
    explanation: str


class AllocationItem(BaseModel):
    priority_code: str
    priority_rank: int = Field(ge=1)
    bucket_type: BucketType
    target_type: Literal[
        "DATA",
        "CASH_FLOW",
        "LIABILITY",
        "EMERGENCY_RESERVE",
        "GOAL",
        "INVESTMENT",
    ]
    target_id: int | str | None
    target_name: str | None
    ownership_scope: Literal["PERSONAL", "HOUSEHOLD"] | None
    user_id: int | str | None
    requested_amount: Decimal | None
    allocated_amount: Decimal = Field(ge=0)
    remaining_need: Decimal | None = Field(default=None, ge=0)
    status: AllocationItemStatus
    reason: str
    evidence_refs: list[str]


class AllocationBucketTotals(BaseModel):
    protected_capital: Decimal = Field(ge=0)
    goal_capital: Decimal = Field(ge=0)
    investment_capital: Decimal = Field(ge=0)
    speculative_capital: Decimal = Field(ge=0, le=0)


class AllocationMemberImpact(BaseModel):
    user_id: int
    full_name: str | None
    personal_allocatable_capital: Decimal | None = Field(default=None, ge=0)
    allocated_to_personal_priorities: Decimal = Field(ge=0)
    remaining_personal_capacity: Decimal | None = Field(default=None, ge=0)
    explanation: str


class CapitalAllocationDataGate(BaseModel):
    status: AllocationGateStatus
    state_quality: str
    state_confidence: int | None
    policy_state: str | None
    investment_readiness: str | None
    currencies: list[str]
    critical_stale_fields: list[str]
    consistency_checks: dict[str, bool]


class SourceFinancialStateReference(BaseModel):
    engine_version: str | None
    evaluated_at: datetime | None
    snapshot_id: int | None
    data_quality: str | None
    confidence: int | None


class SourceFinancialPolicyReference(BaseModel):
    engine_version: str | None
    rules_version: str | None
    policy_id: int | None
    policy_state: str | None
    investment_readiness: str | None
    decision_fingerprint: str


class CapitalAllocationRuleset(BaseModel):
    version: str
    rules: dict[str, Any]


class CapitalAllocationRead(BaseModel):
    allocation_id: int | None = None
    household_id: int
    financial_state_snapshot_id: int | None
    financial_policy_id: int | None
    engine_version: str
    rules_version: str
    allocation_period: AllocationPeriod
    allocation_status: AllocationStatus
    currency: str
    allocatable_capital: Decimal | None = Field(default=None, ge=0)
    allocated_capital: Decimal = Field(ge=0)
    remaining_capital: Decimal | None = Field(default=None, ge=0)
    investment_bucket_amount: Decimal = Field(ge=0)
    bucket_totals: AllocationBucketTotals
    allocations: list[AllocationItem]
    unfunded_priorities: list[AllocationItem]
    member_impacts: list[AllocationMemberImpact]
    blockers: list[AllocationMessage]
    warnings: list[AllocationMessage]
    missing_information: list[AllocationMessage]
    evidence: list[AllocationEvidence]
    rules_evaluated: list[AllocationRuleEvaluation]
    data_gate: CapitalAllocationDataGate
    ruleset: CapitalAllocationRuleset
    source_financial_state: SourceFinancialStateReference
    source_financial_policy: SourceFinancialPolicyReference
    input_fingerprint: str = Field(min_length=64, max_length=64)
    policy_fingerprint: str = Field(min_length=64, max_length=64)
    ruleset_fingerprint: str = Field(min_length=64, max_length=64)
    decision_fingerprint: str = Field(min_length=64, max_length=64)
    generated_at: datetime
    created_at: datetime | None = None


class CapitalAllocationDecisionSummary(BaseModel):
    allocation_id: int
    household_id: int
    financial_state_snapshot_id: int
    financial_policy_id: int
    engine_version: str
    rules_version: str
    allocation_period: AllocationPeriod
    allocation_status: AllocationStatus
    currency: str
    allocatable_capital: Decimal | None
    allocated_capital: Decimal
    investment_bucket_amount: Decimal
    decision_fingerprint: str = Field(min_length=64, max_length=64)
    generated_at: datetime
    created_at: datetime


class CapitalAllocationHistory(BaseModel):
    items: list[CapitalAllocationDecisionSummary]
    total: int = Field(ge=0)
