from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth.dependencies import get_current_user
from backend.app.auth.models import User
from backend.app.core.database import get_session
from backend.app.investment_alerts.repository import (
    DuplicateSubscriptionError,
    get_owned_alert,
    list_owned_alerts,
    mark_owned_alert_read,
)
from backend.app.investment_alerts.schemas import (
    AlertDetail,
    AlertMetrics,
    AlertPage,
    SubscriptionCreate,
    SubscriptionList,
    SubscriptionResponse,
    SubscriptionUpdate,
)
from backend.app.investment_alerts.service import (
    SubscriptionLimitError,
    SubscriptionNotFoundError,
    SubscriptionSourceError,
    alert_metrics,
    create_monitoring_subscription,
    list_monitoring_subscriptions,
    remove_monitoring_subscription,
    update_monitoring_subscription,
)
from backend.app.investment_decisions.service import normalize_asset_filter, parse_decision_id


router = APIRouter(prefix="/investments", tags=["investment-alerts"])


def _private(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"


def _validate_period(date_from: datetime | None, date_to: datetime | None) -> None:
    if (date_from and date_from.tzinfo is None) or (date_to and date_to.tzinfo is None):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Filtros de período devem incluir timezone",
        )
    if date_from and date_to and date_from > date_to:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="date_from deve ser anterior a date_to",
        )


def _subscription_error(exc: Exception) -> HTTPException:
    if isinstance(exc, DuplicateSubscriptionError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ativo já monitorado")
    if isinstance(exc, SubscriptionLimitError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if isinstance(exc, SubscriptionSourceError):
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc))
    if isinstance(exc, SubscriptionNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Monitoramento não encontrado")
    return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Falha no monitoramento")


@router.get("/alert-subscriptions", response_model=SubscriptionList)
async def subscriptions_list(
    response: Response,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    _private(response)
    return await list_monitoring_subscriptions(session, user_id=current_user.id)


@router.post(
    "/alert-subscriptions",
    response_model=SubscriptionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def subscription_create(
    payload: SubscriptionCreate,
    response: Response,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    _private(response)
    try:
        return await create_monitoring_subscription(
            session, user_id=current_user.id, payload=payload
        )
    except (DuplicateSubscriptionError, SubscriptionLimitError, SubscriptionSourceError) as exc:
        raise _subscription_error(exc) from exc


@router.patch("/alert-subscriptions/{subscription_id}", response_model=SubscriptionResponse)
async def subscription_update(
    payload: SubscriptionUpdate,
    response: Response,
    subscription_id: int = Path(ge=1),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    _private(response)
    try:
        return await update_monitoring_subscription(
            session,
            user_id=current_user.id,
            subscription_id=subscription_id,
            payload=payload,
        )
    except (SubscriptionNotFoundError, SubscriptionLimitError) as exc:
        raise _subscription_error(exc) from exc


@router.delete(
    "/alert-subscriptions/{subscription_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def subscription_delete(
    response: Response,
    subscription_id: int = Path(ge=1),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    _private(response)
    try:
        await remove_monitoring_subscription(
            session, user_id=current_user.id, subscription_id=subscription_id
        )
    except SubscriptionNotFoundError as exc:
        raise _subscription_error(exc) from exc


@router.get("/alerts/metrics", response_model=AlertMetrics)
async def alerts_metrics(
    response: Response,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    _private(response)
    return await alert_metrics(session, user_id=current_user.id)


@router.get("/alerts", response_model=AlertPage)
async def alerts_list(
    response: Response,
    page: int = Query(default=1, ge=1, le=100_000),
    page_size: int = Query(default=10, ge=1, le=50),
    asset: str | None = Query(default=None, min_length=1, max_length=32, pattern=r"^[A-Za-z0-9.\-]+$"),
    alert_type: Literal[
        "NEW_OPPORTUNITY", "ACTION_CHANGE", "SCORE_CHANGE", "CONFIDENCE_CHANGE", "RISK_CHANGE"
    ] | None = Query(default=None),
    severity: Literal["INFO", "MEDIUM", "HIGH"] | None = Query(default=None),
    unread_only: bool = Query(default=False),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    _private(response)
    _validate_period(date_from, date_to)
    normalized_asset = normalize_asset_filter(asset) if asset else None
    return await list_owned_alerts(
        session,
        user_id=current_user.id,
        page=page,
        page_size=page_size,
        asset=normalized_asset,
        alert_type=alert_type,
        severity=severity,
        unread_only=unread_only,
        date_from=date_from,
        date_to=date_to,
    )


def _normalized_alert_id(alert_id: str) -> str:
    normalized = parse_decision_id(alert_id)
    if normalized is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alerta não encontrado")
    return normalized


@router.get("/alerts/{alert_id}", response_model=AlertDetail)
async def alert_detail(
    alert_id: str,
    response: Response,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    _private(response)
    alert = await get_owned_alert(
        session,
        user_id=current_user.id,
        alert_id=_normalized_alert_id(alert_id),
    )
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alerta não encontrado")
    return alert


@router.patch("/alerts/{alert_id}/read", response_model=AlertDetail)
async def alert_mark_read(
    alert_id: str,
    response: Response,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    _private(response)
    alert = await mark_owned_alert_read(
        session,
        user_id=current_user.id,
        alert_id=_normalized_alert_id(alert_id),
        read_at=datetime.now(timezone.utc),
    )
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alerta não encontrado")
    return alert
