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
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base


class PlatformBootstrapState(Base):
    __tablename__ = "platform_bootstrap_state"
    __table_args__ = (
        CheckConstraint("id = 1", name="ck_platform_bootstrap_state_singleton"),
        CheckConstraint(
            "completed_at IS NOT NULL OR completed_by_user_id IS NULL",
            name="ck_platform_bootstrap_state_completion",
        ),
    )

    id: Mapped[int] = mapped_column(
        SmallInteger, primary_key=True, autoincrement=False, default=1
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class PlatformAdmin(Base):
    __tablename__ = "platform_admins"
    __table_args__ = (
        CheckConstraint("status IN ('ACTIVE','REVOKED')", name="ck_platform_admins_status"),
        CheckConstraint(
            "(status = 'ACTIVE' AND revoked_at IS NULL) OR "
            "(status = 'REVOKED' AND revoked_at IS NOT NULL)",
            name="ck_platform_admins_revocation",
        ),
        Index(
            "ix_platform_admins_active",
            "user_id",
            unique=True,
            postgresql_where=text("status = 'ACTIVE'"),
        ),
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ACTIVE")
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PlatformAccessInvitation(Base):
    __tablename__ = "platform_access_invitations"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING','ACCEPTED','CANCELLED','EXPIRED')",
            name="ck_platform_access_invitations_status",
        ),
        CheckConstraint(
            "delivery_status IN ('MANUAL_LINK','EMAIL_PENDING','EMAIL_SENT','EMAIL_FAILED')",
            name="ck_platform_access_invitations_delivery",
        ),
        CheckConstraint(
            "cloudflare_access_status IN "
            "('PENDING_AUTHORIZATION','AUTHORIZED','NOT_REQUIRED','FAILED')",
            name="ck_platform_access_invitations_cloudflare",
        ),
        CheckConstraint(
            "email_normalized = lower(btrim(email_normalized))",
            name="ck_platform_access_invitations_email_normalized",
        ),
        CheckConstraint("length(token_hash) = 64", name="ck_platform_access_invitations_token_hash"),
        CheckConstraint("resend_count >= 0", name="ck_platform_access_invitations_resend_count"),
        UniqueConstraint(
            "token_hash",
            name="uq_platform_access_invitations_token_hash",
        ),
        Index(
            "uq_platform_access_invitations_pending_email",
            "email_normalized",
            unique=True,
            postgresql_where=text("status = 'PENDING'"),
        ),
        Index("ix_platform_access_invitations_email_status", "email_normalized", "status"),
        Index("ix_platform_access_invitations_status_expiry", "status", "expires_at"),
        Index("ix_platform_access_invitations_actor_created", "invited_by_user_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    email_normalized: Mapped[str] = mapped_column(String(255), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="PENDING")
    delivery_status: Mapped[str] = mapped_column(String(32), nullable=False, default="MANUAL_LINK")
    cloudflare_access_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="PENDING_AUTHORIZATION"
    )
    invited_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    accepted_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_resent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resend_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"
    __table_args__ = (
        CheckConstraint("length(token_hash) = 64", name="ck_password_reset_tokens_hash"),
        CheckConstraint(
            "NOT (used_at IS NOT NULL AND revoked_at IS NOT NULL)",
            name="ck_password_reset_tokens_terminal_state",
        ),
        UniqueConstraint("token_hash", name="uq_password_reset_tokens_token_hash"),
        Index("ix_password_reset_tokens_user_expiry", "user_id", "expires_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    requested_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    request_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class PlatformAccessAuditEvent(Base):
    __tablename__ = "platform_access_audit_events"
    __table_args__ = (
        Index("ix_platform_access_audit_actor_created", "actor_user_id", "created_at"),
        Index("ix_platform_access_audit_subject_created", "subject_user_id", "created_at"),
        Index("ix_platform_access_audit_type_created", "event_type", "created_at"),
        Index("ix_platform_access_audit_correlation", "correlation_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    actor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    subject_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    invitation_id: Mapped[str | None] = mapped_column(
        ForeignKey("platform_access_invitations.id", ondelete="SET NULL"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    correlation_id: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
