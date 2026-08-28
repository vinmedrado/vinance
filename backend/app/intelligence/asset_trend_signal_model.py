from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Date, DateTime, Index, Integer, JSON, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base


class AssetTrendSignal(Base):
    __tablename__ = "asset_trend_signals"
    __table_args__ = (
        UniqueConstraint("ticker", "market", "date", "source", name="uq_asset_trend_signals_ticker_market_date_source"),
        Index("ix_asset_trend_signals_market_trend_date", "market", "trend_label", "date"),
        Index("ix_asset_trend_signals_market_risk_date", "market", "risk_label", "date"),
        Index("ix_asset_trend_signals_ticker_market", "ticker", "market"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    ticker: Mapped[str] = mapped_column(String(32), nullable=False)
    market: Mapped[str] = mapped_column(String(24), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    return_1d: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    return_7d: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    return_30d: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    return_90d: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    return_180d: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    return_365d: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    volatility_30d: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    momentum_score: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    trend_label: Mapped[str] = mapped_column(String(32), nullable=False)
    risk_label: Mapped[str] = mapped_column(String(32), nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    source: Mapped[str] = mapped_column(String(80), nullable=False, default="vinance_trend_v1")
