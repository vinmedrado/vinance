from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from uuid import uuid4

from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import settings
from backend.app.notifications.models import (
    UserNotificationPreference,
    WebPushDelivery,
    WebPushSubscription,
)
from backend.app.notifications.schemas import (
    NotificationPreferencesUpdate,
    PushSubscriptionCreate,
    validate_public_push_endpoint,
)


ALLOWED_NOTIFICATION_ROUTES = (
    "/account/settings",
    "/household",
    "/investir",
    "/intelligence",
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _fernet() -> Fernet:
    key = (settings.push_subscription_encryption_key or "").encode("ascii")
    try:
        return Fernet(key)
    except (ValueError, TypeError) as exc:
        raise RuntimeError("Web Push subscription encryption is not configured") from exc


def encrypt_subscription(subscription: dict[str, object]) -> str:
    encoded = json.dumps(subscription, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return _fernet().encrypt(encoded).decode("ascii")


def decrypt_subscription(ciphertext: str) -> dict[str, object]:
    try:
        decoded = _fernet().decrypt(ciphertext.encode("ascii"))
        result = json.loads(decoded)
    except (InvalidToken, ValueError, TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError("Stored Web Push subscription is unreadable") from exc
    if not isinstance(result, dict):
        raise RuntimeError("Stored Web Push subscription is invalid")
    return result


def endpoint_digest(endpoint: str) -> str:
    return hashlib.sha256(endpoint.encode("utf-8")).hexdigest()


async def get_or_create_preferences(
    session: AsyncSession, *, user_id: int
) -> UserNotificationPreference:
    record = await session.get(UserNotificationPreference, user_id)
    if record is None:
        record = UserNotificationPreference(user_id=user_id, push_enabled=False)
        session.add(record)
        await session.commit()
        await session.refresh(record)
    return record


async def update_preferences(
    session: AsyncSession,
    *,
    user_id: int,
    payload: NotificationPreferencesUpdate,
) -> UserNotificationPreference:
    record = await get_or_create_preferences(session, user_id=user_id)
    for key, value in payload.model_dump(exclude_none=True).items():
        setattr(record, key, value)
    await session.commit()
    await session.refresh(record)
    return record


async def register_subscription(
    session: AsyncSession,
    *,
    user_id: int,
    payload: PushSubscriptionCreate,
    user_agent_family: str | None = None,
) -> WebPushSubscription:
    if not settings.web_push_enabled:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Web Push is disabled")
    subscription_dict = payload.subscription.model_dump(by_alias=True, mode="json")
    endpoint = str(payload.subscription.endpoint)
    validate_public_push_endpoint(endpoint)
    digest = endpoint_digest(endpoint)

    endpoint_record = await session.scalar(
        select(WebPushSubscription)
        .where(
            WebPushSubscription.endpoint_hash == digest,
            WebPushSubscription.status == "ACTIVE",
        )
        .with_for_update()
    )
    if endpoint_record is not None and endpoint_record.user_id != user_id:
        raise HTTPException(status_code=409, detail="This push endpoint belongs to another account")

    installation_record = await session.scalar(
        select(WebPushSubscription)
        .where(
            WebPushSubscription.installation_id == payload.installation_id,
            WebPushSubscription.status == "ACTIVE",
        )
        .with_for_update()
    )
    if installation_record is not None and installation_record.user_id != user_id:
        raise HTTPException(status_code=409, detail="This installation belongs to another account")

    record = endpoint_record or installation_record
    if record is not None:
        record.endpoint_hash = digest
        record.installation_id = payload.installation_id
        record.subscription_encrypted = encrypt_subscription(subscription_dict)
        record.last_used_at = utcnow()
        record.user_agent_family = (user_agent_family or "")[:80] or None
    else:
        record = WebPushSubscription(
            id=str(uuid4()),
            user_id=user_id,
            installation_id=payload.installation_id,
            endpoint_hash=digest,
            subscription_encrypted=encrypt_subscription(subscription_dict),
            encryption_key_version=1,
            status="ACTIVE",
            user_agent_family=(user_agent_family or "")[:80] or None,
            last_used_at=utcnow(),
        )
        session.add(record)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Push subscription conflicts with another account") from exc
    await session.refresh(record)
    return record


async def revoke_installation(
    session: AsyncSession, *, user_id: int, installation_id: str
) -> int:
    records = list(
        (
            await session.scalars(
                select(WebPushSubscription)
                .where(
                    WebPushSubscription.user_id == user_id,
                    WebPushSubscription.installation_id == installation_id,
                    WebPushSubscription.status == "ACTIVE",
                )
                .with_for_update()
            )
        ).all()
    )
    now = utcnow()
    for record in records:
        record.status = "REVOKED"
        record.revoked_at = now
    if records:
        active_devices = await session.scalar(
            select(func.count())
            .select_from(WebPushSubscription)
            .where(
                WebPushSubscription.user_id == user_id,
                WebPushSubscription.status == "ACTIVE",
            )
        )
        if int(active_devices or 0) == 0:
            preferences = await session.get(UserNotificationPreference, user_id)
            if preferences is not None:
                preferences.push_enabled = False
    await session.commit()
    return len(records)


async def revoke_user_push_access(session: AsyncSession, *, user_id: int) -> None:
    """Revoke every device and suppress queued delivery for an inactive user."""

    from sqlalchemy import update

    now = utcnow()
    await session.execute(
        update(WebPushSubscription)
        .where(
            WebPushSubscription.user_id == user_id,
            WebPushSubscription.status == "ACTIVE",
        )
        .values(status="REVOKED", revoked_at=now)
    )
    await session.execute(
        update(WebPushDelivery)
        .where(
            WebPushDelivery.user_id == user_id,
            WebPushDelivery.status.in_(("PENDING", "FAILED")),
        )
        .values(
            status="SUPPRESSED",
            next_attempt_at=None,
            last_error_code="USER_DEACTIVATED",
        )
    )


def _event_preference(preferences: UserNotificationPreference, event_type: str) -> bool:
    mapping = {
        "ACCOUNT_EVENT": preferences.account_events_enabled,
        "HOUSEHOLD_INVITATION": preferences.household_invites_enabled,
        "FINANCIAL_ALERT": preferences.financial_alerts_enabled,
        "ANALYSIS_UPDATE": preferences.analysis_updates_enabled,
        "TEST": True,
    }
    return bool(mapping.get(event_type, False))


def _validate_safe_payload(*, title: str, body: str, route: str) -> None:
    if route not in ALLOWED_NOTIFICATION_ROUTES:
        raise ValueError("Notification route is not allowlisted")
    if len(title) > 60 or len(body) > 180:
        raise ValueError("Notification copy is too long")
    forbidden = ("R$", "USDT", "saldo:", "senha", "token")
    normalized = body.lower()
    if any(marker.lower() in normalized for marker in forbidden):
        raise ValueError("Notification payload may expose sensitive financial data")


async def create_safe_push_deliveries(
    session: AsyncSession,
    *,
    user_id: int,
    event_type: str,
    dedupe_key: str,
    title: str,
    body: str,
    route: str,
) -> list[WebPushDelivery]:
    _validate_safe_payload(title=title, body=body, route=route)
    preferences = await get_or_create_preferences(session, user_id=user_id)
    if not preferences.push_enabled or not _event_preference(preferences, event_type):
        return []
    subscriptions = list(
        (
            await session.scalars(
                select(WebPushSubscription).where(
                    WebPushSubscription.user_id == user_id,
                    WebPushSubscription.status == "ACTIVE",
                )
            )
        ).all()
    )
    deliveries: list[WebPushDelivery] = []
    for subscription in subscriptions:
        delivery = WebPushDelivery(
            id=str(uuid4()),
            user_id=user_id,
            subscription_id=subscription.id,
            event_type=event_type,
            dedupe_key=dedupe_key[:64],
            route=route,
            payload_json={"title": title, "body": body, "route": route},
            status="PENDING",
            attempt_count=0,
        )
        session.add(delivery)
        deliveries.append(delivery)
    if deliveries:
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            return []
        for delivery in deliveries:
            await session.refresh(delivery)
    return deliveries
