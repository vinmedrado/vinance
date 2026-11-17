from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from backend.app.auth.dependencies import get_current_user
from backend.app.auth.models import User
from backend.app.core.database import get_session
from backend.app.financial_state import transfers
from backend.app.main import app


async def _fake_session():
    yield object()


async def _fake_user():
    return User(
        id=41,
        email="owner@example.com",
        full_name="Owner",
        hashed_password="unused",
        is_active=True,
    )


def test_transfer_routes_require_authentication() -> None:
    app.dependency_overrides.clear()
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/financial/households/7/expenses/transfer-from-personal/preview",
            json={"record_ids": [1]},
        )
    assert response.status_code == 401


def test_expense_transfer_uses_authenticated_owner_and_idempotency(monkeypatch) -> None:
    captured = {}

    async def fake_transfer(session, *, model, target_household_id, user_id, record_ids, duplicate_reviewed, idempotency_key):
        captured.update(
            target_household_id=target_household_id,
            user_id=user_id,
            record_ids=record_ids,
            duplicate_reviewed=duplicate_reviewed,
            idempotency_key=idempotency_key,
            model=model.__name__,
        )
        return {
            "transfer_id": 9,
            "resource_type": "EXPENSE",
            "target_household_id": 7,
            "record_count": 2,
            "moved_record_ids": [2, 3],
            "source_household_ids": [4],
            "status": "COMMITTED",
            "replayed": False,
            "created_at": datetime(2026, 11, 4, tzinfo=timezone.utc),
        }

    monkeypatch.setattr(transfers, "transfer_records", fake_transfer)
    app.dependency_overrides[get_current_user] = _fake_user
    app.dependency_overrides[get_session] = _fake_session
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/financial/households/7/expenses/transfer-from-personal",
                headers={"Idempotency-Key": "move-expenses-1"},
                json={
                    "record_ids": [2, 3],
                    "duplicate_reviewed": True,
                    "owner_user_id": 999,
                },
            )
            invalid_owner = response

            response = client.post(
                "/api/v1/financial/households/7/expenses/transfer-from-personal",
                headers={"Idempotency-Key": "move-expenses-1"},
                json={"record_ids": [2, 3], "duplicate_reviewed": True},
            )
    finally:
        app.dependency_overrides.clear()

    assert invalid_owner.status_code == 422
    assert response.status_code == 200
    assert captured == {
        "target_household_id": 7,
        "user_id": 41,
        "record_ids": [2, 3],
        "duplicate_reviewed": True,
        "idempotency_key": "move-expenses-1",
        "model": "Expense",
    }


def test_commit_requires_idempotency_key() -> None:
    app.dependency_overrides[get_current_user] = _fake_user
    app.dependency_overrides[get_session] = _fake_session
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/financial/households/7/incomes/transfer-from-personal",
                json={"record_ids": [1], "duplicate_reviewed": False},
            )
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 422
