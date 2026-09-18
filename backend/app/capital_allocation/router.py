from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth.dependencies import get_current_user
from backend.app.auth.models import User
from backend.app.capital_allocation import service
from backend.app.capital_allocation.schemas import (
    CapitalAllocationHistory,
    CapitalAllocationRead,
)
from backend.app.core.database import get_session
from backend.app.financial_state import service as state_service


router = APIRouter(prefix="/financial", tags=["capital-allocation"])


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
        detail="Falha no plano de capital",
    )


async def _domain_call(function: Any, *args: Any, **kwargs: Any) -> Any:
    try:
        return await function(*args, **kwargs)
    except state_service.FinancialStateDomainError as exc:
        raise _http_error(exc) from exc


@router.get(
    "/households/{household_id}/capital-allocation",
    response_model=CapitalAllocationRead,
)
async def capital_allocation_current(
    response: Response,
    household_id: int = Path(ge=1),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    _private(response)
    return await _domain_call(
        service.current_capital_allocation,
        session,
        household_id=household_id,
        user_id=current_user.id,
    )


@router.get(
    "/households/{household_id}/capital-allocation/from-policy/{policy_id}",
    response_model=CapitalAllocationRead,
)
async def capital_allocation_from_policy(
    response: Response,
    household_id: int = Path(ge=1),
    policy_id: int = Path(ge=1),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    _private(response)
    return await _domain_call(
        service.capital_allocation_from_policy_decision,
        session,
        household_id=household_id,
        policy_id=policy_id,
        user_id=current_user.id,
    )


@router.post(
    "/households/{household_id}/capital-allocation/decisions",
    response_model=CapitalAllocationRead,
    status_code=status.HTTP_201_CREATED,
)
async def capital_allocation_decision_create(
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
        service.create_capital_allocation_decision,
        session,
        household_id=household_id,
        user_id=current_user.id,
        idempotency_key=idempotency_key,
    )


@router.get(
    "/households/{household_id}/capital-allocation/history",
    response_model=CapitalAllocationHistory,
)
async def capital_allocation_history(
    response: Response,
    household_id: int = Path(ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    _private(response)
    return await _domain_call(
        service.capital_allocation_history,
        session,
        household_id=household_id,
        user_id=current_user.id,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/households/{household_id}/capital-allocation/history/{allocation_id}",
    response_model=CapitalAllocationRead,
)
async def capital_allocation_decision_detail(
    response: Response,
    household_id: int = Path(ge=1),
    allocation_id: int = Path(ge=1),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    _private(response)
    return await _domain_call(
        service.get_capital_allocation_decision,
        session,
        household_id=household_id,
        allocation_id=allocation_id,
        user_id=current_user.id,
    )
