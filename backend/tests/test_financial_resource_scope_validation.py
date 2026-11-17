from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from backend.app.financial.models import Expense, Income
from backend.app.financial_state import service
from backend.app.financial_state.models import Household, HouseholdMember
from backend.app.financial_state.schemas import ExpenseUpdate, IncomeCreate


@pytest.mark.asyncio
async def test_shared_income_cannot_be_created_inside_personal_household(monkeypatch) -> None:
    household = Household(
        id=11,
        name="Espaço pessoal",
        household_type="PERSONAL",
        created_by_user_id=7,
        status="ACTIVE",
    )
    membership = HouseholdMember(
        household_id=11,
        user_id=7,
        role="OWNER",
        status="ACTIVE",
        is_default=True,
    )

    async def fake_access(*_args, **_kwargs):
        return household, membership

    monkeypatch.setattr(service, "get_household_access", fake_access)
    session = AsyncMock()

    with pytest.raises(
        service.FinancialStateValidationError,
        match="shared financial resources require a shared household",
    ):
        await service.create_resource(
            session,
            Income,
            household_id=11,
            user_id=7,
            payload=IncomeCreate(
                description="Renda compartilhada inválida",
                amount=Decimal("1000.00"),
                income_type="salary",
                received_at=date(2026, 11, 5),
                is_recurring=True,
                ownership_scope="HOUSEHOLD",
            ),
        )

    session.add.assert_not_called()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["update", "delete"])
async def test_financial_mutations_lock_record_before_changing_it(
    monkeypatch,
    operation: str,
) -> None:
    household = Household(
        id=22,
        name="Espaço pessoal",
        household_type="PERSONAL",
        created_by_user_id=7,
        status="ACTIVE",
    )
    membership = HouseholdMember(
        household_id=22,
        user_id=7,
        role="OWNER",
        status="ACTIVE",
        is_default=True,
    )
    expense = Expense(
        id=33,
        household_id=22,
        user_id=7,
        ownership_scope="PERSONAL",
        description="Conta de energia",
        amount=Decimal("240.00"),
        category="moradia",
        due_date=date(2026, 11, 5),
        is_paid=False,
        is_recurring=True,
        expense_nature="FIXED",
    )

    async def fake_access(*_args, **_kwargs):
        return household, membership

    locked = AsyncMock(return_value=expense)
    monkeypatch.setattr(service, "get_household_access", fake_access)
    monkeypatch.setattr(service, "_get_visible_record", locked)
    monkeypatch.setattr(service, "_mark_resource_dirty_if_shared_visible", AsyncMock())
    session = AsyncMock()

    if operation == "update":
        await service.update_resource(
            session,
            Expense,
            household_id=22,
            record_id=33,
            user_id=7,
            payload=ExpenseUpdate(description="Conta de energia revisada"),
        )
    else:
        await service.delete_resource(
            session,
            Expense,
            household_id=22,
            record_id=33,
            user_id=7,
        )

    assert locked.await_args.kwargs["lock"] is True
