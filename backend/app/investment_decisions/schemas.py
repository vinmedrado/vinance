from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DecisionHistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    decision_id: str
    correlation_id: str
    created_at: datetime
    asset: str | None = None
    market: str | None = None
    budget: Decimal
    investor_profile: str | None = None
    recommendation: str
    quantity: int | None = None
    price: Decimal | None = None
    invested_amount: Decimal | None = None
    remaining_amount: Decimal | None = None
    risk_level: str | None = None
    confidence: Decimal | None = None
    trend: str | None = None
    ranking: int | None = None
    recommendation_score: Decimal | None = None
    guardrail_status: str | None = None
    latency_ms: int
    fallback_used: bool
    error_code: str | None = None
    status: str


class DecisionHistoryPage(BaseModel):
    items: list[DecisionHistoryItem]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total: int = Field(ge=0)
    total_pages: int = Field(ge=0)


class DecisionDetail(DecisionHistoryItem):
    guardrail_reasons: dict[str, Any]
    explanation: dict[str, Any]
    request_parameters: dict[str, Any]
    input_snapshot: dict[str, Any]
    score_snapshot: dict[str, Any]
    response_snapshot: dict[str, Any]
    snapshot_schema_version: str
    rule_version: str
    recommendation_engine_version: str
    score_version: str | None = None
    guardrail_version: str | None = None
    trend_version: str | None = None


class DecisionMetrics(BaseModel):
    total_decisions: int
    comprar: int
    aguardar: int
    evitar: int
    errors: int
    fallbacks: int
    average_latency_ms: float
    p95_latency_ms: float
    by_profile: dict[str, int]
    by_risk: dict[str, int]
    top_assets: list[dict[str, Any]]
