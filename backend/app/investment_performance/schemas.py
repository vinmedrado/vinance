from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


Horizon = Literal["1d", "7d", "30d"]
ResultClassification = Literal[
    "STRONGLY_CORRECT",
    "CORRECT",
    "NEUTRAL",
    "INCORRECT",
    "STRONGLY_INCORRECT",
]


class PerformanceMetricGroup(BaseModel):
    model_config = ConfigDict(extra="allow")

    key: str
    total: int = Field(ge=0)
    total_eligible: int = Field(ge=0)
    evaluated: int = Field(ge=0)
    pending: int = Field(ge=0)
    average_return_pct: float | None = None
    median_return_pct: float | None = None
    positive_pct: float | None = None
    negative_pct: float | None = None
    directional_accuracy_pct: float | None = None
    directional_sample: int = Field(default=0, ge=0)
    neutral: int = Field(default=0, ge=0)


class PerformanceSummary(BaseModel):
    as_of: datetime
    selected_horizon: Horizon | None = None
    total_decisions: int = Field(ge=0)
    eligible_decisions: int = Field(ge=0)
    evaluated: int = Field(ge=0)
    pending: int = Field(ge=0)
    average_return_pct: float | None = None
    median_return_pct: float | None = None
    positive_pct: float | None = None
    negative_pct: float | None = None
    directional_accuracy_pct: float | None = None
    directional_sample: int = Field(ge=0)
    by_horizon: list[PerformanceMetricGroup]
    by_action: list[PerformanceMetricGroup]
    by_asset: list[PerformanceMetricGroup]
    by_risk: list[PerformanceMetricGroup]
    by_trend: list[PerformanceMetricGroup] = Field(default_factory=list)
    by_confidence: list[PerformanceMetricGroup]
    by_score_band: list[PerformanceMetricGroup]
    by_profile: list[PerformanceMetricGroup]
    by_rule_version: list[PerformanceMetricGroup]
    by_recommendation_engine_version: list[PerformanceMetricGroup]
    by_score_version: list[PerformanceMetricGroup]
    by_guardrail_version: list[PerformanceMetricGroup]
    by_version_cohort: list[PerformanceMetricGroup]
    mixed_versions: bool
    calibration: list[PerformanceMetricGroup]
    calibration_summary: dict[str, Any]
    timeline: list[PerformanceMetricGroup]


class PerformanceEvaluation(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    horizon: Horizon
    reference_price: Decimal
    reference_price_timestamp: datetime
    price_source: str
    evaluation_price: Decimal
    evaluation_timestamp: datetime
    evaluation_price_source: str
    absolute_change: Decimal
    return_pct: Decimal
    max_favorable_excursion_pct: Decimal | None = None
    max_adverse_excursion_pct: Decimal | None = None
    result_status: Literal["EVALUATED"]
    result_classification: ResultClassification
    result_context: dict[str, Any]
    evaluation_policy_version: str
    evaluated_at: datetime


class DecisionPerformanceDetail(BaseModel):
    decision_id: str
    asset: str
    action: Literal["BUY", "WAIT", "AVOID"]
    decision_created_at: datetime
    risk_level: str | None = None
    confidence: Decimal | None = None
    trend: str | None = None
    recommendation_score: Decimal | None = None
    investor_profile: str | None = None
    rule_version: str
    recommendation_engine_version: str
    score_version: str | None = None
    guardrail_version: str | None = None
    reference_price: Decimal | None = None
    reference_price_timestamp: datetime | None = None
    price_source: str | None = None
    evaluations: list[PerformanceEvaluation]
    pending_horizons: list[Horizon]
    eligible_pending_horizons: list[Horizon]
    immature_horizons: list[Horizon]
