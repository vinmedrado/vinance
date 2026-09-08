from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth.dependencies import get_current_user
from backend.app.auth.models import User
from backend.app.core.database import get_session
from backend.app.financial.models import Expense, Income
from backend.app.financial_state import service
from backend.app.financial_state.models import FinancialGoal, FinancialLiability, OwnedAsset
from backend.app.financial_state.schemas import (
    AssetCreate,
    AssetRead,
    AssetUpdate,
    ExpenseCreate,
    ExpenseRead,
    ExpenseUpdate,
    FinancialStateHistory,
    FinancialStateRead,
    FinancialStateSnapshotRead,
    GoalCreate,
    GoalRead,
    GoalUpdate,
    HouseholdCreate,
    HouseholdMemberCreate,
    HouseholdMemberRead,
    HouseholdMemberUpdate,
    HouseholdRead,
    HouseholdUpdate,
    IncomeCreate,
    IncomeRead,
    IncomeUpdate,
    LiabilityCreate,
    LiabilityRead,
    LiabilityUpdate,
)


router = APIRouter(prefix="/financial", tags=["household-financial-state"])


def _private(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"


def _http_error(exc: service.FinancialStateDomainError) -> HTTPException:
    if isinstance(exc, (service.HouseholdNotFoundError, service.FinancialResourceNotFoundError)):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recurso financeiro não encontrado")
    if isinstance(exc, service.HouseholdPermissionError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso financeiro não autorizado")
    if isinstance(exc, service.HouseholdConflictError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if isinstance(exc, service.FinancialStateValidationError):
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc))
    return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Falha financeira")


async def _domain_call(function: Any, *args: Any, **kwargs: Any) -> Any:
    try:
        return await function(*args, **kwargs)
    except service.FinancialStateDomainError as exc:
        raise _http_error(exc) from exc


@router.get("/households", response_model=list[HouseholdRead])
async def households_list(
    response: Response,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    _private(response)
    return await service.list_households(session, user_id=current_user.id)


@router.get("/households/default", response_model=HouseholdRead)
async def household_default(
    response: Response,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    _private(response)
    return await _domain_call(service.get_default_household, session, user_id=current_user.id)


@router.post("/households", response_model=HouseholdRead, status_code=status.HTTP_201_CREATED)
async def household_create(
    payload: HouseholdCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await _domain_call(
        service.create_household,
        session,
        user_id=current_user.id,
        payload=payload,
    )


@router.get("/households/{household_id}", response_model=HouseholdRead)
async def household_detail(
    response: Response,
    household_id: int = Path(ge=1),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    _private(response)
    household, _ = await _domain_call(
        service.get_household_access,
        session,
        household_id=household_id,
        user_id=current_user.id,
    )
    return household


@router.patch("/households/{household_id}", response_model=HouseholdRead)
async def household_update(
    payload: HouseholdUpdate,
    household_id: int = Path(ge=1),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await _domain_call(
        service.update_household,
        session,
        household_id=household_id,
        user_id=current_user.id,
        payload=payload,
    )


@router.get("/households/{household_id}/members", response_model=list[HouseholdMemberRead])
async def household_members_list(
    response: Response,
    household_id: int = Path(ge=1),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    _private(response)
    return await _domain_call(
        service.list_members,
        session,
        household_id=household_id,
        user_id=current_user.id,
    )


@router.post(
    "/households/{household_id}/members",
    response_model=HouseholdMemberRead,
    status_code=status.HTTP_201_CREATED,
)
async def household_member_add(
    payload: HouseholdMemberCreate,
    household_id: int = Path(ge=1),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await _domain_call(
        service.add_member,
        session,
        household_id=household_id,
        user_id=current_user.id,
        payload=payload,
    )


@router.patch(
    "/households/{household_id}/members/{member_id}",
    response_model=HouseholdMemberRead,
)
async def household_member_update(
    payload: HouseholdMemberUpdate,
    household_id: int = Path(ge=1),
    member_id: int = Path(ge=1),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await _domain_call(
        service.update_member,
        session,
        household_id=household_id,
        member_id=member_id,
        user_id=current_user.id,
        payload=payload,
    )


@router.delete(
    "/households/{household_id}/members/{member_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def household_member_remove(
    household_id: int = Path(ge=1),
    member_id: int = Path(ge=1),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await _domain_call(
        service.remove_member,
        session,
        household_id=household_id,
        member_id=member_id,
        user_id=current_user.id,
    )


@router.get("/households/{household_id}/incomes", response_model=list[IncomeRead])
async def incomes_list(
    response: Response,
    household_id: int = Path(ge=1),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    _private(response)
    return await _domain_call(
        service.list_resources,
        session,
        Income,
        household_id=household_id,
        user_id=current_user.id,
    )


@router.post(
    "/households/{household_id}/incomes",
    response_model=IncomeRead,
    status_code=status.HTTP_201_CREATED,
)
async def income_create(
    payload: IncomeCreate,
    household_id: int = Path(ge=1),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await _domain_call(
        service.create_resource,
        session,
        Income,
        household_id=household_id,
        user_id=current_user.id,
        payload=payload,
    )


@router.get("/households/{household_id}/incomes/{record_id}", response_model=IncomeRead)
async def income_detail(
    response: Response,
    household_id: int = Path(ge=1),
    record_id: int = Path(ge=1),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    _private(response)
    return await _domain_call(
        service.get_resource,
        session,
        Income,
        household_id=household_id,
        record_id=record_id,
        user_id=current_user.id,
    )


@router.patch("/households/{household_id}/incomes/{record_id}", response_model=IncomeRead)
async def income_update(
    payload: IncomeUpdate,
    household_id: int = Path(ge=1),
    record_id: int = Path(ge=1),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await _domain_call(
        service.update_resource,
        session,
        Income,
        household_id=household_id,
        record_id=record_id,
        user_id=current_user.id,
        payload=payload,
    )


@router.delete(
    "/households/{household_id}/incomes/{record_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def income_delete(
    household_id: int = Path(ge=1),
    record_id: int = Path(ge=1),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await _domain_call(
        service.delete_resource,
        session,
        Income,
        household_id=household_id,
        record_id=record_id,
        user_id=current_user.id,
    )


@router.get("/households/{household_id}/expenses", response_model=list[ExpenseRead])
async def expenses_list(
    response: Response,
    household_id: int = Path(ge=1),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    _private(response)
    return await _domain_call(
        service.list_resources,
        session,
        Expense,
        household_id=household_id,
        user_id=current_user.id,
    )


@router.post(
    "/households/{household_id}/expenses",
    response_model=ExpenseRead,
    status_code=status.HTTP_201_CREATED,
)
async def expense_create(
    payload: ExpenseCreate,
    household_id: int = Path(ge=1),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await _domain_call(
        service.create_resource,
        session,
        Expense,
        household_id=household_id,
        user_id=current_user.id,
        payload=payload,
    )


@router.get("/households/{household_id}/expenses/{record_id}", response_model=ExpenseRead)
async def expense_detail(
    response: Response,
    household_id: int = Path(ge=1),
    record_id: int = Path(ge=1),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    _private(response)
    return await _domain_call(
        service.get_resource,
        session,
        Expense,
        household_id=household_id,
        record_id=record_id,
        user_id=current_user.id,
    )


@router.patch("/households/{household_id}/expenses/{record_id}", response_model=ExpenseRead)
async def expense_update(
    payload: ExpenseUpdate,
    household_id: int = Path(ge=1),
    record_id: int = Path(ge=1),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await _domain_call(
        service.update_resource,
        session,
        Expense,
        household_id=household_id,
        record_id=record_id,
        user_id=current_user.id,
        payload=payload,
    )


@router.delete(
    "/households/{household_id}/expenses/{record_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def expense_delete(
    household_id: int = Path(ge=1),
    record_id: int = Path(ge=1),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await _domain_call(
        service.delete_resource,
        session,
        Expense,
        household_id=household_id,
        record_id=record_id,
        user_id=current_user.id,
    )


@router.get("/households/{household_id}/debts", response_model=list[LiabilityRead])
async def debts_list(
    response: Response,
    household_id: int = Path(ge=1),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    _private(response)
    return await _domain_call(
        service.list_resources,
        session,
        FinancialLiability,
        household_id=household_id,
        user_id=current_user.id,
    )


@router.post(
    "/households/{household_id}/debts",
    response_model=LiabilityRead,
    status_code=status.HTTP_201_CREATED,
)
async def debt_create(
    payload: LiabilityCreate,
    household_id: int = Path(ge=1),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await _domain_call(
        service.create_resource,
        session,
        FinancialLiability,
        household_id=household_id,
        user_id=current_user.id,
        payload=payload,
    )


@router.get("/households/{household_id}/debts/{record_id}", response_model=LiabilityRead)
async def debt_detail(
    response: Response,
    household_id: int = Path(ge=1),
    record_id: int = Path(ge=1),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    _private(response)
    return await _domain_call(
        service.get_resource,
        session,
        FinancialLiability,
        household_id=household_id,
        record_id=record_id,
        user_id=current_user.id,
    )


@router.patch("/households/{household_id}/debts/{record_id}", response_model=LiabilityRead)
async def debt_update(
    payload: LiabilityUpdate,
    household_id: int = Path(ge=1),
    record_id: int = Path(ge=1),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await _domain_call(
        service.update_resource,
        session,
        FinancialLiability,
        household_id=household_id,
        record_id=record_id,
        user_id=current_user.id,
        payload=payload,
    )


@router.delete(
    "/households/{household_id}/debts/{record_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def debt_delete(
    household_id: int = Path(ge=1),
    record_id: int = Path(ge=1),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await _domain_call(
        service.delete_resource,
        session,
        FinancialLiability,
        household_id=household_id,
        record_id=record_id,
        user_id=current_user.id,
    )


@router.get("/households/{household_id}/assets", response_model=list[AssetRead])
async def assets_list(
    response: Response,
    household_id: int = Path(ge=1),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    _private(response)
    return await _domain_call(
        service.list_resources,
        session,
        OwnedAsset,
        household_id=household_id,
        user_id=current_user.id,
    )


@router.post(
    "/households/{household_id}/assets",
    response_model=AssetRead,
    status_code=status.HTTP_201_CREATED,
)
async def asset_create(
    payload: AssetCreate,
    household_id: int = Path(ge=1),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await _domain_call(
        service.create_resource,
        session,
        OwnedAsset,
        household_id=household_id,
        user_id=current_user.id,
        payload=payload,
    )


@router.get("/households/{household_id}/assets/{record_id}", response_model=AssetRead)
async def asset_detail(
    response: Response,
    household_id: int = Path(ge=1),
    record_id: int = Path(ge=1),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    _private(response)
    return await _domain_call(
        service.get_resource,
        session,
        OwnedAsset,
        household_id=household_id,
        record_id=record_id,
        user_id=current_user.id,
    )


@router.patch("/households/{household_id}/assets/{record_id}", response_model=AssetRead)
async def asset_update(
    payload: AssetUpdate,
    household_id: int = Path(ge=1),
    record_id: int = Path(ge=1),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await _domain_call(
        service.update_resource,
        session,
        OwnedAsset,
        household_id=household_id,
        record_id=record_id,
        user_id=current_user.id,
        payload=payload,
    )


@router.delete(
    "/households/{household_id}/assets/{record_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def asset_delete(
    household_id: int = Path(ge=1),
    record_id: int = Path(ge=1),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await _domain_call(
        service.delete_resource,
        session,
        OwnedAsset,
        household_id=household_id,
        record_id=record_id,
        user_id=current_user.id,
    )


@router.get("/households/{household_id}/goals", response_model=list[GoalRead])
async def goals_list(
    response: Response,
    household_id: int = Path(ge=1),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    _private(response)
    return await _domain_call(
        service.list_resources,
        session,
        FinancialGoal,
        household_id=household_id,
        user_id=current_user.id,
    )


@router.post(
    "/households/{household_id}/goals",
    response_model=GoalRead,
    status_code=status.HTTP_201_CREATED,
)
async def goal_create(
    payload: GoalCreate,
    household_id: int = Path(ge=1),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await _domain_call(
        service.create_resource,
        session,
        FinancialGoal,
        household_id=household_id,
        user_id=current_user.id,
        payload=payload,
    )


@router.get("/households/{household_id}/goals/{record_id}", response_model=GoalRead)
async def goal_detail(
    response: Response,
    household_id: int = Path(ge=1),
    record_id: int = Path(ge=1),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    _private(response)
    return await _domain_call(
        service.get_resource,
        session,
        FinancialGoal,
        household_id=household_id,
        record_id=record_id,
        user_id=current_user.id,
    )


@router.patch("/households/{household_id}/goals/{record_id}", response_model=GoalRead)
async def goal_update(
    payload: GoalUpdate,
    household_id: int = Path(ge=1),
    record_id: int = Path(ge=1),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await _domain_call(
        service.update_resource,
        session,
        FinancialGoal,
        household_id=household_id,
        record_id=record_id,
        user_id=current_user.id,
        payload=payload,
    )


@router.delete(
    "/households/{household_id}/goals/{record_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def goal_delete(
    household_id: int = Path(ge=1),
    record_id: int = Path(ge=1),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await _domain_call(
        service.delete_resource,
        session,
        FinancialGoal,
        household_id=household_id,
        record_id=record_id,
        user_id=current_user.id,
    )


@router.get("/households/{household_id}/financial-state", response_model=FinancialStateRead)
async def financial_state_current(
    response: Response,
    household_id: int = Path(ge=1),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    _private(response)
    return await _domain_call(
        service.current_financial_state,
        session,
        household_id=household_id,
        user_id=current_user.id,
    )


@router.post(
    "/households/{household_id}/financial-state/snapshots",
    response_model=FinancialStateSnapshotRead,
    status_code=status.HTTP_201_CREATED,
)
async def financial_state_snapshot_create(
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
    return await _domain_call(
        service.create_snapshot,
        session,
        household_id=household_id,
        user_id=current_user.id,
        idempotency_key=idempotency_key,
    )


@router.get(
    "/households/{household_id}/financial-state/history",
    response_model=FinancialStateHistory,
)
async def financial_state_history(
    response: Response,
    household_id: int = Path(ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    _private(response)
    return await _domain_call(
        service.snapshot_history,
        session,
        household_id=household_id,
        user_id=current_user.id,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/households/{household_id}/financial-state/history/{snapshot_id}",
    response_model=FinancialStateSnapshotRead,
)
async def financial_state_snapshot_detail(
    response: Response,
    household_id: int = Path(ge=1),
    snapshot_id: int = Path(ge=1),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    _private(response)
    return await _domain_call(
        service.get_snapshot,
        session,
        household_id=household_id,
        snapshot_id=snapshot_id,
        user_id=current_user.id,
    )
