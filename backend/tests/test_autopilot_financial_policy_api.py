from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from fastapi.testclient import TestClient

from backend.app.auth.dependencies import get_current_user
from backend.app.auth.models import User
from backend.app.core.database import get_session
from backend.app.financial_policy import router as policy_router
from backend.app.financial_policy.engine import calculate_financial_policy
from backend.app.financial_state import service as state_service
from backend.app.main import app


NOW = datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc)


async def _fake_user() -> User:
    return User(
        id=91,
        email="policy-api@example.com",
        full_name="Policy API",
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


def _policy_response() -> dict:
    state = {
        "household_id": 10,
        "engine_version": "household-financial-state-v1",
        "evaluated_at": NOW,
        "metrics": {
            "recurring_monthly_income": Decimal("100"),
            "non_recurring_income": Decimal("0"),
            "total_income": Decimal("100"),
            "fixed_expenses": Decimal("25"),
            "variable_expenses": Decimal("25"),
            "total_expenses": Decimal("50"),
            "cash_flow": Decimal("50"),
            "disposable_income": Decimal("50"),
            "savings_capacity": Decimal("50"),
            "investment_capacity": Decimal("50"),
            "total_assets": Decimal("150"),
            "total_liabilities": Decimal("0"),
            "net_worth": Decimal("150"),
            "emergency_reserve": Decimal("150"),
            "emergency_reserve_months": Decimal("3"),
            "monthly_debt_service": Decimal("0"),
            "debt_to_income": Decimal("0"),
            "debt_service_ratio": Decimal("0"),
            "savings_rate": Decimal("50"),
            "asset_distribution": {},
        },
        "goals": [],
        "member_views": [],
        "data_quality": "PARTIAL",
        "confidence": 92,
        "missing_fields": ["goals"],
        "inconsistencies": [],
        "stale_fields": [],
        "provenance": {},
    }
    context = {
        "household": {"id": 10},
        "members": [{"user_id": 91, "status": "ACTIVE"}],
        "assets": [
            {
                "id": 1,
                "household_id": 10,
                "user_id": 91,
                "ownership_scope": "PERSONAL",
                "currency": "BRL",
                "status": "ACTIVE",
            }
        ],
        "liabilities": [],
        "goals": [],
    }
    return calculate_financial_policy(state, normalized_inputs=context)


def test_policy_api_contract_is_registered_and_authenticated() -> None:
    expected = {
        "/api/v1/financial/households/{household_id}/financial-policy",
        (
            "/api/v1/financial/households/{household_id}/financial-policy/"
            "from-state-snapshot/{snapshot_id}"
        ),
        "/api/v1/financial/households/{household_id}/financial-policy/decisions",
        "/api/v1/financial/households/{household_id}/financial-policy/history",
        (
            "/api/v1/financial/households/{household_id}/financial-policy/"
            "history/{policy_id}"
        ),
    }
    paths = app.openapi()["paths"]
    for path in expected:
        method = "post" if path.endswith("/decisions") else "get"
        assert method in paths[path]
        assert paths[path][method]["security"] == [{"HTTPBearer": []}]


def test_current_policy_forwards_authenticated_identity_and_disables_cache(monkeypatch) -> None:
    captured: dict = {}

    async def current(*_args, **kwargs):
        captured.update(kwargs)
        return _policy_response()

    monkeypatch.setattr(policy_router.service, "current_financial_policy", current)
    previous = _authenticated()
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/financial/households/10/financial-policy")
        assert response.status_code == 200
        assert response.headers["cache-control"] == "private, no-store"
        assert response.json()["engine_version"] == "financial-policy-v1"
        assert captured == {"household_id": 10, "user_id": 91}
    finally:
        _restore(previous)


def test_snapshot_replay_forwards_household_snapshot_and_user(monkeypatch) -> None:
    captured: dict = {}

    async def replay(*_args, **kwargs):
        captured.update(kwargs)
        payload = _policy_response()
        payload["source_financial_state"]["snapshot_id"] = 7
        return payload

    monkeypatch.setattr(
        policy_router.service,
        "financial_policy_from_state_snapshot",
        replay,
    )
    previous = _authenticated()
    try:
        with TestClient(app) as client:
            response = client.get(
                "/api/v1/financial/households/10/financial-policy/"
                "from-state-snapshot/7"
            )
        assert response.status_code == 200
        assert response.headers["cache-control"] == "private, no-store"
        assert response.json()["source_financial_state"]["snapshot_id"] == 7
        assert captured == {"household_id": 10, "snapshot_id": 7, "user_id": 91}
    finally:
        _restore(previous)


def test_cross_household_policy_is_indistinguishable_from_missing(monkeypatch) -> None:
    async def not_owned(*_args, **_kwargs):
        raise state_service.HouseholdNotFoundError("not owned")

    monkeypatch.setattr(policy_router.service, "current_financial_policy", not_owned)
    previous = _authenticated()
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/financial/households/999/financial-policy")
        assert response.status_code == 404
        assert response.json()["error"] == "Recurso financeiro não encontrado"
    finally:
        _restore(previous)


def test_anonymous_user_cannot_read_financial_policy() -> None:
    previous = dict(app.dependency_overrides)
    try:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides[get_session] = _fake_session
        with TestClient(app) as client:
            response = client.get("/api/v1/financial/households/10/financial-policy")
        assert response.status_code == 401
    finally:
        _restore(previous)


def test_policy_freeze_forwards_idempotency_and_returns_auditable_identity(
    monkeypatch,
) -> None:
    captured: dict = {}

    async def freeze(*_args, **kwargs):
        captured.update(kwargs)
        payload = _policy_response()
        payload.update(
            {
                "policy_id": 17,
                "financial_state_snapshot_id": 7,
                "created_at": NOW,
            }
        )
        return payload

    monkeypatch.setattr(policy_router.service, "create_policy_decision", freeze)
    previous = _authenticated()
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/financial/households/10/financial-policy/decisions",
                headers={"Idempotency-Key": "policy-request-1"},
            )
        assert response.status_code == 201
        assert response.json()["policy_id"] == 17
        assert response.json()["financial_state_snapshot_id"] == 7
        assert captured == {
            "household_id": 10,
            "user_id": 91,
            "idempotency_key": "policy-request-1",
        }
    finally:
        _restore(previous)


def test_policy_history_and_detail_forward_identity_without_recalculation(
    monkeypatch,
) -> None:
    calls: list[tuple[str, dict]] = []
    payload = _policy_response()
    payload.update(
        {
            "policy_id": 17,
            "financial_state_snapshot_id": 7,
            "created_at": NOW,
        }
    )

    async def history(*_args, **kwargs):
        calls.append(("history", kwargs))
        return {
            "items": [
                {
                    "policy_id": 17,
                    "household_id": 10,
                    "financial_state_snapshot_id": 7,
                    "engine_version": payload["engine_version"],
                    "rules_version": payload["rules_version"],
                    "policy_state": payload["policy_state"],
                    "investment_readiness": payload["investment_readiness"],
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

    monkeypatch.setattr(policy_router.service, "policy_decision_history", history)
    monkeypatch.setattr(policy_router.service, "get_policy_decision", detail)
    previous = _authenticated()
    try:
        with TestClient(app) as client:
            history_response = client.get(
                "/api/v1/financial/households/10/financial-policy/history",
                params={"limit": 5, "offset": 2},
            )
            detail_response = client.get(
                "/api/v1/financial/households/10/financial-policy/history/17"
            )
        assert history_response.status_code == 200
        assert history_response.headers["cache-control"] == "private, no-store"
        assert history_response.json()["total"] == 1
        assert detail_response.status_code == 200
        assert detail_response.headers["cache-control"] == "private, no-store"
        assert detail_response.json()["policy_id"] == 17
        assert calls == [
            (
                "history",
                {
                    "household_id": 10,
                    "user_id": 91,
                    "limit": 5,
                    "offset": 2,
                },
            ),
            (
                "detail",
                {"household_id": 10, "policy_id": 17, "user_id": 91},
            ),
        ]
    finally:
        _restore(previous)


def test_cross_household_policy_history_is_defensively_not_found(monkeypatch) -> None:
    async def not_owned(*_args, **_kwargs):
        raise state_service.HouseholdNotFoundError("not owned")

    monkeypatch.setattr(policy_router.service, "policy_decision_history", not_owned)
    previous = _authenticated()
    try:
        with TestClient(app) as client:
            response = client.get(
                "/api/v1/financial/households/999/financial-policy/history"
            )
        assert response.status_code == 404
        assert response.json()["error"] == "Recurso financeiro não encontrado"
    finally:
        _restore(previous)


def test_anonymous_user_cannot_freeze_financial_policy() -> None:
    previous = dict(app.dependency_overrides)
    try:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides[get_session] = _fake_session
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/financial/households/10/financial-policy/decisions"
            )
        assert response.status_code == 401
    finally:
        _restore(previous)
