from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth.dependencies import get_current_user
from backend.app.auth.models import User
from backend.app.core.database import get_session
from backend.app.financial_state import service as state_service
from backend.app.investment_orchestrator import service
from backend.app.investment_orchestrator.schemas import (
    InvestmentOrchestrationHistory,
    InvestmentOrchestrationRead,
)


router = APIRouter(prefix="/financial", tags=["investment-orchestration"])


def _private(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"


def _http_error(exc: state_service.FinancialStateDomainError) -> HTTPException:
    if isinstance(
        exc,
        (
            state_service.HouseholdNotFoundError,
            state_service.FinancialResourceNotFoundError,
        ),
    ):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recurso financeiro não encontrado",
        )
    if isinstance(exc, state_service.HouseholdPermissionError):
        return HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso financeiro não autorizado",
        )
    if isinstance(exc, state_service.FinancialStateValidationError):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        )
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Falha na estratégia de investimento",
    )


async def _domain_call(function: Any, *args: Any, **kwargs: Any) -> Any:
    try:
        return await function(*args, **kwargs)
    except state_service.FinancialStateDomainError as exc:
        raise _http_error(exc) from exc


@router.get(
    "/households/{household_id}/investment-orchestration",
    response_model=InvestmentOrchestrationRead,
)
async def investment_orchestration_current(
    response: Response,
    household_id: int = Path(ge=1),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    _private(response)
    return await _domain_call(
        service.current_investment_orchestration,
        session,
        household_id=household_id,
        user_id=current_user.id,
    )


@router.get(
    "/households/{household_id}/investment-orchestration/from-allocation/{allocation_id}",
    response_model=InvestmentOrchestrationRead,
)
async def investment_orchestration_from_allocation(
    response: Response,
    household_id: int = Path(ge=1),
    allocation_id: int = Path(ge=1),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    _private(response)
    return await _domain_call(
        service.investment_orchestration_from_allocation_decision,
        session,
        household_id=household_id,
        allocation_id=allocation_id,
        user_id=current_user.id,
    )


@router.post(
    "/households/{household_id}/investment-orchestration/decisions",
    response_model=InvestmentOrchestrationRead,
    status_code=status.HTTP_201_CREATED,
)
async def investment_orchestration_decision_create(
    response: Response,
    household_id: int = Path(ge=1),
    idempotency_key: str | None = Header(
        default=None,
        alias="Idempotency-Key",
        min_length=1,
        max_length=128,
    ),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    _private(response)
    return await _domain_call(
        service.create_investment_orchestration_decision,
        session,
        household_id=household_id,
        user_id=current_user.id,
        idempotency_key=idempotency_key,
    )


@router.get(
    "/households/{household_id}/investment-orchestration/history",
    response_model=InvestmentOrchestrationHistory,
)
async def investment_orchestration_history(
    response: Response,
    household_id: int = Path(ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    _private(response)
    return await _domain_call(
        service.investment_orchestration_history,
        session,
        household_id=household_id,
        user_id=current_user.id,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/households/{household_id}/investment-orchestration/history/{orchestration_id}",
    response_model=InvestmentOrchestrationRead,
)
async def investment_orchestration_decision_detail(
    response: Response,
    household_id: int = Path(ge=1),
    orchestration_id: int = Path(ge=1),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    _private(response)
    return await _domain_call(
        service.get_investment_orchestration_decision,
        session,
        household_id=household_id,
        orchestration_id=orchestration_id,
        user_id=current_user.id,
    )
