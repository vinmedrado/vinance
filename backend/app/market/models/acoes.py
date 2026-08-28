from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Index, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base


class AcaoFundamental(Base):
    __tablename__ = "acoes_fundamentals"
    __table_args__ = (
        UniqueConstraint("ticker", "date", "source", name="uq_acoes_fundamentals_ticker_date_source"),
        Index("ix_acoes_fundamentals_ticker", "ticker"),
        Index("ix_acoes_fundamentals_date", "date"),
        Index("ix_acoes_fundamentals_setor", "setor"),
        Index("ix_acoes_fundamentals_source", "source"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    ticker: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    market_cap: Mapped[Decimal | None] = mapped_column(Numeric(24, 6), nullable=True)
    pl: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    pvp: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    psr: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    ev_ebitda: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    ev_ebit: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    roe: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    roa: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    roic: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    margem_liquida: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    margem_ebitda: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    cagr_receita_5a: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    cagr_lucro_5a: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    dy_12m: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    payout: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    divida_liq_ebitda: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    volume_medio_diario: Mapped[Decimal | None] = mapped_column(Numeric(24, 6), nullable=True)
    setor: Mapped[str | None] = mapped_column(String(120), nullable=True)
    subsetor: Mapped[str | None] = mapped_column(String(120), nullable=True)
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    coletado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
