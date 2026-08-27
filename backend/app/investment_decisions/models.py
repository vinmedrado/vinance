from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base


class InvestmentDecisionAudit(Base):
    __tablename__ = "investment_decision_audits"
    __table_args__ = (
        UniqueConstraint("decision_id", name="uq_investment_decision_audits_decision_id"),
        Index("ix_decision_audits_user_created", "user_id", "created_at"),
        Index("ix_decision_audits_user_action", "user_id", "recommendation", "created_at"),
        Index("ix_decision_audits_user_risk", "user_id", "risk_level", "created_at"),
        Index("ix_decision_audits_user_asset", "user_id", "asset", "created_at"),
        Index("ix_decision_audits_correlation", "correlation_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    decision_id: Mapped[str] = mapped_column(String(36), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    asset: Mapped[str | None] = mapped_column(String(32), nullable=True)
    market: Mapped[str | None] = mapped_column(String(24), nullable=True)
    budget: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    investor_profile: Mapped[str | None] = mapped_column(String(32), nullable=True)
    recommendation: Mapped[str] = mapped_column(String(24), nullable=False)
    quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    invested_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    remaining_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    risk_level: Mapped[str | None] = mapped_column(String(24), nullable=True)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    trend: Mapped[str | None] = mapped_column(String(32), nullable=True)
    ranking: Mapped[int | None] = mapped_column(Integer, nullable=True)
    recommendation_score: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    guardrail_status: Mapped[str | None] = mapped_column(String(24), nullable=True)

    guardrail_reasons: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    explanation: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    request_parameters: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    input_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    score_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    response_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    snapshot_schema_version: Mapped[str] = mapped_column(String(80), nullable=False)
    rule_version: Mapped[str] = mapped_column(String(80), nullable=False)
    recommendation_engine_version: Mapped[str] = mapped_column(String(80), nullable=False)
    score_version: Mapped[str | None] = mapped_column(String(80), nullable=True)
    guardrail_version: Mapped[str | None] = mapped_column(String(80), nullable=True)
    trend_version: Mapped[str | None] = mapped_column(String(80), nullable=True)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fallback_used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
