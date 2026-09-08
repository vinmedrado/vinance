from __future__ import annotations

import os
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from backend.app.auth.models import User
from backend.app.auth.schemas import UserCreate
from backend.app.auth import service as auth_service
from backend.app.financial import service as legacy_financial_service
from backend.app.financial.models import Expense, Income
from backend.app.financial.schemas import (
    ExpenseCreate as LegacyExpenseCreate,
    IncomeCreate as LegacyIncomeCreate,
)
from backend.app.financial_state import service
from backend.app.financial_state.models import (
    FinancialGoal,
    FinancialLiability,
    Household,
    HouseholdMember,
    OwnedAsset,
)
from backend.app.financial_state.schemas import (
    AssetCreate,
    ExpenseCreate,
    GoalCreate,
    HouseholdCreate,
    HouseholdMemberCreate,
    IncomeCreate,
    IncomeUpdate,
    LiabilityCreate,
)


TEST_DATABASE_URL = os.getenv("AUTOPILOT_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="set AUTOPILOT_TEST_DATABASE_URL to an isolated PostgreSQL database",
)
NOW = datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc)


async def _user_with_personal_household(
    session: AsyncSession,
    *,
    label: str,
) -> tuple[User, Household, HouseholdMember]:
    user = User(
        email=f"{label}-{uuid4()}@example.com".lower(),
        full_name=label,
        hashed_password="not-used",
        is_active=True,
    )
    session.add(user)
    await session.flush()
    household = Household(
        name=f"{label} — pessoal",
        household_type="PERSONAL",
        created_by_user_id=user.id,
        status="ACTIVE",
    )
    session.add(household)
    await session.flush()
    member = HouseholdMember(
        household_id=household.id,
        user_id=user.id,
        role="OWNER",
        status="ACTIVE",
        is_default=True,
    )
    session.add(member)
    await session.commit()
    await session.refresh(user)
    await session.refresh(household)
    await session.refresh(member)
    return user, household, member


@pytest.mark.asyncio
async def test_real_postgres_individual_couple_ownership_and_immutable_snapshots() -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.connect() as connection:
        outer = await connection.begin()
        session = AsyncSession(
            bind=connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        try:
            ana = await auth_service.create_user(
                session,
                UserCreate(
                    email=f"ana-{uuid4()}@example.com",
                    password="senha-segura",
                    full_name="Ana",
                ),
            )
            personal = await service.get_default_household(session, user_id=ana.id)
            _, ana_membership = await service.get_household_access(
                session, household_id=personal.id, user_id=ana.id
            )
            assert personal.household_type == "PERSONAL"
            assert ana_membership.role == "OWNER"
            assert ana_membership.is_default is True
            bia, _, _ = await _user_with_personal_household(session, label="Bia")
            outsider, outsider_personal, _ = await _user_with_personal_household(session, label="Fora")

            legacy_income = await legacy_financial_service.create_income(
                session,
                user_id=outsider.id,
                payload=LegacyIncomeCreate(
                    description="Compatibilidade",
                    amount=Decimal("100"),
                    income_type="other",
                    received_at=date(2026, 9, 8),
                    is_recurring=False,
                ),
            )
            legacy_expense = await legacy_financial_service.create_expense(
                session,
                user_id=outsider.id,
                payload=LegacyExpenseCreate(
                    description="Compatibilidade",
                    amount=Decimal("10"),
                    category="other",
                    due_date=date(2026, 9, 8),
                    is_paid=False,
                    is_recurring=False,
                ),
            )
            assert legacy_income.household_id == outsider_personal.id
            assert legacy_expense.household_id == outsider_personal.id
            assert legacy_expense.expense_nature is None
            assert len(
                await legacy_financial_service.list_incomes(session, user_id=outsider.id)
            ) == 1

            await service.create_resource(
                session,
                Income,
                household_id=personal.id,
                user_id=ana.id,
                payload=IncomeCreate(
                    description="Salário",
                    amount=Decimal("6000"),
                    income_type="salary",
                    received_at=date(2026, 9, 5),
                    is_recurring=True,
                    ownership_scope="PERSONAL",
                ),
            )
            await service.create_resource(
                session,
                Income,
                household_id=personal.id,
                user_id=ana.id,
                payload=IncomeCreate(
                    description="Sem renda extraordinária no mês",
                    amount=Decimal("0"),
                    income_type="declared_none",
                    received_at=date(2026, 9, 5),
                    is_recurring=False,
                    ownership_scope="PERSONAL",
                ),
            )
            for nature, amount in (("FIXED", "2000"), ("VARIABLE", "0")):
                await service.create_resource(
                    session,
                    Expense,
                    household_id=personal.id,
                    user_id=ana.id,
                    payload=ExpenseCreate(
                        description=f"Despesas {nature.lower()}",
                        amount=Decimal(amount),
                        category="declared",
                        due_date=date(2026, 9, 5),
                        is_recurring=True,
                        expense_nature=nature,
                        ownership_scope="PERSONAL",
                    ),
                )
            await service.create_resource(
                session,
                OwnedAsset,
                household_id=personal.id,
                user_id=ana.id,
                payload=AssetCreate(
                    ownership_scope="PERSONAL",
                    asset_class="EMERGENCY_RESERVE",
                    name="Reserva",
                    current_value=Decimal("6000"),
                    value_as_of=date(2026, 9, 8),
                ),
            )
            await service.create_resource(
                session,
                FinancialLiability,
                household_id=personal.id,
                user_id=ana.id,
                payload=LiabilityCreate(
                    ownership_scope="PERSONAL",
                    name="Empréstimo",
                    liability_type="loan",
                    current_balance=Decimal("2000"),
                    monthly_payment=Decimal("500"),
                    balance_as_of=date(2026, 9, 8),
                ),
            )
            await service.create_resource(
                session,
                FinancialGoal,
                household_id=personal.id,
                user_id=ana.id,
                payload=GoalCreate(
                    ownership_scope="PERSONAL",
                    name="Reserva ampliada",
                    target_amount=Decimal("10000"),
                    current_amount=Decimal("2500"),
                    priority="HIGH",
                ),
            )

            individual = await service.current_financial_state(
                session,
                household_id=personal.id,
                user_id=ana.id,
                evaluated_at=NOW,
            )
            assert individual["metrics"]["net_worth"] == Decimal("4000.00")
            assert individual["metrics"]["variable_expenses"] == Decimal("0.00")
            assert individual["metrics"]["investment_capacity"] == Decimal("3500.00")

            shared = await service.create_household(
                session,
                user_id=ana.id,
                payload=HouseholdCreate(name="Casa de Ana e Bia"),
            )
            membership = await service.add_member(
                session,
                household_id=shared.id,
                user_id=ana.id,
                payload=HouseholdMemberCreate(email=bia.email),
            )
            with pytest.raises(service.HouseholdNotFoundError):
                await service.current_financial_state(
                    session,
                    household_id=shared.id,
                    user_id=outsider.id,
                    evaluated_at=NOW,
                )

            personal_income = await service.create_resource(
                session,
                Income,
                household_id=shared.id,
                user_id=bia.id,
                payload=IncomeCreate(
                    description="Renda da Bia",
                    amount=Decimal("3000"),
                    income_type="salary",
                    received_at=date(2026, 9, 5),
                    is_recurring=True,
                    ownership_scope="PERSONAL",
                ),
            )
            await service.create_resource(
                session,
                Income,
                household_id=shared.id,
                user_id=ana.id,
                payload=IncomeCreate(
                    description="Renda compartilhada",
                    amount=Decimal("1000"),
                    income_type="rent",
                    received_at=date(2026, 9, 5),
                    is_recurring=True,
                    ownership_scope="HOUSEHOLD",
                ),
            )
            with pytest.raises(service.HouseholdPermissionError):
                await service.update_resource(
                    session,
                    Income,
                    household_id=shared.id,
                    record_id=personal_income.id,
                    user_id=ana.id,
                    payload=IncomeUpdate(description="Não autorizado"),
                )

            await service.remove_member(
                session,
                household_id=shared.id,
                member_id=membership["id"],
                user_id=ana.id,
            )
            reactivated = await service.add_member(
                session,
                household_id=shared.id,
                user_id=ana.id,
                payload=HouseholdMemberCreate(email=bia.email),
            )
            assert reactivated["id"] == membership["id"]
            assert reactivated["status"] == "ACTIVE"

            key = f"snapshot-{uuid4()}"
            first = await service.create_snapshot(
                session,
                household_id=personal.id,
                user_id=ana.id,
                idempotency_key=key,
            )
            second = await service.create_snapshot(
                session,
                household_id=personal.id,
                user_id=ana.id,
                idempotency_key=key,
            )
            assert second.id == first.id
            assert first.input_fingerprint

            with pytest.raises(DBAPIError):
                async with session.begin_nested():
                    await session.execute(
                        text(
                            "UPDATE financial_state_snapshots "
                            "SET confidence = confidence WHERE id = :snapshot_id"
                        ),
                        {"snapshot_id": first.id},
                    )
            with pytest.raises(DBAPIError):
                async with session.begin_nested():
                    await session.execute(text("TRUNCATE financial_state_snapshots"))
        finally:
            await session.close()
            await outer.rollback()
    await engine.dispose()
