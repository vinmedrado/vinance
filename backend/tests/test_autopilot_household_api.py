from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from backend.app.auth.dependencies import get_current_user
from backend.app.auth.models import User
from backend.app.core.database import get_session
from backend.app.financial_state import router as state_router
from backend.app.financial_state import service
from backend.app.main import app


NOW = datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc)


async def _fake_user() -> User:
    return User(
        id=91,
        email="household-api@example.com",
        full_name="Household API",
        hashed_password="unused",
        is_active=True,
    )


async def _fake_session():
    yield object()


def _authenticated() -> dict:
    previous = dict(app.dependency_overrides)
    app.dependency_overrides[get_current_user] = _fake_user
    app.dependency_overrides[get_session] = _fake_session
    return previous


def _restore(previous: dict) -> None:
    app.dependency_overrides.clear()
    app.dependency_overrides.update(previous)


def test_household_api_contract_is_registered_and_authenticated() -> None:
    expected = {
        "/api/v1/financial/households": {"GET", "POST"},
        "/api/v1/financial/households/default": {"GET"},
        "/api/v1/financial/households/{household_id}": {"GET", "PATCH"},
        "/api/v1/financial/households/{household_id}/members": {"GET", "POST"},
        "/api/v1/financial/households/{household_id}/incomes": {"GET", "POST"},
        "/api/v1/financial/households/{household_id}/expenses": {"GET", "POST"},
        "/api/v1/financial/households/{household_id}/debts": {"GET", "POST"},
        "/api/v1/financial/households/{household_id}/assets": {"GET", "POST"},
        "/api/v1/financial/households/{household_id}/goals": {"GET", "POST"},
        "/api/v1/financial/households/{household_id}/financial-state": {"GET"},
        "/api/v1/financial/households/{household_id}/financial-state/snapshots": {"POST"},
        "/api/v1/financial/households/{household_id}/financial-state/history": {"GET"},
    }
    paths = app.openapi()["paths"]
    for path, methods in expected.items():
        assert methods <= {method.upper() for method in paths[path]}
        for method in methods:
            assert paths[path][method.lower()]["security"] == [{"HTTPBearer": []}]


def test_anonymous_user_cannot_list_households() -> None:
    previous = dict(app.dependency_overrides)
    try:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides[get_session] = _fake_session
        with TestClient(app) as client:
            response = client.get("/api/v1/financial/households")
        assert response.status_code == 401
    finally:
        _restore(previous)


@pytest.mark.parametrize(
    ("path", "payload"),
    [
        (
            "/api/v1/financial/households/10/incomes",
            {
                "description": "Salário",
                "amount": 5000,
                "income_type": "salary",
                "received_at": "2026-09-08",
                "is_recurring": True,
                "ownership_scope": "PERSONAL",
            },
        ),
        (
            "/api/v1/financial/households/10/expenses",
            {
                "description": "Moradia",
                "amount": 1500,
                "category": "housing",
                "due_date": "2026-09-08",
                "is_paid": False,
                "is_recurring": True,
                "expense_nature": "FIXED",
                "ownership_scope": "HOUSEHOLD",
            },
        ),
        (
            "/api/v1/financial/households/10/debts",
            {
                "name": "Financiamento",
                "liability_type": "loan",
                "current_balance": 10000,
                "ownership_scope": "PERSONAL",
            },
        ),
        (
            "/api/v1/financial/households/10/assets",
            {
                "name": "Reserva",
                "asset_class": "EMERGENCY_RESERVE",
                "current_value": 1000,
                "ownership_scope": "PERSONAL",
            },
        ),
        (
            "/api/v1/financial/households/10/goals",
            {
                "name": "Casa",
                "target_amount": 100000,
                "priority": "HIGH",
                "ownership_scope": "HOUSEHOLD",
            },
        ),
        (
            "/api/v1/financial/households/10/members",
            {"email": "member@example.com", "role": "MEMBER"},
        ),
    ],
)
def test_client_cannot_choose_database_user_id(monkeypatch, path: str, payload: dict) -> None:
    async def should_not_run(*_args, **_kwargs):
        raise AssertionError("invalid payload reached the service")

    monkeypatch.setattr(state_router.service, "create_resource", should_not_run)
    monkeypatch.setattr(state_router.service, "add_member", should_not_run)
    previous = _authenticated()
    try:
        with TestClient(app) as client:
            response = client.post(path, json={**payload, "user_id": 999})
        assert response.status_code == 422
    finally:
        _restore(previous)


def test_cross_household_lookup_is_indistinguishable_from_missing(monkeypatch) -> None:
    async def not_owned(*_args, **_kwargs):
        raise service.HouseholdNotFoundError("not owned")

    monkeypatch.setattr(state_router.service, "get_household_access", not_owned)
    previous = _authenticated()
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/financial/households/999")
        assert response.status_code == 404
        assert response.json()["error"] == "Recurso financeiro não encontrado"
    finally:
        _restore(previous)


def test_current_state_preserves_null_and_explicit_zero(monkeypatch) -> None:
    async def current(*_args, **_kwargs):
        return {
            "household_id": 10,
            "engine_version": "household-financial-state-v1",
            "evaluated_at": NOW,
            "metrics": {"total_assets": None, "total_liabilities": "0.00"},
            "goals": [],
            "member_views": [],
            "data_quality": "PARTIAL",
            "confidence": 50,
            "missing_fields": ["assets.current_value"],
            "inconsistencies": [],
            "stale_fields": [],
            "provenance": {},
        }

    monkeypatch.setattr(state_router.service, "current_financial_state", current)
    previous = _authenticated()
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/financial/households/10/financial-state")
        assert response.status_code == 200
        assert response.json()["metrics"] == {
            "total_assets": None,
            "total_liabilities": "0.00",
        }
    finally:
        _restore(previous)


def test_snapshot_forwards_authenticated_creator_and_idempotency_key(monkeypatch) -> None:
    captured: dict = {}

    async def create(*_args, **kwargs):
        captured.update(kwargs)
        return {
            "id": 7,
            "household_id": 10,
            "created_by_user_id": 91,
            "evaluated_at": NOW,
            "engine_version": "household-financial-state-v1",
            "normalized_inputs": {},
            "metrics": {},
            "member_views": [],
            "data_quality": "INSUFFICIENT",
            "confidence": 0,
            "missing_fields": ["income"],
            "inconsistencies": [],
            "input_fingerprint": "f" * 64,
            "idempotency_key": "same-request",
            "created_at": NOW,
        }

    monkeypatch.setattr(state_router.service, "create_snapshot", create)
    previous = _authenticated()
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/financial/households/10/financial-state/snapshots",
                headers={"Idempotency-Key": "same-request"},
            )
        assert response.status_code == 201
        assert captured == {
            "household_id": 10,
            "user_id": 91,
            "idempotency_key": "same-request",
        }
    finally:
        _restore(previous)
