from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

from fastapi.testclient import TestClient

from backend.app.auth.dependencies import get_current_user
from backend.app.auth.models import User
from backend.app.core.database import get_session
from backend.app.financial import service
from backend.app.main import app


async def _fake_session():
    yield object()


async def _fake_user():
    return User(
        id=1,
        email="vinance@test.local",
        full_name="Vinance Test",
        hashed_password="not-used-in-test",
        is_active=True,
    )


def _install_overrides():
    app.dependency_overrides[get_current_user] = _fake_user
    app.dependency_overrides[get_session] = _fake_session


def _clear_overrides():
    app.dependency_overrides.clear()


def _stamp():
    return datetime(2026, 6, 1, tzinfo=timezone.utc)


def test_create_and_list_incomes(monkeypatch):
    _install_overrides()

    async def fake_create_income(session, *, user_id, payload):
        return SimpleNamespace(id=1, user_id=user_id, created_at=_stamp(), updated_at=_stamp(), **payload.model_dump())

    async def fake_list_incomes(session, *, user_id):
        return [
            SimpleNamespace(
                id=1,
                user_id=user_id,
                description="Salário",
                amount=Decimal("5000.00"),
                income_type="salary",
                received_at=date(2026, 6, 1),
                is_recurring=True,
                created_at=_stamp(),
                updated_at=_stamp(),
            )
        ]

    monkeypatch.setattr(service, "create_income", fake_create_income)
    monkeypatch.setattr(service, "list_incomes", fake_list_incomes)

    with TestClient(app) as client:
        created = client.post(
            "/api/v1/financial/incomes",
            json={
                "description": "Salário",
                "amount": "5000.00",
                "income_type": "salary",
                "received_at": "2026-06-01",
                "is_recurring": True,
            },
        )
        listed = client.get("/api/v1/financial/incomes")

    _clear_overrides()
    assert created.status_code == 201
    assert listed.status_code == 200
    assert listed.json()[0]["user_id"] == 1


def test_create_and_list_expenses(monkeypatch):
    _install_overrides()

    async def fake_create_expense(session, *, user_id, payload):
        return SimpleNamespace(id=1, user_id=user_id, created_at=_stamp(), updated_at=_stamp(), **payload.model_dump())

    async def fake_list_expenses(session, *, user_id):
        return [
            SimpleNamespace(
                id=1,
                user_id=user_id,
                description="Aluguel",
                amount=Decimal("1800.00"),
                category="housing",
                due_date=date(2026, 6, 10),
                paid_at=None,
                is_paid=False,
                is_recurring=True,
                created_at=_stamp(),
                updated_at=_stamp(),
            )
        ]

    monkeypatch.setattr(service, "create_expense", fake_create_expense)
    monkeypatch.setattr(service, "list_expenses", fake_list_expenses)

    with TestClient(app) as client:
        created = client.post(
            "/api/v1/financial/expenses",
            json={
                "description": "Aluguel",
                "amount": "1800.00",
                "category": "housing",
                "due_date": "2026-06-10",
                "is_paid": False,
                "is_recurring": True,
            },
        )
        listed = client.get("/api/v1/financial/expenses")

    _clear_overrides()
    assert created.status_code == 201
    assert listed.status_code == 200
    assert listed.json()[0]["category"] == "housing"


def test_create_and_get_profile(monkeypatch):
    _install_overrides()

    async def fake_upsert_profile(session, *, user_id, payload):
        return SimpleNamespace(id=1, user_id=user_id, created_at=_stamp(), updated_at=_stamp(), **payload.model_dump())

    async def fake_get_profile(session, *, user_id):
        return SimpleNamespace(
            id=1,
            user_id=user_id,
            monthly_salary=Decimal("5000.00"),
            emergency_reserve=Decimal("3000.00"),
            has_debt_default=False,
            risk_profile="moderate",
            created_at=_stamp(),
            updated_at=_stamp(),
        )

    monkeypatch.setattr(service, "upsert_financial_profile", fake_upsert_profile)
    monkeypatch.setattr(service, "get_financial_profile", fake_get_profile)

    with TestClient(app) as client:
        created = client.post(
            "/api/v1/financial/profile",
            json={
                "monthly_salary": "5000.00",
                "emergency_reserve": "3000.00",
                "has_debt_default": False,
                "risk_profile": "moderate",
            },
        )
        fetched = client.get("/api/v1/financial/profile")

    _clear_overrides()
    assert created.status_code == 201
    assert fetched.status_code == 200
    assert fetched.json()["risk_profile"] == "moderate"


def test_financial_diagnosis_authenticated(monkeypatch):
    _install_overrides()

    async def fake_diagnosis(session, *, user_id):
        return {
            "monthly_salary": Decimal("5000.00"),
            "total_expenses_30d": Decimal("2000.00"),
            "emergency_reserve": Decimal("10000.00"),
            "has_debt_default": False,
            "risk_profile": "moderate",
            "score": {
                "score": 88,
                "level": "healthy",
                "penalties": [],
                "recommendations": ["Manter disciplina orçamentária."],
            },
            "budget": {
                "method": "50/30/20",
                "committed_ratio": Decimal("0.4000"),
                "total_expenses_30d": Decimal("2000.00"),
                "investment_percentage": Decimal("0.20"),
                "investment_capacity": Decimal("1000.00"),
                "emergency_reserve_priority": False,
                "high_risk_allowed": True,
                "explanation": "Diagnóstico financeiro calculado.",
            },
        }

    monkeypatch.setattr(service, "calculate_financial_diagnosis", fake_diagnosis)

    with TestClient(app) as client:
        response = client.get("/api/v1/financial/diagnosis")

    _clear_overrides()
    assert response.status_code == 200
    assert response.json()["budget"]["method"] == "50/30/20"
