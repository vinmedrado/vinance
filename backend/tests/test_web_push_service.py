from __future__ import annotations

import os
import sys
from types import ModuleType

import pytest
import pytest_asyncio
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.app.auth.schemas import UserCreate
from backend.app.auth.service import create_user
from backend.app.core.config import settings
from backend.app.notifications.models import (
    UserNotificationPreference,
    WebPushDelivery,
    WebPushSubscription,
)
from backend.app.notifications.schemas import PushSubscriptionCreate
from backend.app.notifications.service import (
    create_safe_push_deliveries,
    decrypt_subscription,
    get_or_create_preferences,
    register_subscription,
    revoke_installation,
)
from backend.app.notifications.tasks import MAX_PUSH_ATTEMPTS, _send_delivery
from backend.app.platform_access.service import set_user_active


TEST_DATABASE_URL = os.getenv("AUTOPILOT_TEST_DATABASE_URL")

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(
        not TEST_DATABASE_URL,
        reason="set AUTOPILOT_TEST_DATABASE_URL to an isolated PostgreSQL database",
    ),
]


@pytest_asyncio.fixture
async def push_context(monkeypatch):
    assert TEST_DATABASE_URL is not None and "test" in TEST_DATABASE_URL.lower()
    engine = create_async_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.execute(text("SET LOCAL session_replication_role = 'replica'"))
        await connection.execute(text("TRUNCATE TABLE users RESTART IDENTITY CASCADE"))
        await connection.execute(text("SET LOCAL session_replication_role = 'origin'"))
        await connection.execute(
            text(
                "INSERT INTO platform_bootstrap_state (id, completed_at, completed_by_user_id) "
                "VALUES (1, NULL, NULL) ON CONFLICT (id) DO UPDATE SET "
                "completed_at = NULL, completed_by_user_id = NULL"
            )
        )
    from cryptography.fernet import Fernet

    monkeypatch.setattr(
        settings,
        "push_subscription_encryption_key",
        Fernet.generate_key().decode("ascii"),
    )
    monkeypatch.setattr(settings, "web_push_enabled", True)
    yield factory
    await engine.dispose()


def _payload(endpoint: str, installation: str) -> PushSubscriptionCreate:
    return PushSubscriptionCreate(
        installation_id=installation,
        subscription={
            "endpoint": endpoint,
            "expirationTime": None,
            "keys": {"p256dh": "p" * 88, "auth": "a" * 24},
        },
    )


async def _users(factory):
    async with factory() as session:
        a = await create_user(
            session,
            UserCreate(email="a@example.com", password="password-A-strong", full_name="A"),
        )
    async with factory() as session:
        b = await create_user(
            session,
            UserCreate(email="b@example.com", password="password-B-strong", full_name="B"),
        )
    return a, b


async def test_subscription_is_encrypted_and_bound_to_authenticated_owner(push_context) -> None:
    a, _ = await _users(push_context)
    payload = _payload("https://fcm.googleapis.com/fcm/send/one", "install-A")
    async with push_context() as session:
        record = await register_subscription(session, user_id=a.id, payload=payload)
        assert "fcm.googleapis.com" not in record.subscription_encrypted
        decoded = decrypt_subscription(record.subscription_encrypted)
        assert decoded["endpoint"] == str(payload.subscription.endpoint)


async def test_active_endpoint_cannot_be_silently_reassigned_to_another_user(push_context) -> None:
    a, b = await _users(push_context)
    payload = _payload("https://fcm.googleapis.com/fcm/send/shared", "install-A")
    async with push_context() as session:
        await register_subscription(session, user_id=a.id, payload=payload)
    async with push_context() as session:
        with pytest.raises(HTTPException) as collision:
            await register_subscription(
                session,
                user_id=b.id,
                payload=_payload(payload.subscription.endpoint, "install-B"),
            )
        assert collision.value.status_code == 409


async def test_revoked_installation_can_be_registered_again_without_cross_account_leak(
    push_context,
) -> None:
    a, b = await _users(push_context)
    endpoint = "https://fcm.googleapis.com/fcm/send/reusable"
    async with push_context() as session:
        await register_subscription(session, user_id=a.id, payload=_payload(endpoint, "install-shared"))
    async with push_context() as session:
        assert await revoke_installation(session, user_id=a.id, installation_id="install-shared") == 1
    async with push_context() as session:
        record = await register_subscription(
            session,
            user_id=b.id,
            payload=_payload(endpoint, "install-shared"),
        )
        assert record.user_id == b.id


async def test_push_is_opt_in_and_safe_delivery_contains_no_financial_values(push_context) -> None:
    a, _ = await _users(push_context)
    async with push_context() as session:
        preferences = await get_or_create_preferences(session, user_id=a.id)
        assert preferences.push_enabled is False
        await register_subscription(
            session,
            user_id=a.id,
            payload=_payload("https://fcm.googleapis.com/fcm/send/notify", "install-notify"),
        )
        suppressed = await create_safe_push_deliveries(
            session,
            user_id=a.id,
            event_type="ACCOUNT_EVENT",
            dedupe_key="test-disabled",
            title="Vinance",
            body="Há uma atualização importante na sua conta.",
            route="/account/settings",
        )
        assert suppressed == []

        preferences.push_enabled = True
        await session.commit()
        deliveries = await create_safe_push_deliveries(
            session,
            user_id=a.id,
            event_type="ACCOUNT_EVENT",
            dedupe_key="test-enabled",
            title="Vinance",
            body="Há uma atualização importante na sua conta.",
            route="/account/settings",
        )
        assert len(deliveries) == 1
        assert deliveries[0].payload_json == {
            "title": "Vinance",
            "body": "Há uma atualização importante na sua conta.",
            "route": "/account/settings",
        }
        assert not any(char.isdigit() for char in deliveries[0].payload_json["body"])


@pytest.mark.parametrize(
    "endpoint",
    (
        "http://fcm.googleapis.com/fcm/send/insecure",
        "https://127.0.0.1/push",
        "https://localhost/push",
        "https://example.com/push",
        "https://fcm.googleapis.com:8443/fcm/send/wrong-port",
        "https://user@fcm.googleapis.com/fcm/send/credentials",
    ),
)
async def test_push_endpoint_validation_blocks_ssrf_targets(endpoint: str) -> None:
    with pytest.raises(ValidationError):
        _payload(endpoint, "install-ssrf")


async def test_one_event_is_queued_once_for_each_active_device(push_context) -> None:
    a, _ = await _users(push_context)
    async with push_context() as session:
        preferences = await get_or_create_preferences(session, user_id=a.id)
        preferences.push_enabled = True
        await register_subscription(
            session,
            user_id=a.id,
            payload=_payload("https://fcm.googleapis.com/fcm/send/device-one", "install-one"),
        )
        await register_subscription(
            session,
            user_id=a.id,
            payload=_payload("https://updates.push.services.mozilla.com/wpush/v2/device-two", "install-two"),
        )
        deliveries = await create_safe_push_deliveries(
            session,
            user_id=a.id,
            event_type="ACCOUNT_EVENT",
            dedupe_key="same-event-two-devices",
            title="Vinance",
            body="Há uma atualização importante na sua conta.",
            route="/account/settings",
        )
        assert len(deliveries) == 2
        repeated = await create_safe_push_deliveries(
            session,
            user_id=a.id,
            event_type="ACCOUNT_EVENT",
            dedupe_key="same-event-two-devices",
            title="Vinance",
            body="Há uma atualização importante na sua conta.",
            route="/account/settings",
        )
        assert repeated == []


async def test_user_cannot_revoke_another_users_installation(push_context) -> None:
    a, b = await _users(push_context)
    async with push_context() as session:
        await register_subscription(
            session,
            user_id=a.id,
            payload=_payload("https://fcm.googleapis.com/fcm/send/owner-only", "install-owner"),
        )
    async with push_context() as session:
        assert await revoke_installation(
            session, user_id=b.id, installation_id="install-owner"
        ) == 0
    async with push_context() as session:
        record = await session.scalar(
            select(WebPushSubscription).where(
                WebPushSubscription.user_id == a.id,
                WebPushSubscription.installation_id == "install-owner",
            )
        )
        assert record is not None and record.status == "ACTIVE"


async def test_revoking_one_device_does_not_disable_the_others(push_context) -> None:
    a, _ = await _users(push_context)
    async with push_context() as session:
        preferences = await get_or_create_preferences(session, user_id=a.id)
        preferences.push_enabled = True
        await register_subscription(
            session,
            user_id=a.id,
            payload=_payload("https://fcm.googleapis.com/fcm/send/keep-one", "install-keep"),
        )
        await register_subscription(
            session,
            user_id=a.id,
            payload=_payload("https://fcm.googleapis.com/fcm/send/remove-one", "install-remove"),
        )
        assert await revoke_installation(
            session, user_id=a.id, installation_id="install-remove"
        ) == 1
    async with push_context() as session:
        preferences = await session.get(UserNotificationPreference, a.id)
        active_count = await session.scalar(
            select(text("count(*)")).select_from(WebPushSubscription).where(
                WebPushSubscription.user_id == a.id,
                WebPushSubscription.status == "ACTIVE",
            )
        )
        assert active_count == 1
        assert preferences is not None and preferences.push_enabled is True


async def test_revoking_the_last_device_disables_push_preference(push_context) -> None:
    a, _ = await _users(push_context)
    async with push_context() as session:
        preferences = await get_or_create_preferences(session, user_id=a.id)
        preferences.push_enabled = True
        await register_subscription(
            session,
            user_id=a.id,
            payload=_payload("https://fcm.googleapis.com/fcm/send/last-one", "install-last"),
        )
        assert await revoke_installation(
            session, user_id=a.id, installation_id="install-last"
        ) == 1
    async with push_context() as session:
        preferences = await session.get(UserNotificationPreference, a.id)
        assert preferences is not None and preferences.push_enabled is False


async def _pending_delivery(factory, user_id: int, suffix: str) -> tuple[str, str]:
    async with factory() as session:
        preferences = await get_or_create_preferences(session, user_id=user_id)
        preferences.push_enabled = True
        subscription = await register_subscription(
            session,
            user_id=user_id,
            payload=_payload(
                f"https://fcm.googleapis.com/fcm/send/{suffix}",
                f"install-{suffix}",
            ),
        )
        deliveries = await create_safe_push_deliveries(
            session,
            user_id=user_id,
            event_type="TEST",
            dedupe_key=f"delivery-{suffix}",
            title="Vinance",
            body="As notificações estão funcionando neste dispositivo.",
            route="/account/settings",
        )
        return deliveries[0].id, subscription.id


def _fake_pywebpush(monkeypatch, *, status_code: int | None) -> None:
    module = ModuleType("pywebpush")

    class FakeWebPushException(Exception):
        def __init__(self):
            super().__init__("provider failure")
            self.response = (
                type("Response", (), {"status_code": status_code})()
                if status_code is not None
                else None
            )

    def webpush(**_kwargs):
        raise FakeWebPushException()

    module.WebPushException = FakeWebPushException
    module.webpush = webpush
    monkeypatch.setitem(sys.modules, "pywebpush", module)


async def test_provider_410_expires_subscription_without_retry(
    push_context, monkeypatch
) -> None:
    import backend.app.notifications.tasks as tasks

    a, _ = await _users(push_context)
    delivery_id, subscription_id = await _pending_delivery(push_context, a.id, "gone")
    monkeypatch.setattr(tasks, "AsyncSessionLocal", push_context)
    _fake_pywebpush(monkeypatch, status_code=410)
    result = await _send_delivery(delivery_id)
    assert result == {"status": "EXPIRED", "attempt": 1, "retry": False}
    async with push_context() as session:
        subscription = await session.get(WebPushSubscription, subscription_id)
        assert subscription is not None and subscription.status == "EXPIRED"


async def test_provider_failures_stop_retrying_after_bounded_attempts(
    push_context, monkeypatch
) -> None:
    import backend.app.notifications.tasks as tasks

    a, _ = await _users(push_context)
    delivery_id, _ = await _pending_delivery(push_context, a.id, "retry")
    monkeypatch.setattr(tasks, "AsyncSessionLocal", push_context)
    _fake_pywebpush(monkeypatch, status_code=503)
    results = [await _send_delivery(delivery_id) for _ in range(MAX_PUSH_ATTEMPTS)]
    assert [item["attempt"] for item in results] == [1, 2, 3, 4]
    assert [item["retry"] for item in results] == [True, True, True, False]
    async with push_context() as session:
        delivery = await session.get(WebPushDelivery, delivery_id)
        assert delivery is not None
        assert delivery.status == "FAILED"
        assert delivery.next_attempt_at is None


async def test_deactivating_user_revokes_devices_and_suppresses_queue(
    push_context,
) -> None:
    a, b = await _users(push_context)
    delivery_id, subscription_id = await _pending_delivery(push_context, b.id, "deactivate")
    async with push_context() as session:
        await set_user_active(
            session,
            actor_user_id=a.id,
            target_user_id=b.id,
            active=False,
        )
    async with push_context() as session:
        subscription = await session.get(WebPushSubscription, subscription_id)
        delivery = await session.get(WebPushDelivery, delivery_id)
        assert subscription is not None and subscription.status == "REVOKED"
        assert delivery is not None and delivery.status == "SUPPRESSED"
        assert delivery.last_error_code == "USER_DEACTIVATED"
