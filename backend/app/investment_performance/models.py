from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, JSON, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base


class InvestmentDecisionPerformance(Base):
    __tablename__ = "investment_decision_performance"
    __table_args__ = (
        UniqueConstraint(
            "decision_id",
            "horizon",
            name="uq_decision_performance_decision_horizon",
        ),
        Index(
            "ix_decision_performance_horizon_evaluated",
            "horizon",
            "evaluated_at",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    decision_id: Mapped[str] = mapped_column(
        ForeignKey(
            "investment_decision_audits.decision_id",
            name="fk_decision_performance_decision_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    horizon: Mapped[str] = mapped_column(String(8), nullable=False)
    reference_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    reference_price_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    price_source: Mapped[str] = mapped_column(String(80), nullable=False)
    evaluation_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    evaluation_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    evaluation_price_source: Mapped[str] = mapped_column(String(80), nullable=False)
    absolute_change: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    return_pct: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    max_favorable_excursion_pct: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 6), nullable=True
    )
    max_adverse_excursion_pct: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 6), nullable=True
    )
    result_status: Mapped[str] = mapped_column(
        String(24), nullable=False, default="EVALUATED", server_default="EVALUATED"
    )
    result_classification: Mapped[str] = mapped_column(String(32), nullable=False)
    result_context: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    evaluation_policy_version: Mapped[str] = mapped_column(String(80), nullable=False)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
