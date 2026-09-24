from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.action_plan import router as action_plan_router
from backend.app.auth.dependencies import get_current_user
from backend.app.auth.models import User
from backend.app.core.database import get_session
from backend.app.financial_state import service as state_service
from backend.tests.test_autopilot_action_plan_engine import _plan
from backend.tests.test_autopilot_investment_orchestrator_engine import NOW


app = FastAPI()
app.include_router(action_plan_router.router, prefix="/api/v1")


async def _fake_user() -> User:
    return User(
        id=95,
        email="action-plan-api@example.com",
        full_name="Action Plan API",
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


def _response(*, frozen: bool = False):
    result = _plan()
    if frozen:
        result.update(
            {
                "action_plan_id": 41,
                "financial_state_snapshot_id": 7,
                "financial_policy_decision_id": 17,
                "capital_allocation_decision_id": 23,
                "investment_orchestration_decision_id": 31,
                "created_at": NOW,
            }
        )
    return result


def test_five_routes_are_registered_and_authenticated() -> None:
    expected = {
        "/api/v1/financial/households/{household_id}/action-plan": "get",
        "/api/v1/financial/households/{household_id}/action-plan/from-orchestration/{orchestration_id}": "get",
        "/api/v1/financial/households/{household_id}/action-plan/decisions": "post",
        "/api/v1/financial/households/{household_id}/action-plan/history": "get",
        "/api/v1/financial/households/{household_id}/action-plan/history/{action_plan_id}": "get",
    }
    paths = app.openapi()["paths"]
    for path, method in expected.items():
        assert method in paths[path]
        assert paths[path][method]["security"] == [{"HTTPBearer": []}]


def test_current_and_replay_forward_exact_identity_and_disable_cache(monkeypatch) -> None:
    calls = []

    async def current(*_args, **kwargs):
        calls.append(("current", kwargs))
        return _response()

    async def replay(*_args, **kwargs):
        calls.append(("replay", kwargs))
        return _response()

    monkeypatch.setattr(action_plan_router.service, "current_action_plan", current)
    monkeypatch.setattr(
        action_plan_router.service,
        "action_plan_from_orchestration_decision",
        replay,
    )
    _authenticated()
    try:
        with TestClient(app) as client:
            live = client.get("/api/v1/financial/households/10/action-plan")
            frozen = client.get(
                "/api/v1/financial/households/10/action-plan/from-orchestration/31"
            )
        assert live.status_code == frozen.status_code == 200
        assert live.headers["cache-control"] == "private, no-store"
        assert frozen.headers["cache-control"] == "private, no-store"
        assert calls == [
            ("current", {"household_id": 10, "user_id": 95}),
            (
                "replay",
                {"household_id": 10, "orchestration_id": 31, "user_id": 95},
            ),
        ]
    finally:
        _restore()


def test_freeze_forwards_household_scoped_idempotency(monkeypatch) -> None:
    captured = {}

    async def freeze(*_args, **kwargs):
        captured.update(kwargs)
        return _response(frozen=True)

    monkeypatch.setattr(
        action_plan_router.service, "create_action_plan_decision", freeze
    )
    _authenticated()
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/financial/households/10/action-plan/decisions",
                headers={"Idempotency-Key": "action-plan-request"},
            )
        assert response.status_code == 201
        assert response.json()["action_plan_id"] == 41
        assert captured == {
            "household_id": 10,
            "user_id": 95,
            "idempotency_key": "action-plan-request",
        }
    finally:
        _restore()


def test_history_and_detail_use_frozen_payload(monkeypatch) -> None:
    calls = []
    output = _response(frozen=True)

    async def history(*_args, **kwargs):
        calls.append(("history", kwargs))
        return {
            "items": [
                {
                    "action_plan_id": 41,
                    "household_id": 10,
                    "financial_state_snapshot_id": 7,
                    "financial_policy_decision_id": 17,
                    "capital_allocation_decision_id": 23,
                    "investment_orchestration_decision_id": 31,
                    "engine_version": output["engine_version"],
                    "rules_version": output["rules_version"],
                    "status": output["status"],
                    "currency": output["currency"],
                    "period": output["period"],
                    "primary_action": output["summary"]["primary_action"],
                    "action_titles": [
                        item["title"] for item in output["actions"][:3]
                    ],
                    "action_count": output["summary"]["action_count"],
                    "investment_budget": output["summary"][
                        "authorized_investment_capital"
                    ],
                    "total_financial_actions": output["total_financial_actions"],
                    "total_investment_actions": output["total_investment_actions"],
                    "total_hold_cash": output["total_hold_cash"],
                    "decision_fingerprint": output["decision_fingerprint"],
                    "generated_at": NOW,
                    "created_at": NOW,
                }
            ],
            "total": 1,
        }

    async def detail(*_args, **kwargs):
        calls.append(("detail", kwargs))
        return output

    monkeypatch.setattr(action_plan_router.service, "action_plan_history", history)
    monkeypatch.setattr(
        action_plan_router.service, "get_action_plan_decision", detail
    )
    _authenticated()
    try:
        with TestClient(app) as client:
            history_response = client.get(
                "/api/v1/financial/households/10/action-plan/history",
                params={"limit": 5, "offset": 2},
            )
            detail_response = client.get(
                "/api/v1/financial/households/10/action-plan/history/41"
            )
        assert history_response.status_code == detail_response.status_code == 200
        assert calls == [
            ("history", {"household_id": 10, "user_id": 95, "limit": 5, "offset": 2}),
            ("detail", {"household_id": 10, "action_plan_id": 41, "user_id": 95}),
        ]
    finally:
        _restore()


def test_cross_household_is_defensive_404(monkeypatch) -> None:
    async def not_owned(*_args, **_kwargs):
        raise state_service.HouseholdPermissionError("not owned")

    monkeypatch.setattr(action_plan_router.service, "current_action_plan", not_owned)
    _authenticated()
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/financial/households/999/action-plan")
        assert response.status_code == 404
        assert response.headers["cache-control"] == "private, no-store"
        assert response.json()["detail"] == "Recurso financeiro não encontrado"
    finally:
        _restore()


def test_every_persisted_route_hides_cross_household_resources(monkeypatch) -> None:
    async def not_owned(*_args, **_kwargs):
        raise state_service.HouseholdPermissionError("not owned")

    for name in (
        "action_plan_from_orchestration_decision",
        "create_action_plan_decision",
        "action_plan_history",
        "get_action_plan_decision",
    ):
        monkeypatch.setattr(action_plan_router.service, name, not_owned)
    _authenticated()
    try:
        with TestClient(app) as client:
            responses = (
                client.get(
                    "/api/v1/financial/households/999/action-plan/from-orchestration/31"
                ),
                client.post(
                    "/api/v1/financial/households/999/action-plan/decisions"
                ),
                client.get(
                    "/api/v1/financial/households/999/action-plan/history"
                ),
                client.get(
                    "/api/v1/financial/households/999/action-plan/history/41"
                ),
            )
        assert all(response.status_code == 404 for response in responses)
        assert all(
            response.headers["cache-control"] == "private, no-store"
            for response in responses
        )
    finally:
        _restore()


def test_anonymous_user_cannot_read_or_freeze() -> None:
    app.dependency_overrides[get_session] = _fake_session
    try:
        with TestClient(app) as client:
            read = client.get("/api/v1/financial/households/10/action-plan")
            freeze = client.post(
                "/api/v1/financial/households/10/action-plan/decisions"
            )
        assert read.status_code in {401, 403}
        assert freeze.status_code in {401, 403}
    finally:
        _restore()
