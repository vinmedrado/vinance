from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth.dependencies import get_current_user
from backend.app.auth.models import User
from backend.app.auth.rate_limit import enforce_auth_rate_limit
from backend.app.core.config import settings
from backend.app.core.database import get_session
from backend.app.financial_state.service import FinancialStateDomainError

from . import service
from .errors import TradingDomainError
from .schemas import (
    IdempotentAction,
    PaperAccountCreate,
    PaperAccountRead,
    PaperOrderCreate,
    PaperOrderRead,
    PaperPositionRead,
    TradingBacktestRead,
    TradingHealthRead,
    TradingListResponse,
    TradingModelRead,
    TradingOverviewRead,
    TradingRiskBudgetRead,
)


router = APIRouter(prefix="/trading", tags=["trading-paper"])


async def _limit_mutation(user_id: int, action: str) -> None:
    await enforce_auth_rate_limit(
        f"trading-{action}",
        str(user_id),
        settings.trading_mutation_rate_limit,
        unavailable_detail="Trading temporariamente indisponível",
        exceeded_detail="Muitas ações de Trading em pouco tempo; tente novamente em instantes",
    )


def _domain_http(exc: Exception) -> HTTPException:
    if isinstance(exc, TradingDomainError):
        return HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": str(exc)},
        )
    if isinstance(exc, FinancialStateDomainError):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "FINANCIAL_CONTEXT_NOT_FOUND", "message": "financial context not found"},
        )
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={"code": "TRADING_INTERNAL_ERROR", "message": "Trading operation failed"},
    )


@router.get("/overview", response_model=TradingOverviewRead)
async def trading_overview(
    household_id: int = Query(gt=0),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    try:
        return await service.overview(
            session, user_id=current_user.id, household_id=household_id
        )
    except (TradingDomainError, FinancialStateDomainError) as exc:
        raise _domain_http(exc) from exc


@router.get("/risk-budget", response_model=TradingRiskBudgetRead)
async def trading_risk_budget(
    household_id: int = Query(gt=0),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    try:
        return await service.get_risk_budget(
            session, user_id=current_user.id, household_id=household_id
        )
    except (TradingDomainError, FinancialStateDomainError) as exc:
        raise _domain_http(exc) from exc


@router.get("/opportunities", response_model=TradingListResponse)
async def trading_opportunities(
    symbol: str | None = Query(default=None, min_length=3, max_length=40),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    try:
        return await service.list_opportunities(
            session, symbol=symbol, limit=limit, offset=offset
        )
    except TradingDomainError as exc:
        raise _domain_http(exc) from exc


@router.get("/signals", response_model=TradingListResponse)
async def trading_signals(
    symbol: str | None = Query(default=None, min_length=3, max_length=40),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    try:
        return await service.list_signals(
            session, symbol=symbol, limit=limit, offset=offset
        )
    except TradingDomainError as exc:
        raise _domain_http(exc) from exc


@router.post(
    "/paper/account",
    response_model=PaperAccountRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_paper_account(
    payload: PaperAccountCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await _limit_mutation(current_user.id, "create-account")
    try:
        return await service.create_paper_account(
            session, user_id=current_user.id, payload=payload
        )
    except TradingDomainError as exc:
        raise _domain_http(exc) from exc


@router.get("/paper/account", response_model=PaperAccountRead)
async def paper_account(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    try:
        return await service.get_paper_account(session, user_id=current_user.id)
    except TradingDomainError as exc:
        raise _domain_http(exc) from exc


@router.get("/paper/orders", response_model=TradingListResponse)
async def paper_orders(
    order_status: str | None = Query(default=None, alias="status", max_length=20),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    try:
        return await service.list_paper_orders(
            session,
            user_id=current_user.id,
            status=order_status,
            limit=limit,
            offset=offset,
        )
    except TradingDomainError as exc:
        raise _domain_http(exc) from exc


@router.post(
    "/paper/orders", response_model=PaperOrderRead, status_code=status.HTTP_201_CREATED
)
async def create_paper_order(
    payload: PaperOrderCreate,
    household_id: int = Query(gt=0),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await _limit_mutation(current_user.id, "create-order")
    try:
        return await service.create_order(
            session,
            user_id=current_user.id,
            household_id=household_id,
            payload=payload,
        )
    except (TradingDomainError, FinancialStateDomainError) as exc:
        raise _domain_http(exc) from exc


@router.post("/paper/orders/{order_id}/cancel", response_model=PaperOrderRead)
async def cancel_paper_order(
    order_id: int,
    payload: IdempotentAction,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await _limit_mutation(current_user.id, "cancel-order")
    try:
        return await service.cancel_order(
            session, user_id=current_user.id, order_id=order_id, payload=payload
        )
    except TradingDomainError as exc:
        raise _domain_http(exc) from exc


@router.get("/paper/positions", response_model=TradingListResponse)
async def paper_positions(
    position_status: str | None = Query(default=None, alias="status", max_length=20),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    try:
        return await service.list_paper_positions(
            session,
            user_id=current_user.id,
            status=position_status,
            limit=limit,
            offset=offset,
        )
    except TradingDomainError as exc:
        raise _domain_http(exc) from exc


@router.post("/paper/positions/{position_id}/close", response_model=PaperPositionRead)
async def close_paper_position(
    position_id: int,
    payload: IdempotentAction,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await _limit_mutation(current_user.id, "close-position")
    try:
        return await service.close_position(
            session,
            user_id=current_user.id,
            position_id=position_id,
            payload=payload,
        )
    except TradingDomainError as exc:
        raise _domain_http(exc) from exc


@router.get("/paper/events", response_model=TradingListResponse)
async def paper_events(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    try:
        return await service.list_paper_events(
            session, user_id=current_user.id, limit=limit, offset=offset
        )
    except TradingDomainError as exc:
        raise _domain_http(exc) from exc


@router.get("/backtests", response_model=TradingListResponse)
async def trading_backtests(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    try:
        return await service.list_backtests(session, limit=limit, offset=offset)
    except TradingDomainError as exc:
        raise _domain_http(exc) from exc


@router.get("/backtests/{backtest_id}", response_model=TradingBacktestRead)
async def trading_backtest(
    backtest_id: int,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    try:
        return await service.get_backtest(session, backtest_id=backtest_id)
    except TradingDomainError as exc:
        raise _domain_http(exc) from exc


@router.get("/models", response_model=TradingListResponse)
async def trading_models(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _: User = Depends(get_current_user),
):
    try:
        return await service.list_models(limit=limit, offset=offset)
    except TradingDomainError as exc:
        raise _domain_http(exc) from exc


@router.get("/models/{model_id}", response_model=TradingModelRead)
async def trading_model(
    model_id: str,
    _: User = Depends(get_current_user),
):
    try:
        return await service.get_model(model_id=model_id)
    except TradingDomainError as exc:
        raise _domain_http(exc) from exc


@router.get("/health", response_model=TradingHealthRead)
async def trading_health(
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    try:
        return await service.health(session)
    except TradingDomainError as exc:
        raise _domain_http(exc) from exc
