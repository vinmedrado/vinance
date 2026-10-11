from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class FixedIncomeEvaluation(BaseModel):
    model_config = ConfigDict(extra="allow")

    product_id: int | None = None
    source_product_id: str
    product_name: str
    product_type: str
    asset_class: Literal["FIXED_INCOME"] = "FIXED_INCOME"
    market: Literal["FIXED_INCOME"] = "FIXED_INCOME"
    eligibility: Literal["ELIGIBLE", "LIMITED", "INELIGIBLE", "UNKNOWN"]
    action: Literal["BUY", "WAIT", "AVOID", "NO_RECOMMENDATION"]
    guardrail_status: Literal["APPROVED", "WARNING", "BLOCKED"]
    suitability: str
    liquidity_assessment: str
    maturity_fit: str
    risk_assessment: str
    recommendation_score: Decimal | None = None
    minimum_investment: Decimal | None = Field(default=None, ge=0)
    candidate_amount: Decimal = Field(ge=0)
    market_date: date | None = None
    data_timestamp: datetime | None = None
    freshness_status: str
    confidence: Decimal | None = None
    warnings: list[Any]
    blockers: list[Any]
    reasons: list[Any]
    evidence: list[Any]
    rule_traces: list[Any]
