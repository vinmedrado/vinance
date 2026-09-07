from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Date, DateTime, Index, Integer, JSON, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base


class AssetScore(Base):
    __tablename__ = "asset_scores"
    __table_args__ = (
        UniqueConstraint("ticker", "market", "date", "source", name="uq_asset_scores_ticker_market_date_source"),
        Index("ix_asset_scores_market_date_score", "market", "date", "score_total"),
        Index("ix_asset_scores_ticker_market", "ticker", "market"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticker: Mapped[str] = mapped_column(String(32), nullable=False)
    market: Mapped[str] = mapped_column(String(24), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    score_total: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    score_value: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    score_quality: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    score_dividend: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    score_liquidity: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    score_risk: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    source: Mapped[str] = mapped_column(String(80), nullable=False, default="vinance_score_v1")
