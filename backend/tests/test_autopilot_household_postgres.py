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
    AssetUpdate,
    ExpenseCreate,
    ExpenseUpdate,
    GoalCreate,
    GoalUpdate,
    HouseholdCreate,
    HouseholdInvitationCreate,
    IncomeCreate,
    IncomeUpdate,
    LiabilityCreate,
    LiabilityUpdate,
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


async def _invite_and_accept(
    session: AsyncSession,
    *,
    household: Household,
    owner: User,
    invitee: User,
) -> dict:
    invitation = await service.create_invitation(
        session,
        household_id=household.id,
        user_id=owner.id,
        payload=HouseholdInvitationCreate(email=invitee.email),
    )
    await service.accept_invitation(
        session,
        invitation_id=invitation["id"],
        user_id=invitee.id,
    )
    members = await service.list_members(
        session,
        household_id=household.id,
        user_id=owner.id,
    )
    return next(member for member in members if member["user_id"] == invitee.id)


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
            membership = await _invite_and_accept(
                session, household=shared, owner=ana, invitee=bia
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
            with pytest.raises(service.FinancialResourceNotFoundError):
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
            reactivated = await _invite_and_accept(
                session, household=shared, owner=ana, invitee=bia
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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("model", "personal_payload", "household_payload", "share_update", "private_update"),
    [
        (
            Income,
            IncomeCreate(description="B private income", amount=Decimal("5111"), income_type="salary", received_at=date(2026, 9, 8), is_recurring=True, ownership_scope="PERSONAL"),
            IncomeCreate(description="Shared income", amount=Decimal("1000"), income_type="rent", received_at=date(2026, 9, 8), is_recurring=True, ownership_scope="HOUSEHOLD"),
            IncomeUpdate(ownership_scope="HOUSEHOLD"),
            IncomeUpdate(ownership_scope="PERSONAL"),
        ),
        (
            Expense,
            ExpenseCreate(description="B private expense", amount=Decimal("1444"), category="private", due_date=date(2026, 9, 8), is_recurring=True, expense_nature="FIXED", ownership_scope="PERSONAL"),
            ExpenseCreate(description="Shared expense", amount=Decimal("600"), category="shared", due_date=date(2026, 9, 8), is_recurring=True, expense_nature="FIXED", ownership_scope="HOUSEHOLD"),
            ExpenseUpdate(ownership_scope="HOUSEHOLD"),
            ExpenseUpdate(ownership_scope="PERSONAL"),
        ),
        (
            FinancialLiability,
            LiabilityCreate(name="B private debt", liability_type="loan", current_balance=Decimal("9222"), ownership_scope="PERSONAL"),
            LiabilityCreate(name="Shared debt", liability_type="loan", current_balance=Decimal("200"), ownership_scope="HOUSEHOLD"),
            LiabilityUpdate(ownership_scope="HOUSEHOLD"),
            LiabilityUpdate(ownership_scope="PERSONAL"),
        ),
        (
            OwnedAsset,
            AssetCreate(name="B private asset", asset_class="CASH", current_value=Decimal("8111"), ownership_scope="PERSONAL"),
            AssetCreate(name="Shared reserve", asset_class="EMERGENCY_RESERVE", current_value=Decimal("700"), ownership_scope="HOUSEHOLD"),
            AssetUpdate(ownership_scope="HOUSEHOLD"),
            AssetUpdate(ownership_scope="PERSONAL"),
        ),
        (
            FinancialGoal,
            GoalCreate(name="B private goal 7444", target_amount=Decimal("7444"), priority="HIGH", ownership_scope="PERSONAL"),
            GoalCreate(name="Shared goal", target_amount=Decimal("2000"), priority="HIGH", ownership_scope="HOUSEHOLD"),
            GoalUpdate(ownership_scope="HOUSEHOLD"),
            GoalUpdate(ownership_scope="PERSONAL"),
        ),
    ],
)
async def test_real_postgres_personal_is_owner_only_for_every_resource(
    model, personal_payload, household_payload, share_update, private_update
) -> None:
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
            ana, _, _ = await _user_with_personal_household(session, label="Privacy-A")
            bia, _, _ = await _user_with_personal_household(session, label="Privacy-B")
            shared = await service.create_household(
                session,
                user_id=ana.id,
                payload=HouseholdCreate(name="Privacy shared"),
            )
            await _invite_and_accept(
                session, household=shared, owner=ana, invitee=bia
            )
            private = await service.create_resource(
                session,
                model,
                household_id=shared.id,
                user_id=bia.id,
                payload=personal_payload,
            )
            shared_record = await service.create_resource(
                session,
                model,
                household_id=shared.id,
                user_id=ana.id,
                payload=household_payload,
            )

            assert [item.id for item in await service.list_resources(session, model, household_id=shared.id, user_id=ana.id)] == [shared_record.id]
            assert {item.id for item in await service.list_resources(session, model, household_id=shared.id, user_id=bia.id)} == {private.id, shared_record.id}
            with pytest.raises(service.FinancialResourceNotFoundError):
                await service.get_resource(session, model, household_id=shared.id, record_id=private.id, user_id=ana.id)
            with pytest.raises(service.FinancialResourceNotFoundError):
                await service.update_resource(session, model, household_id=shared.id, record_id=private.id, user_id=ana.id, payload=share_update)
            with pytest.raises(service.FinancialResourceNotFoundError):
                await service.delete_resource(session, model, household_id=shared.id, record_id=private.id, user_id=ana.id)

            shared_private = await service.update_resource(
                session,
                model,
                household_id=shared.id,
                record_id=private.id,
                user_id=bia.id,
                payload=share_update,
            )
            assert shared_private.ownership_scope == "HOUSEHOLD"
            assert (await service.get_resource(session, model, household_id=shared.id, record_id=private.id, user_id=ana.id)).id == private.id
            with pytest.raises(service.HouseholdPermissionError):
                await service.update_resource(session, model, household_id=shared.id, record_id=private.id, user_id=ana.id, payload=private_update)

            private_again = await service.update_resource(
                session,
                model,
                household_id=shared.id,
                record_id=private.id,
                user_id=bia.id,
                payload=private_update,
            )
            assert private_again.ownership_scope == "PERSONAL"
            with pytest.raises(service.FinancialResourceNotFoundError):
                await service.get_resource(session, model, household_id=shared.id, record_id=private.id, user_id=ana.id)
        finally:
            await session.close()
            await outer.rollback()
    await engine.dispose()


@pytest.mark.asyncio
async def test_real_postgres_shared_state_and_snapshot_cannot_infer_personal_income() -> None:
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
            ana, _, _ = await _user_with_personal_household(session, label="Inference-A")
            bia, _, _ = await _user_with_personal_household(session, label="Inference-B")
            shared = await service.create_household(
                session,
                user_id=ana.id,
                payload=HouseholdCreate(name="Inference shared"),
            )
            await _invite_and_accept(
                session, household=shared, owner=ana, invitee=bia
            )
            for owner, amount, scope, description in (
                (ana, "5111", "PERSONAL", "A private 5111"),
                (bia, "3222", "PERSONAL", "B private 3222"),
                (ana, "1000", "HOUSEHOLD", "Shared 1000"),
            ):
                await service.create_resource(
                    session,
                    Income,
                    household_id=shared.id,
                    user_id=owner.id,
                    payload=IncomeCreate(
                        description=description,
                        amount=Decimal(amount),
                        income_type="salary",
                        received_at=date(2026, 9, 8),
                        is_recurring=True,
                        ownership_scope=scope,
                    ),
                )

            inputs = await service.build_normalized_inputs(
                session, household_id=shared.id, user_id=bia.id
            )
            state = await service.current_financial_state(
                session,
                household_id=shared.id,
                user_id=bia.id,
                evaluated_at=NOW,
            )
            snapshot = await service.create_snapshot(
                session,
                household_id=shared.id,
                user_id=bia.id,
                idempotency_key=f"privacy-{uuid4()}",
                evaluated_at=NOW,
            )

            assert inputs["privacy_contract_version"] == "household-privacy-v1"
            assert inputs["decision_scope"] == "HOUSEHOLD_SHARED"
            assert [item["amount"] for item in inputs["incomes"]] == [Decimal("1000")]
            assert inputs["financial_profiles"] == []
            assert state["metrics"]["recurring_monthly_income"] == Decimal("1000.00")
            assert state["member_views"] == []
            frozen = str(snapshot.normalized_inputs) + str(snapshot.metrics) + str(snapshot.member_views)
            assert "5111" not in frozen
            assert "3222" not in frozen
        finally:
            await session.close()
            await outer.rollback()
    await engine.dispose()
