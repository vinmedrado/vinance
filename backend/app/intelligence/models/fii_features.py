from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Index, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base
from backend.app.intelligence.models._base_features import TickerFeatureMixin


class FiiMLFeature(TickerFeatureMixin, Base):
    __tablename__ = "fii_ml_features"
    __table_args__ = (
        UniqueConstraint("ticker", "date", name="uq_fii_ml_features_ticker_date"),
        Index("ix_fii_ml_features_ticker_date", "ticker", "date"),
        Index("ix_fii_ml_features_score_final", "score_final"),
    )

    dy_trend_3m: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    pvp_zscore: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    vacancia_delta: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    momentum_30d: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    momentum_90d: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    volatilidade_30d: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    retorno_vs_ifix: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
