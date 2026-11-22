from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

from backend.app.notifications.models import (
    UserNotificationPreference,
    WebPushDelivery,
    WebPushSubscription,
)
from backend.app.platform_access.models import (
    PasswordResetToken,
    PlatformAccessAuditEvent,
    PlatformAccessInvitation,
    PlatformAdmin,
    PlatformBootstrapState,
)


ROOT = Path(__file__).resolve().parents[2]


def _constraint_names(table) -> set[str]:
    return {constraint.name for constraint in table.constraints if constraint.name}


def _index_names(table) -> set[str]:
    return {index.name for index in table.indexes if index.name}


def test_access_schema_has_one_canonical_alembic_head() -> None:
    config = Config(str(ROOT / "alembic.ini"))
    script = ScriptDirectory.from_config(config)
    assert script.get_heads() == ["0029_access_pwa_push_v1"]


def test_bootstrap_and_platform_admin_are_separate_from_household_ownership() -> None:
    bootstrap = PlatformBootstrapState.__table__
    assert {"id", "completed_at", "completed_by_user_id"} <= set(bootstrap.columns.keys())
    assert "ck_platform_bootstrap_state_singleton" in _constraint_names(bootstrap)

    admins = PlatformAdmin.__table__
    assert {"user_id", "status", "created_at", "created_by_user_id"} <= set(admins.columns.keys())
    assert "household_id" not in admins.columns
    assert "ck_platform_admins_status" in _constraint_names(admins)


def test_platform_invites_and_password_resets_store_only_token_digests() -> None:
    invitations = PlatformAccessInvitation.__table__
    assert {
        "email_normalized",
        "token_hash",
        "status",
        "expires_at",
        "accepted_at",
        "cancelled_at",
        "cloudflare_access_status",
        "delivery_status",
    } <= set(invitations.columns.keys())
    assert "token" not in invitations.columns
    assert invitations.columns.token_hash.type.length == 64
    assert "uq_platform_access_invitations_token_hash" in _constraint_names(invitations)
    assert "uq_platform_access_invitations_pending_email" in _index_names(invitations)

    resets = PasswordResetToken.__table__
    assert {"user_id", "token_hash", "expires_at", "used_at", "revoked_at"} <= set(
        resets.columns.keys()
    )
    assert "token" not in resets.columns
    assert resets.columns.token_hash.type.length == 64


def test_access_audit_contract_does_not_persist_raw_credentials() -> None:
    audit = PlatformAccessAuditEvent.__table__
    assert {"actor_user_id", "subject_user_id", "event_type", "metadata_json", "created_at"} <= set(
        audit.columns.keys()
    )
    forbidden = {"password", "token", "secret", "credential"}
    assert forbidden.isdisjoint(audit.columns.keys())


def test_push_subscription_is_owner_bound_and_endpoint_is_not_plaintext() -> None:
    subscriptions = WebPushSubscription.__table__
    assert {
        "user_id",
        "installation_id",
        "endpoint_hash",
        "subscription_encrypted",
        "status",
        "last_used_at",
    } <= set(subscriptions.columns.keys())
    assert "endpoint" not in subscriptions.columns
    assert "p256dh" not in subscriptions.columns
    assert "auth" not in subscriptions.columns
    assert "uq_web_push_subscriptions_active_endpoint" in _index_names(subscriptions)
    assert "uq_web_push_subscriptions_active_installation" in _index_names(subscriptions)


def test_push_preferences_and_deliveries_support_idempotent_safe_events() -> None:
    preferences = UserNotificationPreference.__table__
    assert {
        "user_id",
        "push_enabled",
        "account_events_enabled",
        "household_invites_enabled",
        "financial_alerts_enabled",
    } <= set(preferences.columns.keys())

    deliveries = WebPushDelivery.__table__
    assert {
        "user_id",
        "subscription_id",
        "event_type",
        "dedupe_key",
        "route",
        "status",
        "attempt_count",
    } <= set(deliveries.columns.keys())
    assert "uq_web_push_deliveries_subscription_dedupe" in _constraint_names(deliveries)
    assert "financial_value" not in deliveries.columns
