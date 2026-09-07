from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Index, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base


class InvestmentRecommendation(Base):
    __tablename__ = "investment_recommendations"
    __table_args__ = (
        Index(
            "ix_investment_recommendations_budget_market_generated_at",
            "budget",
            "market",
            "generated_at",
        ),
        Index("ix_investment_recommendations_market_rank", "market", "recommendation_rank"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    budget: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    market: Mapped[str] = mapped_column(String(24), nullable=False)
    ticker: Mapped[str] = mapped_column(String(32), nullable=False)
    score_total: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    quantity_possible: Mapped[int] = mapped_column(Integer, nullable=False)
    invested_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    recommendation_rank: Mapped[int] = mapped_column(Integer, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
