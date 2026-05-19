from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field

RiskProfile = Literal["conservador", "moderado", "arrojado", "agressivo"]
MarketType = Literal["renda_fixa", "fii", "etf", "acao", "internacional", "cripto", "caixa"]


class InvestmentDecisionRequest(BaseModel):
    monthly_income: float = Field(default=0, ge=0)
    monthly_expenses: float = Field(default=0, ge=0)
    cash_available: float = Field(default=0, ge=0)
    emergency_reserve_current: float = Field(default=0, ge=0)
    risk_profile: RiskProfile = "moderado"
    horizon_months: int = Field(default=24, ge=1, le=600)
    objective: str = "crescimento patrimonial"


class BacktestRequest(BaseModel):
    ticker: str = "BOVA11"
    initial_capital: float = Field(default=10000, ge=100)
    monthly_contribution: float = Field(default=500, ge=0)
    strategy: str = "momentum_quality"
    horizon_months: int = Field(default=36, ge=6, le=240)
    risk_profile: RiskProfile = "moderado"


class TrainModelRequest(BaseModel):
    market: MarketType | str = "etf"
    risk_profile: RiskProfile = "moderado"
    horizon_months: int = Field(default=24, ge=1, le=240)
    capital: float = Field(default=10000, ge=0)
