from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.action_plan import service
from backend.app.action_plan.schemas import ActionPlanHistory, ActionPlanRead
from backend.app.auth.dependencies import get_current_user
from backend.app.auth.models import User
from backend.app.core.database import get_session
from backend.app.financial_state import service as state_service


router = APIRouter(prefix="/financial", tags=["action-plan"])


def _private(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"


def _http_error(exc: state_service.FinancialStateDomainError) -> HTTPException:
    if isinstance(
        exc,
        (
            state_service.HouseholdNotFoundError,
            state_service.FinancialResourceNotFoundError,
            state_service.HouseholdPermissionError,
        ),
    ):
        # A defensive 404 does not reveal whether another household/resource exists.
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
        detail="Falha ao montar o plano de ação",
        headers={"Cache-Control": "private, no-store"},
    )


async def _domain_call(function: Any, *args: Any, **kwargs: Any) -> Any:
    try:
        return await function(*args, **kwargs)
    except state_service.FinancialStateDomainError as exc:
        raise _http_error(exc) from exc


@router.get(
    "/households/{household_id}/action-plan",
    response_model=ActionPlanRead,
)
async def action_plan_current(
    response: Response,
    household_id: int = Path(ge=1),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    _private(response)
    return await _domain_call(
        service.current_action_plan,
        session,
        household_id=household_id,
        user_id=current_user.id,
    )


@router.get(
    "/households/{household_id}/action-plan/from-orchestration/{orchestration_id}",
    response_model=ActionPlanRead,
)
async def action_plan_from_orchestration(
    response: Response,
    household_id: int = Path(ge=1),
    orchestration_id: int = Path(ge=1),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    _private(response)
    return await _domain_call(
        service.action_plan_from_orchestration_decision,
        session,
        household_id=household_id,
        orchestration_id=orchestration_id,
        user_id=current_user.id,
    )


@router.post(
    "/households/{household_id}/action-plan/decisions",
    response_model=ActionPlanRead,
    status_code=status.HTTP_201_CREATED,
)
async def action_plan_decision_create(
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
        service.create_action_plan_decision,
        session,
        household_id=household_id,
        user_id=current_user.id,
        idempotency_key=idempotency_key,
    )


@router.get(
    "/households/{household_id}/action-plan/history",
    response_model=ActionPlanHistory,
)
async def action_plan_history(
    response: Response,
    household_id: int = Path(ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    _private(response)
    return await _domain_call(
        service.action_plan_history,
        session,
        household_id=household_id,
        user_id=current_user.id,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/households/{household_id}/action-plan/history/{action_plan_id}",
    response_model=ActionPlanRead,
)
async def action_plan_decision_detail(
    response: Response,
    household_id: int = Path(ge=1),
    action_plan_id: int = Path(ge=1),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    _private(response)
    return await _domain_call(
        service.get_action_plan_decision,
        session,
        household_id=household_id,
        action_plan_id=action_plan_id,
        user_id=current_user.id,
    )
