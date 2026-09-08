from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.financial.budget_engine import calculate_budget_strategy
from backend.app.financial.models import Expense, FinancialProfile, Income
from backend.app.financial.schemas import ExpenseCreate, FinancialProfileCreate, IncomeCreate
from backend.app.financial.scoring import calculate_financial_score
from backend.app.financial_state.service import get_default_household


async def create_income(session: AsyncSession, *, user_id: int, payload: IncomeCreate) -> Income:
    household = await get_default_household(session, user_id=user_id)
    income = Income(
        user_id=user_id,
        household_id=household.id,
        ownership_scope="PERSONAL",
        **payload.model_dump(),
    )
    session.add(income)
    await session.commit()
    await session.refresh(income)
    return income


async def list_incomes(session: AsyncSession, *, user_id: int) -> list[Income]:
    household = await get_default_household(session, user_id=user_id)
    result = await session.execute(
        select(Income)
        .where(
            Income.user_id == user_id,
            Income.household_id == household.id,
            Income.ownership_scope == "PERSONAL",
        )
        .order_by(Income.received_at.desc(), Income.id.desc())
    )
    return list(result.scalars().all())


async def create_expense(session: AsyncSession, *, user_id: int, payload: ExpenseCreate) -> Expense:
    household = await get_default_household(session, user_id=user_id)
    expense = Expense(
        user_id=user_id,
        household_id=household.id,
        ownership_scope="PERSONAL",
        expense_nature=None,
        **payload.model_dump(),
    )
    session.add(expense)
    await session.commit()
    await session.refresh(expense)
    return expense


async def list_expenses(session: AsyncSession, *, user_id: int) -> list[Expense]:
    household = await get_default_household(session, user_id=user_id)
    result = await session.execute(
        select(Expense)
        .where(
            Expense.user_id == user_id,
            Expense.household_id == household.id,
            Expense.ownership_scope == "PERSONAL",
        )
        .order_by(Expense.due_date.asc(), Expense.id.desc())
    )
    return list(result.scalars().all())


async def upsert_financial_profile(
    session: AsyncSession,
    *,
    user_id: int,
    payload: FinancialProfileCreate,
) -> FinancialProfile:
    profile = await get_financial_profile(session, user_id=user_id)
    values = payload.model_dump()
    if profile is None:
        profile = FinancialProfile(user_id=user_id, **values)
        session.add(profile)
    else:
        for field, value in values.items():
            setattr(profile, field, value)
    await session.commit()
    await session.refresh(profile)
    return profile


async def get_financial_profile(session: AsyncSession, *, user_id: int) -> FinancialProfile | None:
    result = await session.execute(select(FinancialProfile).where(FinancialProfile.user_id == user_id))
    return result.scalar_one_or_none()


async def _sum_user_expenses_30d(session: AsyncSession, *, user_id: int, today: date | None = None) -> Decimal:
    start = today or date.today()
    end = start + timedelta(days=30)
    result = await session.execute(
        select(func.coalesce(func.sum(Expense.amount), 0)).where(
            Expense.user_id == user_id,
            Expense.due_date >= start,
            Expense.due_date <= end,
        )
    )
    return Decimal(str(result.scalar_one() or 0))


async def calculate_financial_diagnosis(session: AsyncSession, *, user_id: int) -> dict:
    profile = await get_financial_profile(session, user_id=user_id)
    if profile is None:
        raise ValueError("Financial profile is required before diagnosis")

    total_expenses_30d = await _sum_user_expenses_30d(session, user_id=user_id)
    score = calculate_financial_score(
        monthly_salary=profile.monthly_salary,
        total_expenses_30d=total_expenses_30d,
        emergency_reserve=profile.emergency_reserve,
        has_debt_default=profile.has_debt_default,
    )
    budget = calculate_budget_strategy(
        monthly_salary=profile.monthly_salary,
        total_expenses_30d=total_expenses_30d,
        emergency_reserve=profile.emergency_reserve,
        has_debt_default=profile.has_debt_default,
        financial_score=score["score"],
    )
    return {
        "monthly_salary": profile.monthly_salary,
        "total_expenses_30d": total_expenses_30d,
        "emergency_reserve": profile.emergency_reserve,
        "has_debt_default": profile.has_debt_default,
        "risk_profile": profile.risk_profile,
        "score": score,
        "budget": budget,
    }
