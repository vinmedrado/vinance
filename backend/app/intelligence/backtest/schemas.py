from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

MarketName = Literal["acoes", "fii", "etf", "bdr", "cripto"]
RebalanceFrequency = Literal["daily", "weekly", "monthly"]


class BacktestRunRequest(BaseModel):
    market: MarketName
    start_date: date
    end_date: date
    holding_period_days: int = Field(default=90, ge=1, le=365)
    top_n: int = Field(default=5, ge=1, le=50)
    rebalance_frequency: RebalanceFrequency = "monthly"


class BacktestMetrics(BaseModel):
    total_return: float | None = None
    annualized_return: float | None = None
    volatility: float | None = None
    sharpe_ratio: float | None = None
    max_drawdown: float | None = None
    win_rate: float | None = None
    hit_rate_top_n: float | None = None


class BacktestParameters(BaseModel):
    market: str
    start_date: date
    end_date: date
    holding_period_days: int
    top_n: int
    rebalance_frequency: str


class BacktestRunResponse(BaseModel):
    parameters: BacktestParameters
    metrics: BacktestMetrics
    warnings: list[str]
    sample_size: int
    methodology: list[str]


class BacktestSummaryItem(BaseModel):
    market: str
    feature_rows: int
    price_rows: int
    latest_feature_date: date | None = None
    latest_price_date: date | None = None


class BacktestSummaryResponse(BaseModel):
    markets: list[BacktestSummaryItem]
    methodology: list[str]
    warnings: list[str]
