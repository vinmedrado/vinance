from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

AssetClass = Literal["renda_fixa", "fii", "acoes", "etf", "bdr", "cripto"]
RiskProfile = Literal["conservative", "moderate", "aggressive"]


class AllocationItem(BaseModel):
    asset_class: AssetClass
    percentage: Decimal = Field(ge=0, le=100)
    amount: Decimal = Field(ge=0)


class AssetScoreRead(BaseModel):
    ticker: str
    name: str | None = None
    asset_class: AssetClass
    score: int = Field(ge=0, le=100)
    reasons: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    methodology: str


class RecommendationClassRead(BaseModel):
    asset_class: AssetClass
    allocation_percentage: Decimal = Field(ge=0, le=100)
    allocation_amount: Decimal = Field(ge=0)
    assets: list[AssetScoreRead] = Field(default_factory=list)
    message: str | None = None


class RecommendationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    financial_score: int = Field(ge=0, le=100)
    investment_capacity: Decimal = Field(ge=0)
    adjusted_risk_profile: RiskProfile
    allocation: list[AllocationItem]
    recommendations_by_class: list[RecommendationClassRead]
    warnings: list[str] = Field(default_factory=list)
    methodology: list[str] = Field(default_factory=list)

from datetime import date as _date
from decimal import Decimal as _Decimal
from typing import Any as _Any

from pydantic import BaseModel as _BaseModel, ConfigDict as _ConfigDict


class AssetScoreRankingItem(_BaseModel):
    model_config = _ConfigDict(from_attributes=True)

    ticker: str
    market: str
    date: _date
    score_total: _Decimal
    score_value: _Decimal | None = None
    score_quality: _Decimal | None = None
    score_dividend: _Decimal | None = None
    score_liquidity: _Decimal | None = None
    score_risk: _Decimal | None = None
    price: _Decimal | None = None
    metadata_json: dict[str, _Any]


class BudgetAdvisorItem(_BaseModel):
    ticker: str
    market: str
    score_total: _Decimal
    price: _Decimal
    quantity_possible: int
    invested_amount: _Decimal
    profile: str
    profile_score: _Decimal | None = None
    recommendation_score: _Decimal | None = None
    recommendation_components_json: dict[str, _Any] | None = None
    trend_label: str | None = None
    momentum_score: _Decimal | None = None
    trend_confidence: str | None = None
    trend_method: str | None = None
    status: str
    risk_level: str
    reasons_json: dict[str, _Any]


class DiversifiedBudgetAllocationItem(_BaseModel):
    allocation: str
    market: str
    ticker: str
    quantity: int
    price: _Decimal
    invested_amount: _Decimal
    score_total: _Decimal
    profile: str
    profile_score: _Decimal | None = None
    recommendation_score: _Decimal | None = None
    recommendation_components_json: dict[str, _Any] | None = None
    trend_label: str | None = None
    momentum_score: _Decimal | None = None
    trend_confidence: str | None = None
    trend_method: str | None = None
    status: str
    risk_level: str
    reasons_json: dict[str, _Any]


class DiversifiedBudgetAdvisorResponse(_BaseModel):
    budget: _Decimal
    profile: str
    total_invested: _Decimal
    remaining_budget: _Decimal
    allocation: list[DiversifiedBudgetAllocationItem]


class GuardrailItem(_BaseModel):
    model_config = _ConfigDict(from_attributes=True)

    ticker: str
    market: str
    date: _date
    status: str
    risk_level: str
    penalty_score: _Decimal
    reasons_json: dict[str, _Any]
    source: str


class TrendSignalItem(_BaseModel):
    model_config = _ConfigDict(from_attributes=True)

    ticker: str
    market: str
    date: _date
    price: _Decimal | None = None
    return_1d: _Decimal | None = None
    return_7d: _Decimal | None = None
    return_30d: _Decimal | None = None
    return_90d: _Decimal | None = None
    volatility_30d: _Decimal | None = None
    momentum_score: _Decimal
    trend_label: str
    risk_label: str
    metadata_json: dict[str, _Any]
