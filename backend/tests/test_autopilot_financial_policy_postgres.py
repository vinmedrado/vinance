from __future__ import annotations

import os
from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from backend.app.auth import service as auth_service
from backend.app.auth.schemas import UserCreate
from backend.app.financial.models import Expense, Income
from backend.app.financial_policy import service as policy_service
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
    IncomeUpdate,
    LiabilityCreate,
)


TEST_DATABASE_URL = os.getenv("AUTOPILOT_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="set AUTOPILOT_TEST_DATABASE_URL to an isolated PostgreSQL database",
)


@pytest.mark.asyncio
async def test_real_postgres_policy_current_history_and_household_isolation() -> None:
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
            owner = await auth_service.create_user(
                session,
                UserCreate(
                    email=f"policy-owner-{uuid4()}@example.com",
                    password="senha-segura",
                    full_name="Policy Owner",
                ),
            )
            outsider = await auth_service.create_user(
                session,
                UserCreate(
                    email=f"policy-outsider-{uuid4()}@example.com",
                    password="senha-segura",
                    full_name="Policy Outsider",
                ),
            )
            household = await state_service.get_default_household(
                session, user_id=owner.id
            )
            recurring_income = await state_service.create_resource(
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
                    current_value=Decimal("6000"),
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

            ready = await policy_service.current_financial_policy(
                session,
                household_id=household.id,
                user_id=owner.id,
            )
            assert ready["policy_state"] == "INVESTMENT_READY"
            assert ready["investment_readiness"] == "READY"

            policy_key = f"policy-decision-{uuid4()}"
            frozen = await policy_service.create_policy_decision(
                session,
                household_id=household.id,
                user_id=owner.id,
                idempotency_key=policy_key,
            )
            frozen_retry = await policy_service.create_policy_decision(
                session,
                household_id=household.id,
                user_id=owner.id,
                idempotency_key=policy_key,
            )
            assert frozen_retry["policy_id"] == frozen["policy_id"]
            assert frozen_retry["decision_fingerprint"] == frozen["decision_fingerprint"]
            assert frozen["financial_state_snapshot_id"] is not None
            assert frozen["policy_state"] == "INVESTMENT_READY"
            assert await session.scalar(
                select(func.count(FinancialPolicyDecision.id)).where(
                    FinancialPolicyDecision.household_id == household.id
                )
            ) == 1

            policy_history = await policy_service.policy_decision_history(
                session,
                household_id=household.id,
                user_id=owner.id,
                limit=20,
                offset=0,
            )
            policy_detail = await policy_service.get_policy_decision(
                session,
                household_id=household.id,
                policy_id=frozen["policy_id"],
                user_id=owner.id,
            )
            assert policy_history["total"] == 1
            assert policy_history["items"][0]["policy_id"] == frozen["policy_id"]
            assert policy_detail["decision_fingerprint"] == frozen["decision_fingerprint"]

            for mutation in (
                "UPDATE financial_policy_decisions SET policy_state = 'DATA_BLOCKED' WHERE id = :policy_id",
                "DELETE FROM financial_policy_decisions WHERE id = :policy_id",
                "TRUNCATE TABLE financial_policy_decisions",
            ):
                with pytest.raises(DBAPIError):
                    async with session.begin_nested():
                        await session.execute(
                            text(mutation), {"policy_id": frozen["policy_id"]}
                        )
            assert await session.scalar(
                select(func.count(FinancialPolicyDecision.id)).where(
                    FinancialPolicyDecision.household_id == household.id
                )
            ) == 1

            snapshot = await state_service.create_snapshot(
                session,
                household_id=household.id,
                user_id=owner.id,
                idempotency_key=f"policy-baseline-{uuid4()}",
            )
            snapshot_count = await session.scalar(
                select(func.count(FinancialStateSnapshot.id)).where(
                    FinancialStateSnapshot.household_id == household.id
                )
            )

            await state_service.update_resource(
                session,
                Income,
                household_id=household.id,
                record_id=recurring_income.id,
                user_id=owner.id,
                payload=IncomeUpdate(amount=Decimal("2000")),
            )
            recovery = await policy_service.current_financial_policy(
                session,
                household_id=household.id,
                user_id=owner.id,
                evaluated_at=snapshot.evaluated_at + timedelta(seconds=1),
            )
            assert recovery["policy_state"] == "CASHFLOW_RECOVERY"
            assert recovery["investment_readiness"] == "BLOCKED"
            assert recovery["previous_financial_state"]["comparable"] is True
            assert recovery["previous_financial_state"]["boundary_crossings"]

            replay = await policy_service.financial_policy_from_state_snapshot(
                session,
                household_id=household.id,
                snapshot_id=snapshot.id,
                user_id=owner.id,
            )
            assert replay["source_financial_state"]["snapshot_id"] == snapshot.id
            assert replay["policy_state"] == "INVESTMENT_READY"
            assert await session.scalar(
                select(func.count(FinancialStateSnapshot.id)).where(
                    FinancialStateSnapshot.household_id == household.id
                )
            ) == snapshot_count

            with pytest.raises(state_service.HouseholdNotFoundError):
                await policy_service.current_financial_policy(
                    session,
                    household_id=household.id,
                    user_id=outsider.id,
                )
            with pytest.raises(state_service.HouseholdNotFoundError):
                await policy_service.financial_policy_from_state_snapshot(
                    session,
                    household_id=household.id,
                    snapshot_id=snapshot.id,
                    user_id=outsider.id,
                )
            with pytest.raises(state_service.HouseholdNotFoundError):
                await policy_service.create_policy_decision(
                    session,
                    household_id=household.id,
                    user_id=outsider.id,
                    idempotency_key=f"outsider-{uuid4()}",
                )
            with pytest.raises(state_service.HouseholdNotFoundError):
                await policy_service.policy_decision_history(
                    session,
                    household_id=household.id,
                    user_id=outsider.id,
                    limit=20,
                    offset=0,
                )
            with pytest.raises(state_service.HouseholdNotFoundError):
                await policy_service.get_policy_decision(
                    session,
                    household_id=household.id,
                    policy_id=frozen["policy_id"],
                    user_id=outsider.id,
                )
        finally:
            await session.close()
            await outer.rollback()
    await engine.dispose()
