from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from backend.app.auth.dependencies import get_current_user
from backend.app.auth.models import User
from backend.app.capital_allocation import router as allocation_router
from backend.app.capital_allocation.engine import calculate_capital_allocation
from backend.app.core.database import get_session
from backend.app.financial_policy.engine import calculate_financial_policy
from backend.app.financial_state import service as state_service
from backend.app.financial_state.engine import calculate_financial_state
from backend.app.main import app
from backend.tests.test_autopilot_financial_policy_engine import _complete_inputs


NOW = datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc)


async def _fake_user() -> User:
    return User(
        id=91,
        email="allocation-api@example.com",
        full_name="Allocation API",
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


def _allocation_response(*, frozen: bool = False) -> dict:
    inputs = _complete_inputs()
    state = calculate_financial_state(inputs, evaluated_at=NOW)
    if frozen:
        state["snapshot_id"] = 7
    policy = calculate_financial_policy(state, normalized_inputs=inputs)
    if frozen:
        policy["policy_id"] = 17
        policy["financial_state_snapshot_id"] = 7
    allocation = calculate_capital_allocation(state, policy)
    if frozen:
        allocation["allocation_id"] = 23
        allocation["created_at"] = NOW
    return allocation


def test_capital_allocation_api_is_registered_and_authenticated() -> None:
    expected = {
        "/api/v1/financial/households/{household_id}/capital-allocation": "get",
        (
            "/api/v1/financial/households/{household_id}/capital-allocation/"
            "from-policy/{policy_id}"
        ): "get",
        "/api/v1/financial/households/{household_id}/capital-allocation/decisions": "post",
        "/api/v1/financial/households/{household_id}/capital-allocation/history": "get",
        (
            "/api/v1/financial/households/{household_id}/capital-allocation/"
            "history/{allocation_id}"
        ): "get",
    }
    paths = app.openapi()["paths"]
    for path, method in expected.items():
        assert method in paths[path]
        assert paths[path][method]["security"] == [{"HTTPBearer": []}]


def test_current_allocation_forwards_identity_and_disables_cache(monkeypatch) -> None:
    captured = {}

    async def current(*_args, **kwargs):
        captured.update(kwargs)
        return _allocation_response()

    monkeypatch.setattr(allocation_router.service, "current_capital_allocation", current)
    previous = _authenticated()
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/financial/households/10/capital-allocation")
        assert response.status_code == 200
        assert response.headers["cache-control"] == "private, no-store"
        assert response.json()["engine_version"] == "capital-allocation-v1"
        assert captured == {"household_id": 10, "user_id": 91}
    finally:
        _restore(previous)


def test_replay_forwards_exact_policy_identity(monkeypatch) -> None:
    captured = {}

    async def replay(*_args, **kwargs):
        captured.update(kwargs)
        return _allocation_response(frozen=True)

    monkeypatch.setattr(
        allocation_router.service, "capital_allocation_from_policy_decision", replay
    )
    previous = _authenticated()
    try:
        with TestClient(app) as client:
            response = client.get(
                "/api/v1/financial/households/10/capital-allocation/from-policy/17"
            )
        assert response.status_code == 200
        assert response.headers["cache-control"] == "private, no-store"
        assert response.json()["financial_policy_id"] == 17
        assert captured == {"household_id": 10, "policy_id": 17, "user_id": 91}
    finally:
        _restore(previous)


def test_cross_household_allocation_is_indistinguishable_from_missing(monkeypatch) -> None:
    async def not_owned(*_args, **_kwargs):
        raise state_service.HouseholdNotFoundError("not owned")

    monkeypatch.setattr(allocation_router.service, "current_capital_allocation", not_owned)
    previous = _authenticated()
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/financial/households/999/capital-allocation")
        assert response.status_code == 404
        assert response.json()["error"] == "Recurso financeiro não encontrado"
    finally:
        _restore(previous)


def test_anonymous_user_cannot_read_or_freeze_allocation() -> None:
    previous = dict(app.dependency_overrides)
    try:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides[get_session] = _fake_session
        with TestClient(app) as client:
            read = client.get("/api/v1/financial/households/10/capital-allocation")
            write = client.post(
                "/api/v1/financial/households/10/capital-allocation/decisions"
            )
        assert read.status_code == 401
        assert write.status_code == 401
    finally:
        _restore(previous)


def test_freeze_forwards_idempotency_and_returns_full_chain(monkeypatch) -> None:
    captured = {}

    async def freeze(*_args, **kwargs):
        captured.update(kwargs)
        return _allocation_response(frozen=True)

    monkeypatch.setattr(
        allocation_router.service, "create_capital_allocation_decision", freeze
    )
    previous = _authenticated()
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/financial/households/10/capital-allocation/decisions",
                headers={"Idempotency-Key": "allocation-request-1"},
            )
        assert response.status_code == 201
        assert response.json()["allocation_id"] == 23
        assert response.json()["financial_state_snapshot_id"] == 7
        assert response.json()["financial_policy_id"] == 17
        assert response.headers["cache-control"] == "private, no-store"
        assert captured == {
            "household_id": 10,
            "user_id": 91,
            "idempotency_key": "allocation-request-1",
        }
    finally:
        _restore(previous)


def test_freeze_rejects_invalid_idempotency_header_before_service(monkeypatch) -> None:
    async def must_not_run(*_args, **_kwargs):
        raise AssertionError("invalid header must not reach domain service")

    monkeypatch.setattr(
        allocation_router.service, "create_capital_allocation_decision", must_not_run
    )
    previous = _authenticated()
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/financial/households/10/capital-allocation/decisions",
                headers={"Idempotency-Key": "x" * 129},
            )
        assert response.status_code == 422
    finally:
        _restore(previous)


def test_history_and_detail_forward_identity_without_recalculation(monkeypatch) -> None:
    calls = []
    payload = _allocation_response(frozen=True)

    async def history(*_args, **kwargs):
        calls.append(("history", kwargs))
        return {
            "items": [
                {
                    "allocation_id": 23,
                    "household_id": 10,
                    "financial_state_snapshot_id": 7,
                    "financial_policy_id": 17,
                    "engine_version": payload["engine_version"],
                    "rules_version": payload["rules_version"],
                    "allocation_period": payload["allocation_period"],
                    "allocation_status": payload["allocation_status"],
                    "currency": payload["currency"],
                    "allocatable_capital": payload["allocatable_capital"],
                    "allocated_capital": payload["allocated_capital"],
                    "investment_bucket_amount": payload["investment_bucket_amount"],
                    "decision_fingerprint": payload["decision_fingerprint"],
                    "generated_at": payload["generated_at"],
                    "created_at": NOW,
                }
            ],
            "total": 1,
        }

    async def detail(*_args, **kwargs):
        calls.append(("detail", kwargs))
        return payload

    monkeypatch.setattr(allocation_router.service, "capital_allocation_history", history)
    monkeypatch.setattr(
        allocation_router.service, "get_capital_allocation_decision", detail
    )
    previous = _authenticated()
    try:
        with TestClient(app) as client:
            history_response = client.get(
                "/api/v1/financial/households/10/capital-allocation/history",
                params={"limit": 5, "offset": 2},
            )
            detail_response = client.get(
                "/api/v1/financial/households/10/capital-allocation/history/23"
            )
        assert history_response.status_code == 200
        assert history_response.headers["cache-control"] == "private, no-store"
        assert history_response.json()["total"] == 1
        assert detail_response.status_code == 200
        assert detail_response.headers["cache-control"] == "private, no-store"
        assert calls == [
            (
                "history",
                {"household_id": 10, "user_id": 91, "limit": 5, "offset": 2},
            ),
            (
                "detail",
                {"household_id": 10, "allocation_id": 23, "user_id": 91},
            ),
        ]
    finally:
        _restore(previous)


def test_validation_error_is_exposed_without_leaking_another_household(monkeypatch) -> None:
    async def invalid(*_args, **_kwargs):
        raise state_service.FinancialStateValidationError("source chain mismatch")

    monkeypatch.setattr(
        allocation_router.service, "capital_allocation_from_policy_decision", invalid
    )
    previous = _authenticated()
    try:
        with TestClient(app) as client:
            response = client.get(
                "/api/v1/financial/households/10/capital-allocation/from-policy/17"
            )
        assert response.status_code == 422
        assert response.json()["error"] == "source chain mismatch"
    finally:
        _restore(previous)
