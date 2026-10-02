from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth.dependencies import get_current_user
from backend.app.auth.models import User
from backend.app.continuous_autopilot import service
from backend.app.continuous_autopilot.schemas import (
    ContinuousAutopilotHistory,
    ContinuousAutopilotRead,
    ContinuousEvaluationRequest,
)
from backend.app.core.database import get_session
from backend.app.financial_state import service as state_service


router = APIRouter(prefix="/financial", tags=["continuous-autopilot"])


def _private(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"


def _http_error(exc: state_service.FinancialStateDomainError) -> HTTPException:
    if isinstance(exc, service.ContinuousAutopilotConflictError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Idempotency-Key já utilizado por outra avaliação",
            headers={"Cache-Control": "private, no-store"},
        )
    if isinstance(exc, service.ContinuousAutopilotCooldownError):
        return HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Aguarde antes de repetir uma avaliação que falhou",
            headers={
                "Cache-Control": "private, no-store",
                "Retry-After": str(exc.retry_after),
            },
        )
    if isinstance(exc, service.ContinuousAutopilotUnavailableError):
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="A avaliação está temporariamente indisponível",
            headers={"Cache-Control": "private, no-store", "Retry-After": "30"},
        )
    if isinstance(
        exc,
        (
            state_service.HouseholdNotFoundError,
            state_service.HouseholdPermissionError,
            state_service.FinancialResourceNotFoundError,
        ),
    ):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recurso financeiro não encontrado",
            headers={"Cache-Control": "private, no-store"},
        )
    if isinstance(exc, state_service.FinancialStateValidationError):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
            headers={"Cache-Control": "private, no-store"},
        )
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Falha ao avaliar o Autopilot",
        headers={"Cache-Control": "private, no-store"},
    )


async def _domain_call(function: Any, *args: Any, **kwargs: Any) -> Any:
    try:
        return await function(*args, **kwargs)
    except state_service.FinancialStateDomainError as exc:
        raise _http_error(exc) from exc


@router.get(
    "/households/{household_id}/continuous-autopilot",
    response_model=ContinuousAutopilotRead,
)
async def continuous_autopilot_current(
    response: Response,
    household_id: int = Path(ge=1),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    _private(response)
    return await _domain_call(
        service.current_continuous_autopilot,
        session,
        household_id=household_id,
        user_id=current_user.id,
    )


@router.post(
    "/households/{household_id}/continuous-autopilot/evaluate",
    response_model=ContinuousAutopilotRead,
)
async def continuous_autopilot_evaluate(
    response: Response,
    payload: ContinuousEvaluationRequest | None = None,
    household_id: int = Path(ge=1),
    idempotency_key: str = Header(
        alias="Idempotency-Key", min_length=1, max_length=128
    ),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    _private(response)
    if idempotency_key.startswith("continuous-scheduled:"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Idempotency-Key utiliza namespace reservado",
            headers={"Cache-Control": "private, no-store"},
        )
    return await _domain_call(
        service.evaluate_continuous_autopilot,
        session,
        household_id=household_id,
        user_id=current_user.id,
        idempotency_key=idempotency_key,
    )


@router.get(
    "/households/{household_id}/continuous-autopilot/history",
    response_model=ContinuousAutopilotHistory,
)
async def continuous_autopilot_history(
    response: Response,
    household_id: int = Path(ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    _private(response)
    return await _domain_call(
        service.continuous_autopilot_history,
        session,
        household_id=household_id,
        user_id=current_user.id,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/households/{household_id}/continuous-autopilot/history/{continuous_decision_id}",
    response_model=ContinuousAutopilotRead,
)
async def continuous_autopilot_detail(
    response: Response,
    household_id: int = Path(ge=1),
    continuous_decision_id: int = Path(ge=1),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    _private(response)
    return await _domain_call(
        service.get_continuous_autopilot_decision,
        session,
        household_id=household_id,
        continuous_decision_id=continuous_decision_id,
        user_id=current_user.id,
    )
