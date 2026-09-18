from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    JSON,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base


class FinancialPolicyDecision(Base):
    """An immutable policy decision bound to one exact Financial State snapshot."""

    __tablename__ = "financial_policy_decisions"
    __table_args__ = (
        UniqueConstraint(
            "id",
            "financial_state_snapshot_id",
            "household_id",
            name="uq_financial_policy_decisions_chain",
        ),
        CheckConstraint(
            "policy_state IN ('DATA_BLOCKED','CASHFLOW_RECOVERY','DEBT_PRIORITY',"
            "'EMERGENCY_RESERVE_PRIORITY','GOAL_PRIORITY','BALANCED_BUILD',"
            "'INVESTMENT_READY')",
            name="ck_financial_policy_decisions_state",
        ),
        CheckConstraint(
            "investment_readiness IN ('BLOCKED','LIMITED','READY')",
            name="ck_financial_policy_decisions_readiness",
        ),
        ForeignKeyConstraint(
            ["financial_state_snapshot_id", "household_id"],
            ["financial_state_snapshots.id", "financial_state_snapshots.household_id"],
            name="fk_policy_decision_snapshot_household",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "financial_state_snapshot_id",
            "engine_version",
            "rules_version",
            name="uq_policy_decision_snapshot_versions",
        ),
        Index(
            "ix_financial_policy_decisions_household_generated",
            "household_id",
            "generated_at",
        ),
        Index(
            "uq_financial_policy_decisions_idempotency",
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
    created_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    engine_version: Mapped[str] = mapped_column(String(80), nullable=False)
    rules_version: Mapped[str] = mapped_column(String(80), nullable=False)
    policy_state: Mapped[str] = mapped_column(String(40), nullable=False)
    investment_readiness: Mapped[str] = mapped_column(String(16), nullable=False)
    input_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    ruleset_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    decision_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    decision_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
