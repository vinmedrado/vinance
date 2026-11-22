from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base


class UserNotificationPreference(Base):
    __tablename__ = "user_notification_preferences"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    push_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    account_events_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    household_invites_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    financial_alerts_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    analysis_updates_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class WebPushSubscription(Base):
    __tablename__ = "web_push_subscriptions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('ACTIVE','EXPIRED','REVOKED')",
            name="ck_web_push_subscriptions_status",
        ),
        CheckConstraint("length(endpoint_hash) = 64", name="ck_web_push_subscriptions_endpoint_hash"),
        CheckConstraint(
            "encryption_key_version > 0",
            name="ck_web_push_subscriptions_encryption_version",
        ),
        CheckConstraint(
            "(status = 'ACTIVE' AND revoked_at IS NULL) OR "
            "(status IN ('EXPIRED','REVOKED') AND revoked_at IS NOT NULL)",
            name="ck_web_push_subscriptions_revocation",
        ),
        Index(
            "uq_web_push_subscriptions_active_endpoint",
            "endpoint_hash",
            unique=True,
            postgresql_where=text("status = 'ACTIVE'"),
        ),
        Index(
            "uq_web_push_subscriptions_active_installation",
            "installation_id",
            unique=True,
            postgresql_where=text("status = 'ACTIVE'"),
        ),
        Index("ix_web_push_subscriptions_user_status", "user_id", "status", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    installation_id: Mapped[str] = mapped_column(String(64), nullable=False)
    endpoint_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    subscription_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    encryption_key_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ACTIVE")
    user_agent_family: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class WebPushDelivery(Base):
    __tablename__ = "web_push_deliveries"
    __table_args__ = (
        UniqueConstraint(
            "subscription_id",
            "dedupe_key",
            name="uq_web_push_deliveries_subscription_dedupe",
        ),
        CheckConstraint(
            "status IN ('PENDING','SENT','FAILED','EXPIRED','SUPPRESSED')",
            name="ck_web_push_deliveries_status",
        ),
        CheckConstraint("attempt_count >= 0", name="ck_web_push_deliveries_attempts"),
        Index("ix_web_push_deliveries_status_retry", "status", "next_attempt_at"),
        Index("ix_web_push_deliveries_user_created", "user_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    subscription_id: Mapped[str | None] = mapped_column(
        ForeignKey("web_push_subscriptions.id", ondelete="SET NULL"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(String(48), nullable=False)
    dedupe_key: Mapped[str] = mapped_column(String(64), nullable=False)
    route: Mapped[str] = mapped_column(String(255), nullable=False)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="PENDING")
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
