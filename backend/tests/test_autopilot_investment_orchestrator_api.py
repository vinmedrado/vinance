from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.auth.dependencies import get_current_user
from backend.app.auth.models import User
from backend.app.core.database import get_session
from backend.app.financial_state import service as state_service
from backend.app.investment_orchestrator import router as orchestration_router
from backend.tests.test_autopilot_investment_orchestrator_service import (
    NOW,
    _orchestration,
)


app = FastAPI()
app.include_router(orchestration_router.router, prefix="/api/v1")


async def _fake_user() -> User:
    return User(
        id=91,
        email="orchestration-api@example.com",
        full_name="Orchestration API",
        hashed_password="unused",
        is_active=True,
    )


async def _fake_session():
    yield object()


def _authenticated() -> None:
    app.dependency_overrides[get_current_user] = _fake_user
    app.dependency_overrides[get_session] = _fake_session


def _restore() -> None:
    app.dependency_overrides.clear()


def _response(frozen: bool = False):
    result = _orchestration()
    if frozen:
        result["orchestration_id"] = 31
        result["created_at"] = NOW
    return result


def test_five_canonical_routes_are_registered_and_authenticated() -> None:
    expected = {
        "/api/v1/financial/households/{household_id}/investment-orchestration": "get",
        "/api/v1/financial/households/{household_id}/investment-orchestration/from-allocation/{allocation_id}": "get",
        "/api/v1/financial/households/{household_id}/investment-orchestration/decisions": "post",
        "/api/v1/financial/households/{household_id}/investment-orchestration/history": "get",
        "/api/v1/financial/households/{household_id}/investment-orchestration/history/{orchestration_id}": "get",
    }
    paths = app.openapi()["paths"]
    for path, method in expected.items():
        assert method in paths[path]
        assert paths[path][method]["security"] == [{"HTTPBearer": []}]


def test_current_forwards_identity_and_disables_cache(monkeypatch) -> None:
    captured = {}

    async def current(*_args, **kwargs):
        captured.update(kwargs)
        return _response()

    monkeypatch.setattr(
        orchestration_router.service, "current_investment_orchestration", current
    )
    _authenticated()
    try:
        with TestClient(app) as client:
            response = client.get(
                "/api/v1/financial/households/10/investment-orchestration"
            )
        assert response.status_code == 200
        assert response.headers["cache-control"] == "private, no-store"
        assert response.json()["engine_version"] == "investment-orchestrator-v1"
        assert captured == {"household_id": 10, "user_id": 91}
    finally:
        _restore()


def test_from_allocation_forwards_exact_chain_identity(monkeypatch) -> None:
    captured = {}

    async def replay(*_args, **kwargs):
        captured.update(kwargs)
        return _response()

    monkeypatch.setattr(
        orchestration_router.service,
        "investment_orchestration_from_allocation_decision",
        replay,
    )
    _authenticated()
    try:
        with TestClient(app) as client:
            response = client.get(
                "/api/v1/financial/households/10/investment-orchestration/from-allocation/23"
            )
        assert response.status_code == 200
        assert captured == {"household_id": 10, "allocation_id": 23, "user_id": 91}
    finally:
        _restore()


def test_freeze_forwards_household_scoped_idempotency(monkeypatch) -> None:
    captured = {}

    async def freeze(*_args, **kwargs):
        captured.update(kwargs)
        return _response(frozen=True)

    monkeypatch.setattr(
        orchestration_router.service,
        "create_investment_orchestration_decision",
        freeze,
    )
    _authenticated()
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/financial/households/10/investment-orchestration/decisions",
                headers={"Idempotency-Key": "orchestration-request"},
            )
        assert response.status_code == 201
        assert response.json()["orchestration_id"] == 31
        assert captured == {
            "household_id": 10,
            "user_id": 91,
            "idempotency_key": "orchestration-request",
        }
    finally:
        _restore()


def test_history_and_detail_do_not_enumerate_other_households(monkeypatch) -> None:
    calls = []

    async def history(*_args, **kwargs):
        calls.append(("history", kwargs))
        output = _response(frozen=True)
        return {
            "items": [
                {
                    "orchestration_id": 31,
                    "household_id": 10,
                    "financial_state_snapshot_id": 7,
                    "financial_policy_decision_id": 17,
                    "capital_allocation_decision_id": 23,
                    "engine_version": output["engine_version"],
                    "rules_version": output["rules_version"],
                    "status": output["status"],
                    "currency": output["currency"],
                    "investment_budget": output["investment_budget"],
                    "suggested_capital": output["suggested_capital"],
                    "remaining_investment_cash": output["remaining_investment_cash"],
                    "decision_fingerprint": output["decision_fingerprint"],
                    "generated_at": NOW,
                    "created_at": NOW,
                }
            ],
            "total": 1,
        }

    async def detail(*_args, **kwargs):
        calls.append(("detail", kwargs))
        return _response(frozen=True)

    monkeypatch.setattr(
        orchestration_router.service, "investment_orchestration_history", history
    )
    monkeypatch.setattr(
        orchestration_router.service,
        "get_investment_orchestration_decision",
        detail,
    )
    _authenticated()
    try:
        with TestClient(app) as client:
            history_response = client.get(
                "/api/v1/financial/households/10/investment-orchestration/history",
                params={"limit": 5, "offset": 2},
            )
            detail_response = client.get(
                "/api/v1/financial/households/10/investment-orchestration/history/31"
            )
        assert history_response.status_code == 200
        assert detail_response.status_code == 200
        assert calls == [
            ("history", {"household_id": 10, "user_id": 91, "limit": 5, "offset": 2}),
            ("detail", {"household_id": 10, "orchestration_id": 31, "user_id": 91}),
        ]
    finally:
        _restore()


def test_cross_household_is_defensive_404(monkeypatch) -> None:
    async def not_owned(*_args, **_kwargs):
        raise state_service.HouseholdNotFoundError("not owned")

    monkeypatch.setattr(
        orchestration_router.service, "current_investment_orchestration", not_owned
    )
    _authenticated()
    try:
        with TestClient(app) as client:
            response = client.get(
                "/api/v1/financial/households/999/investment-orchestration"
            )
        assert response.status_code == 404
        assert response.json()["detail"] == "Recurso financeiro não encontrado"
    finally:
        _restore()


def test_anonymous_user_cannot_read_or_freeze() -> None:
    app.dependency_overrides[get_session] = _fake_session
    try:
        with TestClient(app) as client:
            read = client.get(
                "/api/v1/financial/households/10/investment-orchestration"
            )
            freeze = client.post(
                "/api/v1/financial/households/10/investment-orchestration/decisions"
            )
        assert read.status_code in {401, 403}
        assert freeze.status_code in {401, 403}
    finally:
        _restore()
