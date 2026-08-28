from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.auth.dependencies import get_current_user
from backend.app.auth.models import User
from backend.app.core.database import get_session
from backend.app.financial import service
from backend.app.financial.schemas import (
    ExpenseCreate,
    ExpenseRead,
    FinancialDiagnosisRead,
    FinancialProfileCreate,
    FinancialProfileRead,
    IncomeCreate,
    IncomeRead,
)

router = APIRouter(prefix="/financial", tags=["financial"])


@router.post("/incomes", response_model=IncomeRead, status_code=status.HTTP_201_CREATED)
async def create_income(
    payload: IncomeCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await service.create_income(session, user_id=current_user.id, payload=payload)


@router.get("/incomes", response_model=list[IncomeRead])
async def list_incomes(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await service.list_incomes(session, user_id=current_user.id)


@router.post("/expenses", response_model=ExpenseRead, status_code=status.HTTP_201_CREATED)
async def create_expense(
    payload: ExpenseCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await service.create_expense(session, user_id=current_user.id, payload=payload)


@router.get("/expenses", response_model=list[ExpenseRead])
async def list_expenses(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await service.list_expenses(session, user_id=current_user.id)


@router.post("/profile", response_model=FinancialProfileRead, status_code=status.HTTP_201_CREATED)
async def upsert_profile(
    payload: FinancialProfileCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    return await service.upsert_financial_profile(session, user_id=current_user.id, payload=payload)


@router.get("/profile", response_model=FinancialProfileRead)
async def get_profile(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    profile = await service.get_financial_profile(session, user_id=current_user.id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Financial profile not found")
    return profile


@router.get("/diagnosis", response_model=FinancialDiagnosisRead)
async def get_diagnosis(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    try:
        return await service.calculate_financial_diagnosis(session, user_id=current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
