"""add invite-only platform access, PWA notification preferences, and Web Push

Revision ID: 0029_access_pwa_push_v1
Revises: 0028_financial_record_transfers
Create Date: 2026-11-20
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0029_access_pwa_push_v1"
down_revision = "0028_financial_record_transfers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "platform_bootstrap_state",
        sa.Column("id", sa.SmallInteger(), autoincrement=False, nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("id = 1", name="ck_platform_bootstrap_state_singleton"),
        sa.CheckConstraint(
            "completed_at IS NOT NULL OR completed_by_user_id IS NULL",
            name="ck_platform_bootstrap_state_completion",
        ),
        sa.ForeignKeyConstraint(["completed_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "platform_admins",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="ACTIVE", nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('ACTIVE','REVOKED')", name="ck_platform_admins_status"),
        sa.CheckConstraint(
            "(status = 'ACTIVE' AND revoked_at IS NULL) OR "
            "(status = 'REVOKED' AND revoked_at IS NOT NULL)",
            name="ck_platform_admins_revocation",
        ),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.create_index(
        "ix_platform_admins_active",
        "platform_admins",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("status = 'ACTIVE'"),
    )
    op.create_table(
        "platform_access_invitations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("email_normalized", sa.String(length=255), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="PENDING", nullable=False),
        sa.Column("delivery_status", sa.String(length=32), server_default="MANUAL_LINK", nullable=False),
        sa.Column(
            "cloudflare_access_status",
            sa.String(length=32),
            server_default="PENDING_AUTHORIZATION",
            nullable=False,
        ),
        sa.Column("invited_by_user_id", sa.Integer(), nullable=False),
        sa.Column("accepted_by_user_id", sa.Integer(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_resent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resend_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "cloudflare_access_status IN ('PENDING_AUTHORIZATION','AUTHORIZED','NOT_REQUIRED','FAILED')",
            name="ck_platform_access_invitations_cloudflare",
        ),
        sa.CheckConstraint(
            "delivery_status IN ('MANUAL_LINK','EMAIL_PENDING','EMAIL_SENT','EMAIL_FAILED')",
            name="ck_platform_access_invitations_delivery",
        ),
        sa.CheckConstraint(
            "email_normalized = lower(btrim(email_normalized))",
            name="ck_platform_access_invitations_email_normalized",
        ),
        sa.CheckConstraint("resend_count >= 0", name="ck_platform_access_invitations_resend_count"),
        sa.CheckConstraint(
            "status IN ('PENDING','ACCEPTED','CANCELLED','EXPIRED')",
            name="ck_platform_access_invitations_status",
        ),
        sa.CheckConstraint("length(token_hash) = 64", name="ck_platform_access_invitations_token_hash"),
        sa.ForeignKeyConstraint(["accepted_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["invited_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_platform_access_invitations_token_hash"),
    )
    op.create_index(
        "uq_platform_access_invitations_pending_email",
        "platform_access_invitations",
        ["email_normalized"],
        unique=True,
        postgresql_where=sa.text("status = 'PENDING'"),
    )
    op.create_index(
        "ix_platform_access_invitations_email_status",
        "platform_access_invitations",
        ["email_normalized", "status"],
    )
    op.create_index(
        "ix_platform_access_invitations_status_expiry",
        "platform_access_invitations",
        ["status", "expires_at"],
    )
    op.create_index(
        "ix_platform_access_invitations_actor_created",
        "platform_access_invitations",
        ["invited_by_user_id", "created_at"],
    )
    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("requested_by_user_id", sa.Integer(), nullable=True),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("length(token_hash) = 64", name="ck_password_reset_tokens_hash"),
        sa.CheckConstraint(
            "NOT (used_at IS NOT NULL AND revoked_at IS NOT NULL)",
            name="ck_password_reset_tokens_terminal_state",
        ),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_password_reset_tokens_token_hash"),
    )
    op.create_index("ix_password_reset_tokens_user_id", "password_reset_tokens", ["user_id"])
    op.create_index(
        "ix_password_reset_tokens_user_expiry",
        "password_reset_tokens",
        ["user_id", "expires_at"],
    )
    op.create_table(
        "platform_access_audit_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("subject_user_id", sa.Integer(), nullable=True),
        sa.Column("invitation_id", sa.String(length=36), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("correlation_id", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["invitation_id"], ["platform_access_invitations.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["subject_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_platform_access_audit_actor_created",
        "platform_access_audit_events",
        ["actor_user_id", "created_at"],
    )
    op.create_index(
        "ix_platform_access_audit_subject_created",
        "platform_access_audit_events",
        ["subject_user_id", "created_at"],
    )
    op.create_index(
        "ix_platform_access_audit_type_created",
        "platform_access_audit_events",
        ["event_type", "created_at"],
    )
    op.create_index(
        "ix_platform_access_audit_correlation",
        "platform_access_audit_events",
        ["correlation_id"],
    )
    op.create_table(
        "user_notification_preferences",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("push_enabled", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("account_events_enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("household_invites_enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("financial_alerts_enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("analysis_updates_enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.create_table(
        "web_push_subscriptions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("installation_id", sa.String(length=64), nullable=False),
        sa.Column("endpoint_hash", sa.String(length=64), nullable=False),
        sa.Column("subscription_encrypted", sa.Text(), nullable=False),
        sa.Column("encryption_key_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("status", sa.String(length=16), server_default="ACTIVE", nullable=False),
        sa.Column("user_agent_family", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("encryption_key_version > 0", name="ck_web_push_subscriptions_encryption_version"),
        sa.CheckConstraint("length(endpoint_hash) = 64", name="ck_web_push_subscriptions_endpoint_hash"),
        sa.CheckConstraint(
            "(status = 'ACTIVE' AND revoked_at IS NULL) OR "
            "(status IN ('EXPIRED','REVOKED') AND revoked_at IS NOT NULL)",
            name="ck_web_push_subscriptions_revocation",
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE','EXPIRED','REVOKED')",
            name="ck_web_push_subscriptions_status",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_web_push_subscriptions_user_id", "web_push_subscriptions", ["user_id"])
    op.create_index(
        "ix_web_push_subscriptions_user_status",
        "web_push_subscriptions",
        ["user_id", "status", "created_at"],
    )
    op.create_index(
        "uq_web_push_subscriptions_active_endpoint",
        "web_push_subscriptions",
        ["endpoint_hash"],
        unique=True,
        postgresql_where=sa.text("status = 'ACTIVE'"),
    )
    op.create_index(
        "uq_web_push_subscriptions_active_installation",
        "web_push_subscriptions",
        ["installation_id"],
        unique=True,
        postgresql_where=sa.text("status = 'ACTIVE'"),
    )
    op.create_table(
        "web_push_deliveries",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("subscription_id", sa.String(length=36), nullable=True),
        sa.Column("event_type", sa.String(length=48), nullable=False),
        sa.Column("dedupe_key", sa.String(length=64), nullable=False),
        sa.Column("route", sa.String(length=255), nullable=False),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="PENDING", nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_error_code", sa.String(length=64), nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("attempt_count >= 0", name="ck_web_push_deliveries_attempts"),
        sa.CheckConstraint(
            "status IN ('PENDING','SENT','FAILED','EXPIRED','SUPPRESSED')",
            name="ck_web_push_deliveries_status",
        ),
        sa.ForeignKeyConstraint(["subscription_id"], ["web_push_subscriptions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "subscription_id",
            "dedupe_key",
            name="uq_web_push_deliveries_subscription_dedupe",
        ),
    )
    op.create_index(
        "ix_web_push_deliveries_status_retry",
        "web_push_deliveries",
        ["status", "next_attempt_at"],
    )
    op.create_index(
        "ix_web_push_deliveries_user_created",
        "web_push_deliveries",
        ["user_id", "created_at"],
    )
    op.create_index("ix_web_push_deliveries_user_id", "web_push_deliveries", ["user_id"])

    op.execute("INSERT INTO platform_bootstrap_state (id) VALUES (1) ON CONFLICT (id) DO NOTHING")


def downgrade() -> None:
    op.drop_index("ix_web_push_deliveries_user_id", table_name="web_push_deliveries")
    op.drop_index("ix_web_push_deliveries_user_created", table_name="web_push_deliveries")
    op.drop_index("ix_web_push_deliveries_status_retry", table_name="web_push_deliveries")
    op.drop_table("web_push_deliveries")
    op.drop_index("uq_web_push_subscriptions_active_installation", table_name="web_push_subscriptions")
    op.drop_index("uq_web_push_subscriptions_active_endpoint", table_name="web_push_subscriptions")
    op.drop_index("ix_web_push_subscriptions_user_status", table_name="web_push_subscriptions")
    op.drop_index("ix_web_push_subscriptions_user_id", table_name="web_push_subscriptions")
    op.drop_table("web_push_subscriptions")
    op.drop_table("user_notification_preferences")
    op.drop_index("ix_platform_access_audit_correlation", table_name="platform_access_audit_events")
    op.drop_index("ix_platform_access_audit_type_created", table_name="platform_access_audit_events")
    op.drop_index("ix_platform_access_audit_subject_created", table_name="platform_access_audit_events")
    op.drop_index("ix_platform_access_audit_actor_created", table_name="platform_access_audit_events")
    op.drop_table("platform_access_audit_events")
    op.drop_index("ix_password_reset_tokens_user_expiry", table_name="password_reset_tokens")
    op.drop_index("ix_password_reset_tokens_user_id", table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")
    op.drop_index("ix_platform_access_invitations_actor_created", table_name="platform_access_invitations")
    op.drop_index("ix_platform_access_invitations_status_expiry", table_name="platform_access_invitations")
    op.drop_index("ix_platform_access_invitations_email_status", table_name="platform_access_invitations")
    op.drop_index("uq_platform_access_invitations_pending_email", table_name="platform_access_invitations")
    op.drop_table("platform_access_invitations")
    op.drop_index("ix_platform_admins_active", table_name="platform_admins")
    op.drop_table("platform_admins")
    op.drop_table("platform_bootstrap_state")
