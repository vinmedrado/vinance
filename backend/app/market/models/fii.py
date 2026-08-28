from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Index, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base


class FiiFundamental(Base):
    __tablename__ = "fii_fundamentals"
    __table_args__ = (
        UniqueConstraint("ticker", "date", "source", name="uq_fii_fundamentals_ticker_date_source"),
        Index("ix_fii_fundamentals_ticker", "ticker"),
        Index("ix_fii_fundamentals_date", "date"),
        Index("ix_fii_fundamentals_segmento", "segmento"),
        Index("ix_fii_fundamentals_source", "source"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    ticker: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    patrimonio_liq: Mapped[Decimal | None] = mapped_column(Numeric(24, 6), nullable=True)
    vpa: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    pvp: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    dy_12m: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    dy_3m_acumulado: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    ultimo_rendimento: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    data_ultimo_rend: Mapped[date | None] = mapped_column(Date, nullable=True)
    volume_medio_diario: Mapped[Decimal | None] = mapped_column(Numeric(24, 6), nullable=True)
    liquidez_diaria: Mapped[Decimal | None] = mapped_column(Numeric(24, 6), nullable=True)
    tipo: Mapped[str | None] = mapped_column(String(80), nullable=True)
    segmento: Mapped[str | None] = mapped_column(String(120), nullable=True)
    num_cotistas: Mapped[int | None] = mapped_column(Integer, nullable=True)
    num_imoveis: Mapped[int | None] = mapped_column(Integer, nullable=True)
    vacancia_fisica: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    vacancia_financeira: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    gestora: Mapped[str | None] = mapped_column(String(160), nullable=True)
    administradora: Mapped[str | None] = mapped_column(String(160), nullable=True)
    taxa_adm: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    taxa_performance: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    coletado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
