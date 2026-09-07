from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Date, DateTime, Index, Integer, JSON, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base


class AssetRecommendationGuardrail(Base):
    __tablename__ = "asset_recommendation_guardrails"
    __table_args__ = (
        UniqueConstraint("ticker", "market", "date", "source", name="uq_asset_recommendation_guardrails_ticker_market_date_source"),
        Index("ix_asset_recommendation_guardrails_market_status_date", "market", "status", "date"),
        Index("ix_asset_recommendation_guardrails_ticker_market", "ticker", "market"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticker: Mapped[str] = mapped_column(String(32), nullable=False)
    market: Mapped[str] = mapped_column(String(24), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(24), nullable=False)
    penalty_score: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False, default=Decimal("0.0000"))
    reasons_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    source: Mapped[str] = mapped_column(String(80), nullable=False, default="vinance_guardrail_v1")
