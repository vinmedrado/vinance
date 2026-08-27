from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base
from backend.app.investment_alerts.rules import (
    ALERT_RULE_VERSION,
    DEFAULT_COOLDOWN_MINUTES,
    DEFAULT_MINIMUM_CONFIDENCE_DELTA,
    DEFAULT_MINIMUM_SCORE_DELTA,
    DELIVERY_CHANNEL_IN_APP,
)


class InvestmentAlertSubscription(Base):
    __tablename__ = "investment_alert_subscriptions"
    __table_args__ = (
        UniqueConstraint("user_id", "asset", name="uq_alert_subscriptions_user_asset"),
        CheckConstraint(
            "minimum_score_delta >= 1 AND minimum_score_delta <= 100",
            name="ck_alert_subscriptions_score_delta",
        ),
        CheckConstraint(
            "minimum_confidence_delta >= 1 AND minimum_confidence_delta <= 100",
            name="ck_alert_subscriptions_confidence_delta",
        ),
        CheckConstraint(
            "cooldown_minutes >= 30 AND cooldown_minutes <= 10080",
            name="ck_alert_subscriptions_cooldown",
        ),
        Index("ix_alert_subscriptions_user_enabled", "user_id", "enabled"),
        Index("ix_alert_subscriptions_enabled_updated", "enabled", "updated_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    asset: Mapped[str] = mapped_column(String(32), nullable=False)
    market: Mapped[str] = mapped_column(String(24), nullable=False)
    budget: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    investor_profile: Mapped[str] = mapped_column(String(32), nullable=False)
    include_warnings: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    trend_filter: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source_decision_id: Mapped[str] = mapped_column(
        ForeignKey("investment_decision_audits.decision_id", ondelete="RESTRICT"), nullable=False
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    alert_on_action_change: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    alert_on_score_change: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    alert_on_confidence_change: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    alert_on_risk_change: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    alert_on_new_opportunity: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    minimum_score_delta: Mapped[Decimal] = mapped_column(
        Numeric(8, 4), nullable=False, default=DEFAULT_MINIMUM_SCORE_DELTA
    )
    minimum_confidence_delta: Mapped[Decimal] = mapped_column(
        Numeric(8, 4), nullable=False, default=DEFAULT_MINIMUM_CONFIDENCE_DELTA
    )
    cooldown_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=DEFAULT_COOLDOWN_MINUTES)
    rule_version: Mapped[str] = mapped_column(String(80), nullable=False, default=ALERT_RULE_VERSION)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class InvestmentAlertState(Base):
    __tablename__ = "investment_alert_states"
    __table_args__ = (
        UniqueConstraint("subscription_id", name="uq_alert_states_subscription"),
        UniqueConstraint("user_id", "asset", name="uq_alert_states_user_asset"),
        Index("ix_alert_states_user_checked", "user_id", "last_checked_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subscription_id: Mapped[int] = mapped_column(
        ForeignKey("investment_alert_subscriptions.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    asset: Mapped[str] = mapped_column(String(32), nullable=False)
    last_decision_id: Mapped[str | None] = mapped_column(
        ForeignKey("investment_decision_audits.decision_id", ondelete="RESTRICT"), nullable=True
    )
    last_action: Mapped[str | None] = mapped_column(String(24), nullable=True)
    last_score: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    last_confidence: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    last_risk_level: Mapped[str | None] = mapped_column(String(24), nullable=True)
    last_trend: Mapped[str | None] = mapped_column(String(32), nullable=True)
    last_evaluation_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    evaluations_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    alerts_generated_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cooldown_suppressed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duplicates_prevented_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    volume_suppressed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    errors_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class InvestmentAlert(Base):
    __tablename__ = "investment_alerts"
    __table_args__ = (
        UniqueConstraint("alert_id", name="uq_investment_alerts_alert_id"),
        UniqueConstraint("deduplication_key", name="uq_investment_alerts_deduplication_key"),
        CheckConstraint(
            "alert_type IN ('NEW_OPPORTUNITY','ACTION_CHANGE','SCORE_CHANGE','CONFIDENCE_CHANGE','RISK_CHANGE')",
            name="ck_investment_alerts_type",
        ),
        CheckConstraint(
            "severity IN ('INFO','MEDIUM','HIGH')",
            name="ck_investment_alerts_severity",
        ),
        CheckConstraint("delivery_channel = 'IN_APP'", name="ck_investment_alerts_channel"),
        Index("ix_investment_alerts_user_created", "user_id", "created_at"),
        Index("ix_investment_alerts_user_read_created", "user_id", "read_at", "created_at"),
        Index("ix_investment_alerts_user_asset", "user_id", "asset", "created_at"),
        Index("ix_investment_alerts_user_type", "user_id", "alert_type", "created_at"),
        Index("ix_investment_alerts_user_severity", "user_id", "severity", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    alert_id: Mapped[str] = mapped_column(String(36), nullable=False)
    deduplication_key: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    subscription_id: Mapped[int | None] = mapped_column(
        ForeignKey("investment_alert_subscriptions.id", ondelete="SET NULL"), nullable=True
    )
    decision_id: Mapped[str] = mapped_column(
        ForeignKey("investment_decision_audits.decision_id", ondelete="RESTRICT"), nullable=False
    )
    asset: Mapped[str] = mapped_column(String(32), nullable=False)
    alert_type: Mapped[str] = mapped_column(String(32), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    delivery_channel: Mapped[str] = mapped_column(
        String(16), nullable=False, default=DELIVERY_CHANNEL_IN_APP
    )
    previous_state: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    current_state: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    rule_version: Mapped[str] = mapped_column(String(80), nullable=False, default=ALERT_RULE_VERSION)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
