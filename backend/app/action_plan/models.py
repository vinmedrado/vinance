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


class ActionPlanDecision(Base):
    """Immutable presentation/orchestration decision for one exact A1 -> A5 chain."""

    __tablename__ = "action_plan_decisions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('BLOCKED','PARTIAL','READY','NO_ACTION_REQUIRED')",
            name="ck_action_plan_status",
        ),
        CheckConstraint("period = 'MONTHLY'", name="ck_action_plan_period"),
        CheckConstraint(
            "authorized_financial_capital >= 0 AND investment_budget >= 0 "
            "AND suggested_capital >= 0 AND total_financial_actions >= 0 "
            "AND total_investment_actions >= 0 AND total_hold_cash >= 0 "
            "AND speculative_capital >= 0",
            name="ck_action_plan_nonnegative",
        ),
        CheckConstraint(
            "total_financial_actions <= authorized_financial_capital",
            name="ck_action_plan_financial_conservation",
        ),
        CheckConstraint(
            "total_investment_actions <= suggested_capital",
            name="ck_action_plan_investment_conservation",
        ),
        CheckConstraint(
            "total_investment_actions + total_hold_cash <= investment_budget",
            name="ck_action_plan_budget_conservation",
        ),
        CheckConstraint(
            "speculative_capital = 0",
            name="ck_action_plan_no_speculation",
        ),
        ForeignKeyConstraint(
            [
                "investment_orchestration_decision_id",
                "capital_allocation_decision_id",
                "financial_policy_decision_id",
                "financial_state_snapshot_id",
                "household_id",
                "investment_budget",
                "suggested_capital",
                "remaining_investment_cash",
            ],
            [
                "investment_orchestration_decisions.id",
                "investment_orchestration_decisions.capital_allocation_decision_id",
                "investment_orchestration_decisions.financial_policy_decision_id",
                "investment_orchestration_decisions.financial_state_snapshot_id",
                "investment_orchestration_decisions.household_id",
                "investment_orchestration_decisions.investment_budget",
                "investment_orchestration_decisions.suggested_capital",
                "investment_orchestration_decisions.remaining_investment_cash",
            ],
            name="fk_action_plan_orchestration_chain",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "investment_orchestration_decision_id",
            "engine_version",
            "rules_version",
            name="uq_action_plan_orchestration_versions",
        ),
        Index(
            "ix_action_plan_household_generated",
            "household_id",
            "generated_at",
        ),
        Index(
            "uq_action_plan_idempotency",
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
    investment_orchestration_decision_id: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    created_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    engine_version: Mapped[str] = mapped_column(String(80), nullable=False)
    rules_version: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    period: Mapped[str] = mapped_column(String(16), nullable=False)
    authorized_financial_capital: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False
    )
    investment_budget: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    suggested_capital: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    remaining_investment_cash: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False
    )
    total_financial_actions: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False
    )
    total_investment_actions: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False
    )
    total_hold_cash: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    speculative_capital: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    state_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    allocation_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    orchestration_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    ruleset_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    decision_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    decision_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
