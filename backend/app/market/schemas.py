from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field, field_validator

RiskProfile = Literal["Conservador", "Moderado", "Agressivo"]


class RadarRequest(BaseModel):
    amount: float = Field(gt=0, le=100_000_000)
    risk_profile: RiskProfile = "Moderado"
    symbols: list[str] | None = Field(default=None, max_length=50)
    crypto_ids: list[str] | None = Field(default=None, max_length=30)

    @field_validator("symbols")
    @classmethod
    def normalize_symbols(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return value
        cleaned = sorted({item.strip().upper() for item in value if item and item.strip()})
        return cleaned or None

    @field_validator("crypto_ids")
    @classmethod
    def normalize_crypto_ids(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return value
        cleaned = sorted({item.strip().lower() for item in value if item and item.strip()})
        return cleaned or None


class OpportunityOut(BaseModel):
    symbol: str
    asset_class: str
    score: float
    classification: str
    metrics: dict[str, Any] = Field(default_factory=dict)
    rationale: str | None = None


class RadarResponse(BaseModel):
    amount: float
    risk_profile: RiskProfile
    allocation: dict[str, float]
    macro_context: dict[str, Any]
    opportunities: list[OpportunityOut]
    disclaimer: str
