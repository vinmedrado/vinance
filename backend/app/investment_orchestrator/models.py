from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base


class InvestmentOrchestrationDecision(Base):
    """Immutable investment decision bound to one exact Autopilot 1 -> 4 chain."""

    __tablename__ = "investment_orchestration_decisions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('BLOCKED','LIMITED','ACTIVE','NO_SUITABLE_OPPORTUNITY')",
            name="ck_investment_orchestration_status",
        ),
        CheckConstraint(
            "investment_budget >= 0 AND suggested_capital >= 0 "
            "AND remaining_investment_cash >= 0 AND speculative_capital >= 0",
            name="ck_investment_orchestration_nonnegative",
        ),
        CheckConstraint(
            "suggested_capital <= investment_budget "
            "AND suggested_capital + remaining_investment_cash = investment_budget",
            name="ck_investment_orchestration_conservation",
        ),
        CheckConstraint(
            "speculative_capital = 0",
            name="ck_investment_orchestration_no_speculation",
        ),
        ForeignKeyConstraint(
            [
                "capital_allocation_decision_id",
                "financial_policy_decision_id",
                "financial_state_snapshot_id",
                "household_id",
                "investment_budget",
            ],
            [
                "capital_allocation_decisions.id",
                "capital_allocation_decisions.financial_policy_decision_id",
                "capital_allocation_decisions.financial_state_snapshot_id",
                "capital_allocation_decisions.household_id",
                "capital_allocation_decisions.investment_bucket_amount",
            ],
            name="fk_investment_orchestration_allocation_chain",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "capital_allocation_decision_id",
            "engine_version",
            "rules_version",
            name="uq_investment_orchestration_allocation_versions",
        ),
        Index(
            "ix_investment_orchestration_household_generated",
            "household_id",
            "generated_at",
        ),
        Index(
            "uq_investment_orchestration_idempotency",
            "household_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    household_id: Mapped[int] = mapped_column(
        ForeignKey("households.id", ondelete="RESTRICT"), nullable=False
    )
    financial_state_snapshot_id: Mapped[int] = mapped_column(Integer, nullable=False)
    financial_policy_decision_id: Mapped[int] = mapped_column(Integer, nullable=False)
    capital_allocation_decision_id: Mapped[int] = mapped_column(Integer, nullable=False)
    created_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    engine_version: Mapped[str] = mapped_column(String(80), nullable=False)
    rules_version: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    investment_budget: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    suggested_capital: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    remaining_investment_cash: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False
    )
    speculative_capital: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    state_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    allocation_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    market_context_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    ruleset_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    decision_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    decision_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
