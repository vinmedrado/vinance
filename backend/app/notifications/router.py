from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth.dependencies import get_current_user
from backend.app.auth.models import User
from backend.app.auth.rate_limit import enforce_auth_rate_limit
from backend.app.core.config import settings
from backend.app.core.database import get_session
from backend.app.notifications.schemas import (
    NotificationCapabilities,
    NotificationPreferencesRead,
    NotificationPreferencesUpdate,
    PushActionResult,
    PushSubscriptionCreate,
    PushSubscriptionRead,
)
from backend.app.notifications.service import (
    create_safe_push_deliveries,
    get_or_create_preferences,
    register_subscription,
    revoke_installation,
    update_preferences,
)
from backend.app.notifications.tasks import send_web_push_delivery


router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/capabilities", response_model=NotificationCapabilities)
async def capabilities(_: User = Depends(get_current_user)) -> NotificationCapabilities:
    return NotificationCapabilities(
        web_push_enabled=bool(settings.web_push_enabled),
        vapid_public_key=settings.vapid_public_key if settings.web_push_enabled else None,
    )


@router.get("/preferences", response_model=NotificationPreferencesRead)
async def preferences(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> NotificationPreferencesRead:
    return await get_or_create_preferences(session, user_id=current_user.id)


@router.patch("/preferences", response_model=NotificationPreferencesRead)
async def preferences_update(
    payload: NotificationPreferencesUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> NotificationPreferencesRead:
    return await update_preferences(session, user_id=current_user.id, payload=payload)


@router.post("/subscriptions", response_model=PushSubscriptionRead, status_code=201)
async def subscription_create(
    payload: PushSubscriptionCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> PushSubscriptionRead:
    await enforce_auth_rate_limit(
        "web-push-subscription",
        f"{current_user.id}:{payload.installation_id}",
        settings.platform_access_rate_limit,
    )
    user_agent = request.headers.get("user-agent", "")[:80]
    record = await register_subscription(
        session,
        user_id=current_user.id,
        payload=payload,
        user_agent_family=user_agent,
    )
    return PushSubscriptionRead(
        id=record.id,
        installation_id=record.installation_id,
        status=record.status,
        created_at=record.created_at,
    )


@router.delete("/subscriptions/{installation_id}", response_model=PushActionResult)
async def subscription_delete(
    installation_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> PushActionResult:
    revoked = await revoke_installation(
        session, user_id=current_user.id, installation_id=installation_id
    )
    return PushActionResult(
        status="REVOKED",
        message="Notificações desativadas neste dispositivo.",
        queued=revoked,
    )


@router.post("/test", response_model=PushActionResult, status_code=status.HTTP_202_ACCEPTED)
async def notification_test(
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> PushActionResult:
    client = request.client.host if request.client else "unknown"
    await enforce_auth_rate_limit(
        "web-push-test",
        f"{current_user.id}:{client}",
        settings.platform_access_rate_limit,
    )
    deliveries = await create_safe_push_deliveries(
        session,
        user_id=current_user.id,
        event_type="TEST",
        dedupe_key=f"test:{current_user.id}:{uuid4().hex}"[:64],
        title="Vinance",
        body="As notificações estão funcionando neste dispositivo.",
        route="/account/settings",
    )
    for delivery in deliveries:
        send_web_push_delivery.delay(delivery.id)
    return PushActionResult(
        status="QUEUED" if deliveries else "DISABLED",
        message=(
            "Notificação de teste enfileirada."
            if deliveries
            else "Ative as notificações e registre este dispositivo primeiro."
        ),
        queued=len(deliveries),
    )
