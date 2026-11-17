from __future__ import annotations

import asyncio
import os
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select, text
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
from backend.app.financial_state import service, transfers
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


async def _wait_for_postgres_blocker(
    observer: AsyncSession,
    *,
    blocker_pid: int,
    blocked_pid: int,
    timeout_seconds: float = 5.0,
) -> None:
    """Wait for an observed lock edge instead of relying on timing sleeps."""

    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout_seconds
    while loop.time() < deadline:
        result = await observer.execute(
            text("SELECT :blocker_pid = ANY(pg_blocking_pids(:blocked_pid))"),
            {"blocker_pid": blocker_pid, "blocked_pid": blocked_pid},
        )
        if bool(result.scalar_one()):
            return
        await asyncio.sleep(0.01)
    raise AssertionError(
        f"PostgreSQL backend {blocked_pid} was not blocked by {blocker_pid}"
    )


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

            if model in (Income, Expense):
                with pytest.raises(service.FinancialStateValidationError):
                    await service.update_resource(
                        session,
                        model,
                        household_id=shared.id,
                        record_id=private.id,
                        user_id=bia.id,
                        payload=share_update,
                    )
                assert private.ownership_scope == "PERSONAL"
            else:
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
async def test_real_postgres_legacy_diagnosis_counts_only_active_personal_expenses() -> None:
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
            ana, ana_personal, _ = await _user_with_personal_household(
                session,
                label="Diagnosis-A",
            )
            bia, bia_personal, _ = await _user_with_personal_household(
                session,
                label="Diagnosis-B",
            )
            shared = await service.create_household(
                session,
                user_id=ana.id,
                payload=HouseholdCreate(name="Diagnosis shared"),
            )
            await _invite_and_accept(
                session,
                household=shared,
                owner=ana,
                invitee=bia,
            )

            async def create_expense(
                *,
                owner: User,
                household: Household,
                description: str,
                amount: str,
                scope: str,
                day: int,
            ) -> Expense:
                return await service.create_resource(
                    session,
                    Expense,
                    household_id=household.id,
                    user_id=owner.id,
                    payload=ExpenseCreate(
                        description=description,
                        amount=Decimal(amount),
                        category="diagnosis-regression",
                        due_date=date(2026, 11, day),
                        is_recurring=False,
                        expense_nature="VARIABLE",
                        ownership_scope=scope,
                    ),
                )

            await create_expense(
                owner=ana,
                household=ana_personal,
                description="Ana personal counted",
                amount="100.00",
                scope="PERSONAL",
                day=3,
            )
            await create_expense(
                owner=bia,
                household=bia_personal,
                description="Bia personal counted",
                amount="200.00",
                scope="PERSONAL",
                day=4,
            )

            # Mesmo pertencendo a Bia, um registro privado dentro de um household
            # compartilhado não integra o diagnóstico pessoal legado.
            await create_expense(
                owner=bia,
                household=shared,
                description="Bia private inside shared household",
                amount="300.00",
                scope="PERSONAL",
                day=5,
            )
            await create_expense(
                owner=ana,
                household=shared,
                description="Shared expense excluded from personal diagnosis",
                amount="400.00",
                scope="HOUSEHOLD",
                day=6,
            )

            moved = await create_expense(
                owner=ana,
                household=ana_personal,
                description="Ana expense transferred to shared",
                amount="500.00",
                scope="PERSONAL",
                day=7,
            )
            await transfers.transfer_records(
                session,
                model=Expense,
                target_household_id=shared.id,
                user_id=ana.id,
                record_ids=[moved.id],
                duplicate_reviewed=False,
                idempotency_key=f"diagnosis-transfer-{uuid4()}",
            )
            await session.refresh(moved)
            assert moved.household_id == shared.id
            assert moved.ownership_scope == "HOUSEHOLD"

            archived_personal = Household(
                name="Diagnosis archived personal",
                household_type="PERSONAL",
                created_by_user_id=ana.id,
                status="ARCHIVED",
            )
            session.add(archived_personal)
            await session.flush()
            session.add(
                Expense(
                    user_id=ana.id,
                    household_id=archived_personal.id,
                    ownership_scope="PERSONAL",
                    description="Archived personal expense",
                    amount=Decimal("600.00"),
                    category="diagnosis-regression",
                    due_date=date(2026, 11, 8),
                    is_paid=False,
                    is_recurring=False,
                    expense_nature="VARIABLE",
                )
            )
            await session.flush()

            ana_total = await legacy_financial_service._sum_user_expenses_30d(
                session,
                user_id=ana.id,
                today=date(2026, 11, 1),
            )
            bia_total = await legacy_financial_service._sum_user_expenses_30d(
                session,
                user_id=bia.id,
                today=date(2026, 11, 1),
            )

            assert ana_total == Decimal("100.00")
            assert bia_total == Decimal("200.00")
        finally:
            await session.close()
            await outer.rollback()
    await engine.dispose()


@pytest.mark.asyncio
async def test_real_postgres_expense_transfer_is_owner_only_atomic_idempotent_and_dirties_both_contexts() -> None:
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
            ana, _, _ = await _user_with_personal_household(session, label="Transfer-A")
            bia, bia_personal, _ = await _user_with_personal_household(session, label="Transfer-B")
            shared = await service.create_household(
                session,
                user_id=ana.id,
                payload=HouseholdCreate(name="Transfer shared"),
            )
            await _invite_and_accept(session, household=shared, owner=ana, invitee=bia)

            expense = await service.create_resource(
                session,
                Expense,
                household_id=bia_personal.id,
                user_id=bia.id,
                payload=ExpenseCreate(
                    description="Energia da casa",
                    amount=Decimal("240.00"),
                    category="housing",
                    due_date=date(2026, 11, 5),
                    is_recurring=True,
                    expense_nature="FIXED",
                    ownership_scope="PERSONAL",
                ),
            )
            untouched = await service.create_resource(
                session,
                Expense,
                household_id=bia_personal.id,
                user_id=bia.id,
                payload=ExpenseCreate(
                    description="Transporte pessoal",
                    amount=Decimal("90.00"),
                    category="transport",
                    due_date=date(2026, 11, 5),
                    is_recurring=False,
                    expense_nature="VARIABLE",
                    ownership_scope="PERSONAL",
                ),
            )
            await service.create_resource(
                session,
                Expense,
                household_id=shared.id,
                user_id=ana.id,
                payload=ExpenseCreate(
                    description="transporte pessoal",
                    amount=Decimal("90.00"),
                    category="transport",
                    due_date=date(2026, 11, 5),
                    is_recurring=False,
                    expense_nature="VARIABLE",
                    ownership_scope="HOUSEHOLD",
                ),
            )
            ana_id = ana.id
            bia_id = bia.id
            bia_personal_id = bia_personal.id
            shared_id = shared.id
            expense_id = expense.id
            untouched_id = untouched.id

            await session.execute(
                text(
                    "UPDATE continuous_autopilot_states "
                    "SET status = 'UP_TO_DATE', pending_categories = CAST('[]' AS json), dirty_since = NULL "
                    "WHERE household_id IN (:source_id, :target_id)"
                ),
                {"source_id": bia_personal_id, "target_id": shared_id},
            )
            await session.commit()

            with pytest.raises(service.FinancialResourceNotFoundError):
                await transfers.transfer_records(
                    session,
                    model=Expense,
                    target_household_id=shared_id,
                    user_id=ana_id,
                    record_ids=[expense_id],
                    duplicate_reviewed=False,
                    idempotency_key="owner-cannot-bypass",
                )

            preview = await transfers.preview_records(
                session,
                model=Expense,
                target_household_id=shared_id,
                user_id=bia_id,
                record_ids=[untouched_id],
            )
            assert preview["requires_duplicate_review"] is True
            assert len(preview["items"][0]["possible_duplicates"]) == 1
            with pytest.raises(service.HouseholdConflictError):
                await transfers.transfer_records(
                    session,
                    model=Expense,
                    target_household_id=shared_id,
                    user_id=bia_id,
                    record_ids=[untouched_id],
                    duplicate_reviewed=False,
                    idempotency_key="duplicate-review-required",
                )
            await session.refresh(untouched)
            assert untouched.household_id == bia_personal_id
            assert untouched.ownership_scope == "PERSONAL"

            with pytest.raises(service.FinancialResourceNotFoundError):
                await transfers.transfer_records(
                    session,
                    model=Expense,
                    target_household_id=shared_id,
                    user_id=bia_id,
                    record_ids=[untouched_id, 999_999_999],
                    duplicate_reviewed=False,
                    idempotency_key="atomic-invalid-batch",
                )
            await session.refresh(untouched)
            assert untouched.household_id == bia_personal_id
            assert untouched.ownership_scope == "PERSONAL"

            result = await transfers.transfer_records(
                session,
                model=Expense,
                target_household_id=shared_id,
                user_id=bia_id,
                record_ids=[expense_id],
                duplicate_reviewed=False,
                idempotency_key="move-energy-once",
            )
            replay = await transfers.transfer_records(
                session,
                model=Expense,
                target_household_id=shared_id,
                user_id=bia_id,
                record_ids=[expense_id],
                duplicate_reviewed=False,
                idempotency_key="move-energy-once",
            )

            assert result["replayed"] is False
            assert replay["replayed"] is True
            assert replay["transfer_id"] == result["transfer_id"]
            await session.refresh(expense)
            assert expense.household_id == shared_id
            assert expense.ownership_scope == "HOUSEHOLD"

            audit = await session.execute(
                text(
                    "SELECT COUNT(*) FROM financial_record_transfer_items "
                    "WHERE resource_type = 'EXPENSE' AND resource_id = :resource_id"
                ),
                {"resource_id": expense_id},
            )
            assert audit.scalar_one() == 1

            state_rows = await session.execute(
                text(
                    "SELECT household_id, status, pending_categories "
                    "FROM continuous_autopilot_states "
                    "WHERE household_id IN (:source_id, :target_id)"
                ),
                {"source_id": bia_personal_id, "target_id": shared_id},
            )
            dirty = {row.household_id: row for row in state_rows}
            assert dirty[bia_personal_id].status == "REEVALUATION_REQUIRED"
            assert dirty[shared_id].status == "REEVALUATION_REQUIRED"
            assert "FINANCIAL_DATA" in dirty[bia_personal_id].pending_categories
            assert "FINANCIAL_DATA" in dirty[shared_id].pending_categories

            source_ids = {
                item.id
                for item in await service.list_resources(
                    session,
                    Expense,
                    household_id=bia_personal_id,
                    user_id=bia_id,
                )
            }
            target_ids = {
                item.id
                for item in await service.list_resources(
                    session,
                    Expense,
                    household_id=shared_id,
                    user_id=ana_id,
                )
            }
            assert expense_id not in source_ids
            assert expense_id in target_ids
        finally:
            await session.close()
            await outer.rollback()
    await engine.dispose()


@pytest.mark.asyncio
async def test_real_postgres_transfer_is_concurrent_safe_and_blocks_stale_delete() -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL)
    setup = AsyncSession(engine, expire_on_commit=False)
    try:
        user, personal, _ = await _user_with_personal_household(
            setup, label="Transfer-Concurrent"
        )
        shared = Household(
            name="Casa concorrente",
            household_type="SHARED",
            created_by_user_id=user.id,
            status="ACTIVE",
        )
        setup.add(shared)
        await setup.flush()
        setup.add(
            HouseholdMember(
                household_id=shared.id,
                user_id=user.id,
                role="OWNER",
                status="ACTIVE",
                is_default=False,
            )
        )
        await setup.commit()

        async def create_expense(description: str, amount: str, day: int) -> Expense:
            return await service.create_resource(
                setup,
                Expense,
                household_id=personal.id,
                user_id=user.id,
                payload=ExpenseCreate(
                    description=description,
                    amount=Decimal(amount),
                    category="moradia",
                    due_date=date(2026, 11, day),
                    is_recurring=True,
                    expense_nature="FIXED",
                    ownership_scope="PERSONAL",
                ),
            )

        async def move_record(record_id: int, key: str):
            async with AsyncSession(engine, expire_on_commit=False) as session:
                return await transfers.transfer_records(
                    session,
                    model=Expense,
                    target_household_id=shared.id,
                    user_id=user.id,
                    record_ids=[record_id],
                    duplicate_reviewed=False,
                    idempotency_key=key,
                )

        first = await create_expense("Energia concorrente", "240.00", 5)
        same_key_results = await asyncio.gather(
            move_record(first.id, "same-concurrent-key"),
            move_record(first.id, "same-concurrent-key"),
        )
        assert sorted(result["replayed"] for result in same_key_results) == [False, True]
        assert len({result["transfer_id"] for result in same_key_results}) == 1

        second = await create_expense("Internet concorrente", "120.00", 6)
        different_key_results = await asyncio.gather(
            move_record(second.id, "different-key-a"),
            move_record(second.id, "different-key-b"),
            return_exceptions=True,
        )
        successful = [result for result in different_key_results if isinstance(result, dict)]
        rejected = [result for result in different_key_results if isinstance(result, Exception)]
        assert len(successful) == 1
        assert len(rejected) == 1
        assert isinstance(rejected[0], service.FinancialResourceNotFoundError)

        third = await create_expense("Água concorrente", "90.00", 7)
        lock_session = AsyncSession(engine, expire_on_commit=False)
        stale_session = AsyncSession(engine, expire_on_commit=False)
        try:
            locked_result = await lock_session.execute(
                select(Expense).where(Expense.id == third.id).with_for_update()
            )
            locked = locked_result.scalar_one()
            stale_delete = asyncio.create_task(
                service.delete_resource(
                    stale_session,
                    Expense,
                    household_id=personal.id,
                    record_id=third.id,
                    user_id=user.id,
                )
            )
            await asyncio.sleep(0.1)
            assert not stale_delete.done()
            locked.household_id = shared.id
            locked.ownership_scope = "HOUSEHOLD"
            await lock_session.commit()
            with pytest.raises(service.FinancialResourceNotFoundError):
                await stale_delete
        finally:
            await lock_session.close()
            await stale_session.close()

        async with AsyncSession(engine) as verify:
            item_count = await verify.execute(
                text(
                    "SELECT COUNT(*) FROM financial_record_transfer_items "
                    "WHERE resource_type = 'EXPENSE' "
                    "AND resource_id IN (:first_id, :second_id)"
                ),
                {"first_id": first.id, "second_id": second.id},
            )
            assert item_count.scalar_one() == 2
    finally:
        await setup.close()
        await engine.dispose()


@pytest.mark.asyncio
async def test_real_postgres_income_transfer_preserves_financial_data_and_audit() -> None:
    """Income uses the same audited move without being recreated or losing fields."""

    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL)
    session = AsyncSession(engine, expire_on_commit=False)
    try:
        user, personal, _ = await _user_with_personal_household(
            session, label="Transfer-Income"
        )
        shared = await service.create_household(
            session,
            user_id=user.id,
            payload=HouseholdCreate(name="Casa para renda compartilhada"),
        )
        income = await service.create_resource(
            session,
            Income,
            household_id=personal.id,
            user_id=user.id,
            payload=IncomeCreate(
                description="Renda recorrente da casa",
                amount=Decimal("4321.09"),
                income_type="salary",
                received_at=date(2026, 11, 10),
                is_recurring=True,
                ownership_scope="PERSONAL",
            ),
        )
        original_id = income.id

        result = await transfers.transfer_records(
            session,
            model=Income,
            target_household_id=shared.id,
            user_id=user.id,
            record_ids=[original_id],
            duplicate_reviewed=False,
            idempotency_key=f"income-transfer-{uuid4()}",
        )

        await session.refresh(income)
        assert result["resource_type"] == "INCOME"
        assert result["moved_record_ids"] == [original_id]
        assert income.id == original_id
        assert income.household_id == shared.id
        assert income.ownership_scope == "HOUSEHOLD"
        assert income.description == "Renda recorrente da casa"
        assert income.amount == Decimal("4321.09")
        assert income.income_type == "salary"
        assert income.received_at == date(2026, 11, 10)
        assert income.is_recurring is True

        audit = await session.execute(
            text(
                "SELECT owner_user_id, source_household_id, target_household_id, "
                "before_data FROM financial_record_transfer_items "
                "WHERE resource_type = 'INCOME' AND resource_id = :resource_id"
            ),
            {"resource_id": original_id},
        )
        row = audit.one()
        assert row.owner_user_id == user.id
        assert row.source_household_id == personal.id
        assert row.target_household_id == shared.id
        assert row.before_data["amount"] == "4321.09"
        assert row.before_data["ownership_scope"] == "PERSONAL"
    finally:
        await session.close()
        await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("membership_action", ["remove", "leave"])
async def test_real_postgres_transfer_and_membership_change_do_not_deadlock(
    membership_action: str,
) -> None:
    """Changing membership must win cleanly without a User/Household lock cycle."""

    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL)
    setup = AsyncSession(engine, expire_on_commit=False)
    try:
        owner, _, _ = await _user_with_personal_household(
            setup, label=f"Deadlock-owner-{membership_action}"
        )
        member, member_personal, _ = await _user_with_personal_household(
            setup, label=f"Deadlock-member-{membership_action}"
        )
        shared = await service.create_household(
            setup,
            user_id=owner.id,
            payload=HouseholdCreate(name=f"Deadlock shared {membership_action}"),
        )
        member_view = await _invite_and_accept(
            setup,
            household=shared,
            owner=owner,
            invitee=member,
        )
        expense = await service.create_resource(
            setup,
            Expense,
            household_id=member_personal.id,
            user_id=member.id,
            payload=ExpenseCreate(
                description=f"Despesa concorrente {membership_action}",
                amount=Decimal("175.00"),
                category="moradia",
                due_date=date(2026, 11, 9),
                is_recurring=False,
                expense_nature="VARIABLE",
                ownership_scope="PERSONAL",
            ),
        )
        owner_id = owner.id
        member_id = member.id
        member_membership_id = int(member_view["id"])
        source_household_id = member_personal.id
        target_household_id = shared.id
        expense_id = expense.id
    finally:
        await setup.close()

    membership_session = AsyncSession(engine, expire_on_commit=False)
    transfer_session = AsyncSession(engine, expire_on_commit=False)
    observer = AsyncSession(engine, expire_on_commit=False)
    try:
        await membership_session.execute(text("SET LOCAL statement_timeout = '5000ms'"))
        await transfer_session.execute(text("SET LOCAL statement_timeout = '5000ms'"))
        membership_pid = int(
            (await membership_session.execute(text("SELECT pg_backend_pid()"))).scalar_one()
        )
        transfer_pid = int(
            (await transfer_session.execute(text("SELECT pg_backend_pid()"))).scalar_one()
        )
        await membership_session.execute(
            select(Household.id)
            .where(Household.id == target_household_id)
            .with_for_update()
        )

        transfer_task = asyncio.create_task(
            transfers.transfer_records(
                transfer_session,
                model=Expense,
                target_household_id=target_household_id,
                user_id=member_id,
                record_ids=[expense_id],
                duplicate_reviewed=False,
                idempotency_key=f"membership-race-{membership_action}",
            )
        )
        await _wait_for_postgres_blocker(
            observer,
            blocker_pid=membership_pid,
            blocked_pid=transfer_pid,
        )

        if membership_action == "remove":
            await service.remove_member(
                membership_session,
                household_id=target_household_id,
                member_id=member_membership_id,
                user_id=owner_id,
            )
        else:
            await service.leave_household(
                membership_session,
                household_id=target_household_id,
                user_id=member_id,
            )

        with pytest.raises(service.HouseholdNotFoundError):
            await asyncio.wait_for(transfer_task, timeout=5)
    finally:
        await membership_session.rollback()
        await transfer_session.rollback()
        await observer.rollback()
        await membership_session.close()
        await transfer_session.close()
        await observer.close()

    async with AsyncSession(engine) as verify:
        saved = await verify.get(Expense, expense_id)
        assert saved is not None
        assert saved.household_id == source_household_id
        assert saved.ownership_scope == "PERSONAL"
        audit_count = await verify.execute(
            text(
                "SELECT COUNT(*) FROM financial_record_transfer_items "
                "WHERE resource_type = 'EXPENSE' AND resource_id = :resource_id"
            ),
            {"resource_id": expense_id},
        )
        assert audit_count.scalar_one() == 0
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
