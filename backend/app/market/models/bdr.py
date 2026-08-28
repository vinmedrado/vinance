from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Index, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base


class BdrFundamental(Base):
    __tablename__ = "bdr_fundamentals"
    __table_args__ = (
        UniqueConstraint("ticker", "date", "source", name="uq_bdr_fundamentals_ticker_date_source"),
        Index("ix_bdr_fundamentals_ticker", "ticker"),
        Index("ix_bdr_fundamentals_date", "date"),
        Index("ix_bdr_fundamentals_ticker_original", "ticker_original"),
        Index("ix_bdr_fundamentals_source", "source"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    ticker: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    market_cap: Mapped[Decimal | None] = mapped_column(Numeric(24, 6), nullable=True)
    empresa_subjacente: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ticker_original: Mapped[str | None] = mapped_column(String(32), nullable=True)
    bolsa_origem: Mapped[str | None] = mapped_column(String(80), nullable=True)
    pais_origem: Mapped[str | None] = mapped_column(String(80), nullable=True)
    moeda_origem: Mapped[str | None] = mapped_column(String(16), nullable=True)
    cotacao_cambio: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    pl: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    pvp: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    dy_12m: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    volume_medio_diario_brl: Mapped[Decimal | None] = mapped_column(Numeric(24, 6), nullable=True)
    nivel_bdr: Mapped[str | None] = mapped_column(String(80), nullable=True)
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    coletado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
