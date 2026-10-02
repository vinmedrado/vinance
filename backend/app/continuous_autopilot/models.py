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


class ContinuousAutopilotDecision(Base):
    """Immutable comparison of two exact Action Plan decisions."""

    __tablename__ = "continuous_autopilot_decisions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('UP_TO_DATE','REEVALUATION_REQUIRED','EVALUATING',"
            "'CHANGED','UNCHANGED','BLOCKED','FAILED')",
            name="ck_continuous_autopilot_decision_status",
        ),
        CheckConstraint(
            "materiality IN ('NONE','LOW','MEDIUM','HIGH','CRITICAL')",
            name="ck_continuous_autopilot_materiality",
        ),
        CheckConstraint(
            "alert_decision IN ('NO_ALERT','INFORMATIONAL','ACTION_RECOMMENDED',"
            "'IMPORTANT','CRITICAL')",
            name="ck_continuous_autopilot_alert_decision",
        ),
        CheckConstraint(
            "reevaluation_scope IN ('NONE','FULL_CHAIN','INVESTMENT_CHAIN')",
            name="ck_continuous_autopilot_scope",
        ),
        CheckConstraint(
            "change_count >= 0",
            name="ck_continuous_autopilot_change_count",
        ),
        ForeignKeyConstraint(
            ["previous_action_plan_id", "household_id"],
            ["action_plan_decisions.id", "action_plan_decisions.household_id"],
            name="fk_continuous_autopilot_previous_plan",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["current_action_plan_id", "household_id"],
            ["action_plan_decisions.id", "action_plan_decisions.household_id"],
            name="fk_continuous_autopilot_current_plan",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "household_id",
            "decision_fingerprint",
            name="uq_continuous_autopilot_household_fingerprint",
        ),
        UniqueConstraint(
            "id",
            "household_id",
            name="uq_continuous_autopilot_id_household",
        ),
        UniqueConstraint(
            "id",
            "household_id",
            "current_action_plan_id",
            name="uq_continuous_autopilot_id_household_plan",
        ),
        Index(
            "ix_continuous_autopilot_household_generated",
            "household_id",
            "generated_at",
        ),
        Index(
            "uq_continuous_autopilot_dedupe",
            "household_id",
            "dedupe_key",
            unique=True,
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    household_id: Mapped[int] = mapped_column(
        ForeignKey("households.id", ondelete="RESTRICT"), nullable=False
    )
    previous_action_plan_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    current_action_plan_id: Mapped[int] = mapped_column(Integer, nullable=False)
    created_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    engine_version: Mapped[str] = mapped_column(String(80), nullable=False)
    rules_version: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    materiality: Mapped[str] = mapped_column(String(16), nullable=False)
    alert_decision: Mapped[str] = mapped_column(String(32), nullable=False)
    reevaluation_scope: Mapped[str] = mapped_column(String(32), nullable=False)
    change_count: Mapped[int] = mapped_column(Integer, nullable=False)
    decision_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    previous_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    current_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    ruleset_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    decision_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    dedupe_key: Mapped[str] = mapped_column(String(64), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ContinuousAutopilotRequest(Base):
    """Immutable idempotency alias for an exact logical evaluation request."""

    __tablename__ = "continuous_autopilot_requests"
    __table_args__ = (
        ForeignKeyConstraint(
            ["continuous_decision_id", "household_id"],
            [
                "continuous_autopilot_decisions.id",
                "continuous_autopilot_decisions.household_id",
            ],
            name="fk_continuous_autopilot_request_decision",
            ondelete="RESTRICT",
        ),
        Index(
            "ix_continuous_autopilot_requests_decision",
            "continuous_decision_id",
            "household_id",
        ),
    )

    household_id: Mapped[int] = mapped_column(
        ForeignKey("households.id", ondelete="RESTRICT"), primary_key=True
    )
    idempotency_key: Mapped[str] = mapped_column(String(128), primary_key=True)
    continuous_decision_id: Mapped[int] = mapped_column(Integer, nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ContinuousAutopilotState(Base):
    """Mutable, per-household operational coordination state."""

    __tablename__ = "continuous_autopilot_states"
    __table_args__ = (
        CheckConstraint(
            "status IN ('UP_TO_DATE','REEVALUATION_REQUIRED','EVALUATING',"
            "'CHANGED','UNCHANGED','BLOCKED','FAILED')",
            name="ck_continuous_autopilot_state_status",
        ),
        CheckConstraint(
            "evaluation_count >= 0 AND change_count >= 0 AND alert_count >= 0 "
            "AND no_change_count >= 0 AND failure_count >= 0 "
            "AND alert_episode >= 0",
            name="ck_continuous_autopilot_state_counters",
        ),
        CheckConstraint(
            "(last_action_plan_id IS NULL) = "
            "(last_continuous_decision_id IS NULL)",
            name="ck_continuous_autopilot_state_pointer_pair",
        ),
        ForeignKeyConstraint(
            [
                "last_continuous_decision_id",
                "household_id",
                "last_action_plan_id",
            ],
            [
                "continuous_autopilot_decisions.id",
                "continuous_autopilot_decisions.household_id",
                "continuous_autopilot_decisions.current_action_plan_id",
            ],
            name="fk_continuous_autopilot_state_chain",
            ondelete="RESTRICT",
        ),
        Index(
            "ix_continuous_autopilot_states_status_dirty",
            "status",
            "dirty_since",
        ),
        Index(
            "ix_continuous_autopilot_states_last_evaluated",
            "last_evaluated_at",
        ),
    )

    household_id: Mapped[int] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), primary_key=True
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="REEVALUATION_REQUIRED"
    )
    pending_categories: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    last_action_plan_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_continuous_decision_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    dirty_since: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_evaluated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_successful_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    active_alert_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    alert_episode: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    evaluation_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    change_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    alert_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    no_change_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    failure_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
