from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

AssetMarket = Literal["fii", "acoes", "etf", "bdr", "cripto", "renda_fixa"]
VALID_MARKETS = {"fii", "acoes", "etf", "bdr", "cripto", "renda_fixa"}


def normalize_ticker(value: str) -> str:
    ticker = value.strip().upper()
    if not ticker:
        raise ValueError("ticker is required")
    return ticker


def normalize_market(value: str) -> str:
    market = value.strip().lower()
    if market not in VALID_MARKETS:
        raise ValueError("invalid market")
    return market


def default_currency_for_market(market: str) -> str:
    return "USD" if market == "cripto" else "BRL"


class AssetCatalogCreate(BaseModel):
    ticker: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=255)
    market: AssetMarket
    sector: str | None = Field(default=None, max_length=120)
    segment: str | None = Field(default=None, max_length=120)
    currency: str | None = Field(default=None, max_length=12)
    exchange: str | None = Field(default=None, max_length=80)
    source: str | None = Field(default=None, max_length=120)
    is_active: bool = True

    @field_validator("ticker")
    @classmethod
    def validate_ticker(cls, value: str) -> str:
        return normalize_ticker(value)

    @field_validator("market", mode="before")
    @classmethod
    def validate_market(cls, value: str) -> str:
        return normalize_market(str(value))

    @field_validator("currency", mode="before")
    @classmethod
    def validate_currency(cls, value: str | None) -> str | None:
        if value is None or str(value).strip() == "":
            return None
        return str(value).strip().upper()

    def normalized_payload(self) -> dict:
        data = self.model_dump()
        if data["currency"] is None:
            data["currency"] = default_currency_for_market(data["market"])
        return data


class AssetCatalogUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    sector: str | None = Field(default=None, max_length=120)
    segment: str | None = Field(default=None, max_length=120)
    currency: str | None = Field(default=None, max_length=12)
    exchange: str | None = Field(default=None, max_length=80)
    source: str | None = Field(default=None, max_length=120)
    is_active: bool | None = None

    @field_validator("currency", mode="before")
    @classmethod
    def validate_currency(cls, value: str | None) -> str | None:
        if value is None or str(value).strip() == "":
            return None
        return str(value).strip().upper()


class AssetCatalogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticker: str
    name: str
    market: AssetMarket
    sector: str | None
    segment: str | None
    currency: str
    exchange: str | None
    source: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class AssetCatalogListResponse(BaseModel):
    items: list[AssetCatalogRead]
    total: int
    limit: int
    offset: int
