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


class CapitalAllocationDecision(Base):
    """Immutable amounts bound to one exact State -> Policy decision chain."""

    __tablename__ = "capital_allocation_decisions"
    __table_args__ = (
        CheckConstraint(
            "allocation_period IN ('MONTHLY')",
            name="ck_capital_allocation_decisions_period",
        ),
        CheckConstraint(
            "allocation_status IN ('BLOCKED','CONSTRAINED','ACTIVE','SURPLUS')",
            name="ck_capital_allocation_decisions_status",
        ),
        CheckConstraint(
            "allocatable_capital IS NULL OR allocatable_capital >= 0",
            name="ck_capital_allocation_decisions_allocatable",
        ),
        CheckConstraint(
            "allocated_capital >= 0 AND investment_bucket_amount >= 0",
            name="ck_capital_allocation_decisions_nonnegative",
        ),
        CheckConstraint(
            "investment_bucket_amount <= allocated_capital",
            name="ck_capital_allocation_decisions_investment_bound",
        ),
        CheckConstraint(
            "((allocatable_capital IS NULL AND allocated_capital = 0 AND remaining_capital IS NULL) "
            "OR (allocatable_capital IS NOT NULL AND remaining_capital IS NOT NULL "
            "AND remaining_capital >= 0 AND allocated_capital <= allocatable_capital "
            "AND allocated_capital + remaining_capital = allocatable_capital))",
            name="ck_capital_allocation_decisions_conservation",
        ),
        ForeignKeyConstraint(
            [
                "financial_policy_decision_id",
                "financial_state_snapshot_id",
                "household_id",
            ],
            [
                "financial_policy_decisions.id",
                "financial_policy_decisions.financial_state_snapshot_id",
                "financial_policy_decisions.household_id",
            ],
            name="fk_capital_allocation_policy_state_household",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "financial_policy_decision_id",
            "engine_version",
            "rules_version",
            name="uq_capital_allocation_policy_versions",
        ),
        Index(
            "ix_capital_allocation_household_generated",
            "household_id",
            "generated_at",
        ),
        Index(
            "uq_capital_allocation_idempotency",
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
    created_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    engine_version: Mapped[str] = mapped_column(String(80), nullable=False)
    rules_version: Mapped[str] = mapped_column(String(80), nullable=False)
    allocation_period: Mapped[str] = mapped_column(String(16), nullable=False)
    allocation_status: Mapped[str] = mapped_column(String(16), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    allocatable_capital: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 2), nullable=True
    )
    allocated_capital: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    remaining_capital: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    investment_bucket_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False
    )
    input_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    ruleset_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    decision_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    decision_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
