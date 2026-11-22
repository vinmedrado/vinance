from __future__ import annotations

import asyncio
from datetime import timedelta
import json

from sqlalchemy import select

from backend.app.core.celery import celery_app
from backend.app.core.config import settings
from backend.app.core.database import AsyncSessionLocal, engine
from backend.app.core.logging import get_logger
from backend.app.notifications.models import WebPushDelivery, WebPushSubscription
from backend.app.notifications.schemas import validate_public_push_endpoint
from backend.app.notifications.service import create_safe_push_deliveries, decrypt_subscription, utcnow


logger = get_logger(__name__)
MAX_PUSH_ATTEMPTS = 4


async def _send_delivery(delivery_id: str) -> dict[str, str | int]:
    async with AsyncSessionLocal() as session:
        delivery = (
            await session.execute(
                select(WebPushDelivery)
                .where(WebPushDelivery.id == delivery_id)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if delivery is None or delivery.status not in {"PENDING", "FAILED"}:
            return {"status": "IGNORED"}
        subscription = await session.get(WebPushSubscription, delivery.subscription_id)
        if subscription is None or subscription.status != "ACTIVE":
            delivery.status = "EXPIRED"
            await session.commit()
            return {"status": "EXPIRED"}
        info = decrypt_subscription(subscription.subscription_encrypted)
        validate_public_push_endpoint(str(info.get("endpoint", "")))
        payload = json.dumps(delivery.payload_json, separators=(",", ":"), ensure_ascii=False)
        try:
            from pywebpush import WebPushException, webpush

            await asyncio.to_thread(
                webpush,
                subscription_info=info,
                data=payload,
                vapid_private_key=settings.vapid_private_key,
                vapid_claims={"sub": settings.vapid_subject},
                ttl=300,
            )
        except Exception as exc:  # provider exception is normalized without payload/endpoint logs
            response = getattr(exc, "response", None)
            response_status = getattr(response, "status_code", None)
            delivery.attempt_count += 1
            delivery.last_error_code = f"HTTP_{response_status}" if response_status else type(exc).__name__[:64]
            if response_status in {404, 410}:
                subscription.status = "EXPIRED"
                subscription.revoked_at = utcnow()
                delivery.status = "EXPIRED"
            else:
                delivery.status = "FAILED"
                delivery.next_attempt_at = (
                    utcnow() + timedelta(minutes=2 ** min(delivery.attempt_count, 4))
                    if delivery.attempt_count < MAX_PUSH_ATTEMPTS
                    else None
                )
            await session.commit()
            logger.warning(
                "web_push.delivery_failed",
                extra={
                    "event": "web_push.delivery_failed",
                    "delivery_id": delivery.id,
                    "error_code": delivery.last_error_code,
                    "attempt": delivery.attempt_count,
                },
            )
            return {
                "status": delivery.status,
                "attempt": delivery.attempt_count,
                "retry": delivery.status == "FAILED" and delivery.attempt_count < MAX_PUSH_ATTEMPTS,
            }
        delivery.status = "SENT"
        delivery.sent_at = utcnow()
        delivery.attempt_count += 1
        delivery.last_error_code = None
        subscription.last_used_at = utcnow()
        await session.commit()
        return {"status": "SENT", "attempt": delivery.attempt_count}


async def _queue_event(
    *,
    user_id: int,
    event_type: str,
    dedupe_key: str,
    title: str,
    body: str,
    route: str,
) -> dict[str, object]:
    async with AsyncSessionLocal() as session:
        deliveries = await create_safe_push_deliveries(
            session,
            user_id=user_id,
            event_type=event_type,
            dedupe_key=dedupe_key,
            title=title,
            body=body,
            route=route,
        )
    for delivery in deliveries:
        send_web_push_delivery.delay(delivery.id)
    return {"status": "QUEUED", "deliveries": len(deliveries)}


def _run(coro):
    try:
        return asyncio.run(coro)
    finally:
        asyncio.run(engine.dispose())


@celery_app.task(
    bind=True,
    name="notifications.send_web_push",
    queue="default",
    max_retries=MAX_PUSH_ATTEMPTS - 1,
)
def send_web_push_delivery(self, delivery_id: str) -> dict[str, str | int | bool]:
    result = _run(_send_delivery(delivery_id))
    if result.get("retry"):
        attempt = int(result.get("attempt", 1))
        raise self.retry(
            exc=RuntimeError("Web Push provider delivery failed"),
            countdown=60 * (2 ** min(attempt, 4)),
        )
    return result


@celery_app.task(name="notifications.queue_safe_event", queue="default")
def queue_safe_notification(**kwargs) -> dict[str, object]:
    return _run(_queue_event(**kwargs))
