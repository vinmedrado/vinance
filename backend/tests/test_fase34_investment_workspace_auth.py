from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.auth.dependencies import get_current_user
from backend.app.auth.models import User
from backend.app.core.database import get_session
from backend.app.intelligence import router as intelligence_router
from backend.app.main import app


async def _fake_user():
    return User(id=34, email="fase34@test.local", full_name="Fase 34", hashed_password="x", is_active=True)


async def _fake_session():
    yield object()


def test_budget_advisor_rejeita_acesso_anonimo():
    previous = dict(app.dependency_overrides)
    try:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides[get_session] = _fake_session
        with TestClient(app) as client:
            response = client.get(
                "/api/intelligence/budget-advisor",
                params={"budget": 300, "market": "FII", "profile": "CONSERVATIVE", "explain": "true"},
            )
        assert response.status_code == 401
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)


def test_budget_advisor_rejeita_bearer_invalido_sem_consultar_dados():
    previous = dict(app.dependency_overrides)
    try:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides[get_session] = _fake_session
        with TestClient(app) as client:
            response = client.get(
                "/api/intelligence/budget-advisor",
                params={"budget": 300, "market": "FII", "profile": "CONSERVATIVE", "explain": "true"},
                headers={"Authorization": "Bearer token-invalido-fase-34"},
            )
        assert response.status_code == 401
        assert response.json()["error"] == "Invalid token"
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)


def test_budget_advisor_autenticado_preserva_fluxo_explicado(monkeypatch):
    previous = dict(app.dependency_overrides)
    calls: dict[str, object] = {}

    async def fake_explained(session, **kwargs):
        calls.update(kwargs)
        return {"best_recommendation": None, "alternatives": [], "budget": 300, "market": "FII", "profile": "CONSERVATIVE"}

    monkeypatch.setattr(intelligence_router, "build_explained_budget_recommendations", fake_explained)
    try:
        app.dependency_overrides[get_current_user] = _fake_user
        app.dependency_overrides[get_session] = _fake_session
        with TestClient(app) as client:
            response = client.get(
                "/api/intelligence/budget-advisor",
                params={"budget": 300, "market": "FII", "profile": "CONSERVATIVE", "explain": "true"},
            )
        assert response.status_code == 200
        assert calls["budget"] == 300
        assert calls["market"] == "FII"
        assert calls["profile"] == "CONSERVATIVE"
        assert calls["limit"] == 20
        assert calls["include_warnings"] is False
        assert calls["trend_filter"] is None
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)
