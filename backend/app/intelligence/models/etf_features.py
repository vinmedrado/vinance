from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Index, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base
from backend.app.intelligence.models._base_features import TickerFeatureMixin


class EtfMLFeature(TickerFeatureMixin, Base):
    __tablename__ = "etf_ml_features"
    __table_args__ = (
        UniqueConstraint("ticker", "date", name="uq_etf_ml_features_ticker_date"),
        Index("ix_etf_ml_features_ticker_date", "ticker", "date"),
        Index("ix_etf_ml_features_score_final", "score_final"),
    )

    taxa_adm_rank: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    tracking_score: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    momentum_30d: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    momentum_90d: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    volatilidade_30d: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    retorno_vs_benchmark: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
