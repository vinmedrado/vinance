from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Index, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base


class CriptoFundamental(Base):
    __tablename__ = "cripto_fundamentals"
    __table_args__ = (
        Index("ix_cripto_fundamentals_coin_id", "coin_id"),
        Index("ix_cripto_fundamentals_ticker", "ticker"),
        Index("ix_cripto_fundamentals_date", "date"),
        Index("ix_cripto_fundamentals_source", "source"),
        Index("ix_cripto_fundamentals_coletado_em", "coletado_em"),
        Index("ix_cripto_fundamentals_coin_id_coletado_em", "coin_id", "coletado_em", "source"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    coin_id: Mapped[str] = mapped_column(String(120), nullable=False)
    ticker: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    price_brl: Mapped[Decimal | None] = mapped_column(Numeric(24, 8), nullable=True)
    price_usd: Mapped[Decimal | None] = mapped_column(Numeric(24, 8), nullable=True)
    market_cap_usd: Mapped[Decimal | None] = mapped_column(Numeric(30, 6), nullable=True)
    market_cap_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    volume_24h_usd: Mapped[Decimal | None] = mapped_column(Numeric(30, 6), nullable=True)
    price_change_1h_pct: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    price_change_24h_pct: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    price_change_7d_pct: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    price_change_30d_pct: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    price_change_90d_pct: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    price_change_1y_pct: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    btc_dominance: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    circulating_supply: Mapped[Decimal | None] = mapped_column(Numeric(30, 6), nullable=True)
    max_supply: Mapped[Decimal | None] = mapped_column(Numeric(30, 6), nullable=True)
    ath_price_usd: Mapped[Decimal | None] = mapped_column(Numeric(24, 8), nullable=True)
    ath_change_pct: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    coletado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
