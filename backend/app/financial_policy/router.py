from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Path, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth.dependencies import get_current_user
from backend.app.auth.models import User
from backend.app.core.database import get_session
from backend.app.financial_policy import service
from backend.app.financial_policy.schemas import FinancialPolicyRead
from backend.app.financial_state import service as state_service


router = APIRouter(prefix="/financial", tags=["financial-policy"])


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
        detail="Falha na política financeira",
    )


async def _domain_call(function: Any, *args: Any, **kwargs: Any) -> Any:
    try:
        return await function(*args, **kwargs)
    except state_service.FinancialStateDomainError as exc:
        raise _http_error(exc) from exc


@router.get(
    "/households/{household_id}/financial-policy",
    response_model=FinancialPolicyRead,
)
async def financial_policy_current(
    response: Response,
    household_id: int = Path(ge=1),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    _private(response)
    return await _domain_call(
        service.current_financial_policy,
        session,
        household_id=household_id,
        user_id=current_user.id,
    )


@router.get(
    "/households/{household_id}/financial-policy/from-state-snapshot/{snapshot_id}",
    response_model=FinancialPolicyRead,
)
async def financial_policy_replay(
    response: Response,
    household_id: int = Path(ge=1),
    snapshot_id: int = Path(ge=1),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    _private(response)
    return await _domain_call(
        service.financial_policy_from_state_snapshot,
        session,
        household_id=household_id,
        snapshot_id=snapshot_id,
        user_id=current_user.id,
    )
