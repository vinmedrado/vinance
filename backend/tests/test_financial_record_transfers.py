from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from backend.app.financial.models import Expense, Income
from backend.app.financial_state.schemas import FinancialRecordTransferRequest
from backend.app.financial_state.transfers import (
    _before_data,
    _request_fingerprint,
    _semantic_key,
    transfer_records,
)
from backend.app.financial_state.service import FinancialStateValidationError


def _expense(**overrides):
    values = {
        "id": 1,
        "user_id": 10,
        "household_id": 20,
        "ownership_scope": "PERSONAL",
        "description": "  Mercado do mês ",
        "amount": Decimal("350.00"),
        "category": "Alimentação",
        "due_date": date(2026, 11, 4),
        "paid_at": None,
        "is_paid": False,
        "is_recurring": True,
        "expense_nature": "VARIABLE",
        "created_at": datetime(2026, 11, 4, tzinfo=timezone.utc),
        "updated_at": datetime(2026, 11, 4, tzinfo=timezone.utc),
    }
    values.update(overrides)
    return Expense(**values)


def test_semantic_duplicate_key_normalizes_text_but_keeps_financial_facts() -> None:
    first = _expense(id=1)
    equivalent = _expense(
        id=2,
        ownership_scope="HOUSEHOLD",
        description="mercado do mês",
        category="alimentação",
    )
    other_payment = _expense(id=3, amount=Decimal("351.00"))

    assert _semantic_key(first) == _semantic_key(equivalent)
    assert _semantic_key(first) != _semantic_key(other_payment)


def test_audit_before_image_preserves_money_dates_and_original_visibility() -> None:
    snapshot = _before_data(_expense())

    assert snapshot["amount"] == "350.00"
    assert snapshot["due_date"] == "2026-11-04"
    assert snapshot["ownership_scope"] == "PERSONAL"
    assert snapshot["household_id"] == 20


def test_idempotency_fingerprint_is_order_independent_but_payload_sensitive() -> None:
    first = _request_fingerprint(
        resource_type="EXPENSE",
        target_household_id=30,
        user_id=10,
        record_ids=[9, 3],
        duplicate_reviewed=False,
    )
    reordered = _request_fingerprint(
        resource_type="EXPENSE",
        target_household_id=30,
        user_id=10,
        record_ids=[3, 9],
        duplicate_reviewed=False,
    )
    reviewed = _request_fingerprint(
        resource_type="EXPENSE",
        target_household_id=30,
        user_id=10,
        record_ids=[3, 9],
        duplicate_reviewed=True,
    )

    assert first == reordered
    assert first != reviewed


@pytest.mark.parametrize("record_ids", [[], [0], [1, 1], list(range(1, 102))])
def test_transfer_request_rejects_unsafe_batches(record_ids: list[int]) -> None:
    with pytest.raises(ValidationError):
        FinancialRecordTransferRequest(record_ids=record_ids)


def test_income_duplicate_identity_keeps_type_and_recurrence() -> None:
    base = Income(
        id=1,
        user_id=10,
        household_id=20,
        ownership_scope="PERSONAL",
        description="Salário",
        amount=Decimal("5000.00"),
        income_type="salary",
        received_at=date(2026, 11, 1),
        is_recurring=True,
    )
    different_type = Income(
        id=2,
        user_id=10,
        household_id=30,
        ownership_scope="HOUSEHOLD",
        description="Salário",
        amount=Decimal("5000.00"),
        income_type="other",
        received_at=date(2026, 11, 1),
        is_recurring=True,
    )
    assert _semantic_key(base) != _semantic_key(different_type)


@pytest.mark.asyncio
@pytest.mark.parametrize("record_ids", [[], [0], [1, 1], list(range(1, 102))])
async def test_transfer_service_rejects_unsafe_batches_defense_in_depth(record_ids: list[int]) -> None:
    with pytest.raises(FinancialStateValidationError):
        await transfer_records(
            object(),  # type: ignore[arg-type]
            model=Expense,
            target_household_id=30,
            user_id=10,
            record_ids=record_ids,
            duplicate_reviewed=False,
            idempotency_key="safe-key",
        )
