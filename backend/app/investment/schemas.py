from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

AssetClass = Literal["renda_fixa", "lci_lca", "fii", "acao", "bdr", "etf", "cripto", "caixa_reserva"]


class YFinanceSyncRequest(BaseModel):
    symbols: list[str] = Field(min_length=1, max_length=80)
    asset_class: AssetClass
    start: date | None = None
    end: date | None = None

    @field_validator("symbols")
    @classmethod
    def normalize_symbols(cls, value: list[str]) -> list[str]:
        return sorted({item.strip().upper() for item in value if item and item.strip()})


class FixedIncomeProductIn(BaseModel):
    issuer: str
    product_type: Literal["Tesouro", "CDB", "LCI", "LCA", "Renda Fixa"]
    name: str
    indexer: str
    rate: float
    maturity_date: datetime | None = None
    liquidity_days: int = Field(default=0, ge=0)
    guarantee_type: str | None = None
    minimum_investment: float = Field(default=0, ge=0)


class FixedIncomeImportRequest(BaseModel):
    products: list[FixedIncomeProductIn] = Field(min_length=1, max_length=500)


class AllocationRequest(BaseModel):
    capital: float = Field(default=0, ge=0)
    monthly_debt_payment: float = Field(default=0, ge=0)


class SyncResponse(BaseModel):
    status: str
    inserted: int = 0
    updated: int = 0
    skipped: int = 0
    warnings: list[str] = Field(default_factory=list)


class AssetOut(BaseModel):
    symbol: str
    name: str | None = None
    asset_class: str
    source: str | None = None
    currency: str | None = None
    country: str | None = None
    last_updated_at: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
