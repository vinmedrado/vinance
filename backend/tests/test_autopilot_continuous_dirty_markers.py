from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from backend.app.auth import service as auth_service
from backend.app.auth.models import User
from backend.app.auth.schemas import UserCreate
from backend.app.continuous_autopilot import service as continuous_service
from backend.app.financial import service as financial_service
from backend.app.financial.models import Expense, FinancialProfile, Income
from backend.app.financial.schemas import (
    ExpenseCreate,
    FinancialProfileCreate,
    IncomeCreate,
)
from backend.app.financial_state import service as state_service
from backend.app.financial_state.models import (
    FinancialGoal,
    FinancialLiability,
    Household,
    OwnedAsset,
)


class _Session:
    def __init__(self):
        self.added = []
        self.events: list[str] = []

    def add(self, value):
        self.added.append(value)

    async def flush(self):
        for value in self.added:
            if isinstance(value, User) and value.id is None:
                value.id = 91
            if isinstance(value, Household) and value.id is None:
                value.id = 10

    async def commit(self):
        self.events.append("commit")

    async def refresh(self, _value):
        return None


def test_all_canonical_financial_resources_have_a_change_category() -> None:
    assert state_service._RESOURCE_CHANGE_CATEGORY == {
        Income: "FINANCIAL_DATA",
        Expense: "FINANCIAL_DATA",
        FinancialLiability: "DEBT",
        OwnedAsset: "ASSETS",
        FinancialGoal: "GOALS",
    }


@pytest.mark.asyncio
async def test_personal_household_is_marked_in_same_user_creation_transaction(
    monkeypatch,
) -> None:
    session = _Session()

    async def mark(_session, **kwargs):
        assert _session is session
        assert kwargs == {"household_id": 10, "category": "HOUSEHOLD"}
        session.events.append("dirty")

    monkeypatch.setattr(continuous_service, "mark_household_dirty", mark)
    monkeypatch.setattr(auth_service, "get_password_hash", lambda _value: "hashed")
    user = await auth_service.create_user(
        session,
        UserCreate(
            email="owner@example.com",
            password="senha-segura",
            full_name="Owner",
        ),
    )
    assert user.id == 91
    assert session.events == ["dirty", "commit"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("operation", "payload"),
    [
        (
            financial_service.create_income,
            IncomeCreate(
                description="Salário",
                amount=Decimal("1000"),
                income_type="salary",
                received_at=date(2026, 9, 24),
                is_recurring=True,
            ),
        ),
        (
            financial_service.create_expense,
            ExpenseCreate(
                description="Moradia",
                amount=Decimal("400"),
                category="housing",
                due_date=date(2026, 9, 24),
                is_paid=False,
                is_recurring=True,
            ),
        ),
    ],
)
async def test_legacy_financial_writes_mark_default_household_before_commit(
    monkeypatch, operation, payload
) -> None:
    session = _Session()

    async def household(*_args, **_kwargs):
        return SimpleNamespace(id=10)

    async def mark(_session, **kwargs):
        assert _session is session
        assert kwargs == {"household_id": 10, "category": "FINANCIAL_DATA"}
        session.events.append("dirty")

    monkeypatch.setattr(financial_service, "get_default_household", household)
    monkeypatch.setattr(continuous_service, "mark_household_dirty", mark)
    await operation(session, user_id=91, payload=payload)
    assert session.events == ["dirty", "commit"]


@pytest.mark.asyncio
async def test_profile_write_marks_all_memberships_before_commit(monkeypatch) -> None:
    session = _Session()

    async def no_profile(*_args, **_kwargs):
        return None

    async def mark(_session, **kwargs):
        assert _session is session
        assert kwargs == {"user_id": 91, "category": "PROFILE"}
        session.events.append("dirty")

    monkeypatch.setattr(financial_service, "get_financial_profile", no_profile)
    monkeypatch.setattr(continuous_service, "mark_user_households_dirty", mark)
    await financial_service.upsert_financial_profile(
        session,
        user_id=91,
        payload=FinancialProfileCreate(
            monthly_salary=Decimal("1000"),
            emergency_reserve=Decimal("100"),
            has_debt_default=False,
            risk_profile="moderate",
        ),
    )
    assert isinstance(session.added[-1], FinancialProfile)
    assert session.events == ["dirty", "commit"]
