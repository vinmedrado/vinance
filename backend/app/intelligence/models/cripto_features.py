from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Index, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base


class CriptoMLFeature(Base):
    __tablename__ = "cripto_ml_features"
    __table_args__ = (
        UniqueConstraint("coin_id", "date", name="uq_cripto_ml_features_coin_id_date"),
        Index("ix_cripto_ml_features_coin_id_date", "coin_id", "date"),
        Index("ix_cripto_ml_features_ticker_date", "ticker", "date"),
        Index("ix_cripto_ml_features_score_final", "score_final"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    coin_id: Mapped[str] = mapped_column(String(120), nullable=False)
    ticker: Mapped[str] = mapped_column(String(32), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    volatilidade_7d: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    volatilidade_30d: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    correlacao_btc_30d: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    momentum_7d: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    momentum_30d: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    momentum_90d: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    volume_anomaly: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    fear_greed_score: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    score_final: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    calculado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
