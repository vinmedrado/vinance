from __future__ import annotations

import os
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from backend.app.auth import service as auth_service
from backend.app.auth.schemas import UserCreate
from backend.app.capital_allocation import service as allocation_service
from backend.app.capital_allocation.models import CapitalAllocationDecision
from backend.app.capital_allocation.schemas import CapitalAllocationRead
from backend.app.financial.models import Expense, Income
from backend.app.financial_policy.models import FinancialPolicyDecision
from backend.app.financial_state import service as state_service
from backend.app.financial_state.models import (
    FinancialGoal,
    FinancialLiability,
    FinancialStateSnapshot,
    OwnedAsset,
)
from backend.app.financial_state.schemas import (
    AssetCreate,
    ExpenseCreate,
    GoalCreate,
    IncomeCreate,
    LiabilityCreate,
)


TEST_DATABASE_URL = os.getenv("AUTOPILOT_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="set AUTOPILOT_TEST_DATABASE_URL to an isolated PostgreSQL database",
)


async def _complete_personal_household(
    session: AsyncSession,
) -> tuple[object, object]:
    owner = await auth_service.create_user(
        session,
        UserCreate(
            email=f"allocation-owner-{uuid4()}@example.com",
            password="senha-segura",
            full_name="Allocation Owner",
        ),
    )
    outsider = await auth_service.create_user(
        session,
        UserCreate(
            email=f"allocation-outsider-{uuid4()}@example.com",
            password="senha-segura",
            full_name="Allocation Outsider",
        ),
    )
    household = await state_service.get_default_household(session, user_id=owner.id)

    await state_service.create_resource(
        session,
        Income,
        household_id=household.id,
        user_id=owner.id,
        payload=IncomeCreate(
            ownership_scope="PERSONAL",
            description="Renda recorrente",
            amount=Decimal("6000"),
            income_type="salary",
            received_at=date(2026, 9, 8),
            is_recurring=True,
        ),
    )
    await state_service.create_resource(
        session,
        Income,
        household_id=household.id,
        user_id=owner.id,
        payload=IncomeCreate(
            ownership_scope="PERSONAL",
            description="Renda não recorrente declarada",
            amount=Decimal("0"),
            income_type="declared_none",
            received_at=date(2026, 9, 8),
            is_recurring=False,
        ),
    )
    for nature in ("FIXED", "VARIABLE"):
        await state_service.create_resource(
            session,
            Expense,
            household_id=household.id,
            user_id=owner.id,
            payload=ExpenseCreate(
                ownership_scope="PERSONAL",
                description=f"Despesa {nature.lower()}",
                amount=Decimal("1000"),
                category="declared",
                due_date=date(2026, 9, 8),
                is_recurring=True,
                expense_nature=nature,
            ),
        )
    await state_service.create_resource(
        session,
        OwnedAsset,
        household_id=household.id,
        user_id=owner.id,
        payload=AssetCreate(
            ownership_scope="PERSONAL",
            asset_class="EMERGENCY_RESERVE",
            name="Reserva",
            current_value=Decimal("12000"),
            value_as_of=date(2026, 9, 8),
        ),
    )
    await state_service.create_resource(
        session,
        FinancialLiability,
        household_id=household.id,
        user_id=owner.id,
        payload=LiabilityCreate(
            ownership_scope="PERSONAL",
            name="Obrigação quitada",
            liability_type="loan",
            current_balance=Decimal("0"),
            monthly_payment=Decimal("0"),
            annual_interest_rate_pct=Decimal("0"),
            status="PAID",
        ),
    )
    await state_service.create_resource(
        session,
        FinancialGoal,
        household_id=household.id,
        user_id=owner.id,
        payload=GoalCreate(
            ownership_scope="PERSONAL",
            name="Objetivo financiado",
            target_amount=Decimal("100"),
            current_amount=Decimal("100"),
            priority="LOW",
        ),
    )
    return (owner, outsider)


@pytest.mark.asyncio
async def test_real_postgres_allocation_audit_idempotency_and_isolation() -> None:
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
            owner, outsider = await _complete_personal_household(session)
            household = await state_service.get_default_household(
                session, user_id=owner.id
            )

            current = await allocation_service.current_capital_allocation(
                session,
                household_id=household.id,
                user_id=owner.id,
            )
            assert current["allocation_status"] == "SURPLUS"
            assert current["allocatable_capital"] == Decimal("4000.00")
            assert current["investment_bucket_amount"] == Decimal("4000.00")
            CapitalAllocationRead.model_validate(current)

            idempotency_key = f"allocation-decision-{uuid4()}"
            frozen = await allocation_service.create_capital_allocation_decision(
                session,
                household_id=household.id,
                user_id=owner.id,
                idempotency_key=idempotency_key,
            )
            frozen_retry = await allocation_service.create_capital_allocation_decision(
                session,
                household_id=household.id,
                user_id=owner.id,
                idempotency_key=idempotency_key,
            )
            assert frozen_retry["allocation_id"] == frozen["allocation_id"]
            assert frozen_retry["decision_fingerprint"] == frozen["decision_fingerprint"]
            assert frozen["financial_state_snapshot_id"] is not None
            assert frozen["financial_policy_id"] is not None
            CapitalAllocationRead.model_validate(frozen)

            assert await session.scalar(
                select(func.count(CapitalAllocationDecision.id)).where(
                    CapitalAllocationDecision.household_id == household.id
                )
            ) == 1
            assert await session.scalar(
                select(func.count(FinancialPolicyDecision.id)).where(
                    FinancialPolicyDecision.household_id == household.id
                )
            ) == 1
            assert await session.scalar(
                select(func.count(FinancialStateSnapshot.id)).where(
                    FinancialStateSnapshot.household_id == household.id
                )
            ) == 1

            replay = await allocation_service.capital_allocation_from_policy_decision(
                session,
                household_id=household.id,
                policy_id=frozen["financial_policy_id"],
                user_id=owner.id,
            )
            history = await allocation_service.capital_allocation_history(
                session,
                household_id=household.id,
                user_id=owner.id,
                limit=20,
                offset=0,
            )
            detail = await allocation_service.get_capital_allocation_decision(
                session,
                household_id=household.id,
                allocation_id=frozen["allocation_id"],
                user_id=owner.id,
            )
            assert replay["decision_fingerprint"] == frozen["decision_fingerprint"]
            assert history["total"] == 1
            assert history["items"][0]["allocation_id"] == frozen["allocation_id"]
            assert detail["decision_fingerprint"] == frozen["decision_fingerprint"]

            for mutation in (
                "UPDATE capital_allocation_decisions SET allocation_status = 'BLOCKED' WHERE id = :allocation_id",
                "DELETE FROM capital_allocation_decisions WHERE id = :allocation_id",
                "TRUNCATE TABLE capital_allocation_decisions",
            ):
                with pytest.raises(DBAPIError):
                    async with session.begin_nested():
                        await session.execute(
                            text(mutation),
                            {"allocation_id": frozen["allocation_id"]},
                        )

            with pytest.raises(state_service.HouseholdNotFoundError):
                await allocation_service.current_capital_allocation(
                    session,
                    household_id=household.id,
                    user_id=outsider.id,
                )
            with pytest.raises(state_service.HouseholdNotFoundError):
                await allocation_service.capital_allocation_from_policy_decision(
                    session,
                    household_id=household.id,
                    policy_id=frozen["financial_policy_id"],
                    user_id=outsider.id,
                )
            with pytest.raises(state_service.HouseholdNotFoundError):
                await allocation_service.create_capital_allocation_decision(
                    session,
                    household_id=household.id,
                    user_id=outsider.id,
                    idempotency_key=f"outsider-{uuid4()}",
                )
            with pytest.raises(state_service.HouseholdNotFoundError):
                await allocation_service.capital_allocation_history(
                    session,
                    household_id=household.id,
                    user_id=outsider.id,
                    limit=20,
                    offset=0,
                )
            with pytest.raises(state_service.HouseholdNotFoundError):
                await allocation_service.get_capital_allocation_decision(
                    session,
                    household_id=household.id,
                    allocation_id=frozen["allocation_id"],
                    user_id=outsider.id,
                )
        finally:
            await session.close()
            await outer.rollback()
    await engine.dispose()
