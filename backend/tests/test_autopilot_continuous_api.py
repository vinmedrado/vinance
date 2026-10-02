from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.auth.dependencies import get_current_user
from backend.app.continuous_autopilot import router as continuous_router
from backend.app.continuous_autopilot import service
from backend.app.core.database import get_session
from backend.app.financial_state import service as state_service
from backend.tests.test_autopilot_continuous_engine import NOW, _evaluate, _plan


app = FastAPI()
app.include_router(continuous_router.router, prefix="/api/v1")


async def _session_override():
    yield object()


async def _user_override():
    return SimpleNamespace(id=91)


app.dependency_overrides[get_session] = _session_override
app.dependency_overrides[get_current_user] = _user_override
client = TestClient(app)


def _decision() -> dict:
    value = _evaluate(None, _plan(plan_id=42))
    value.update({"continuous_decision_id": 51, "created_at": NOW})
    return value


def test_routes_are_canonical_and_do_not_expose_execution() -> None:
    paths = app.openapi()["paths"]
    expected = {
        "/api/v1/financial/households/{household_id}/continuous-autopilot": "get",
        "/api/v1/financial/households/{household_id}/continuous-autopilot/evaluate": "post",
        "/api/v1/financial/households/{household_id}/continuous-autopilot/history": "get",
        "/api/v1/financial/households/{household_id}/continuous-autopilot/history/{continuous_decision_id}": "get",
    }
    for path, method in expected.items():
        assert method in paths[path]
    assert all("execute" not in path and "trade" not in path for path in paths)


def test_current_evaluate_history_and_detail_are_private(monkeypatch) -> None:
    decision = _decision()

    async def current(*_args, **kwargs):
        assert kwargs == {"household_id": 10, "user_id": 91}
        return decision

    async def evaluate(*_args, **kwargs):
        assert kwargs["household_id"] == 10
        assert kwargs["user_id"] == 91
        assert kwargs["idempotency_key"] == "request-1"
        assert "as_of" not in kwargs
        assert "change_categories" not in kwargs
        return decision

    async def history(*_args, **kwargs):
        assert kwargs["limit"] == 5
        return {
            "items": [
                {
                    "continuous_decision_id": 51,
                    "household_id": 10,
                    "previous_action_plan_id": None,
                    "current_action_plan_id": 42,
                    "status": "UP_TO_DATE",
                    "materiality": "NONE",
                    "alert_decision": "NO_ALERT",
                    "title": "Seu plano está atualizado",
                    "summary": "Baseline criado.",
                    "change_count": 0,
                    "decision_fingerprint": decision["decision_fingerprint"],
                    "observed_at": NOW,
                    "generated_at": NOW,
                    "created_at": NOW,
                }
            ],
            "total": 1,
        }

    async def detail(*_args, **kwargs):
        assert kwargs["continuous_decision_id"] == 51
        return decision

    monkeypatch.setattr(service, "current_continuous_autopilot", current)
    monkeypatch.setattr(service, "evaluate_continuous_autopilot", evaluate)
    monkeypatch.setattr(service, "continuous_autopilot_history", history)
    monkeypatch.setattr(service, "get_continuous_autopilot_decision", detail)

    responses = [
        client.get("/api/v1/financial/households/10/continuous-autopilot"),
        client.post(
            "/api/v1/financial/households/10/continuous-autopilot/evaluate",
            headers={"Idempotency-Key": "request-1"},
            json={},
        ),
        client.get(
            "/api/v1/financial/households/10/continuous-autopilot/history?limit=5"
        ),
        client.get(
            "/api/v1/financial/households/10/continuous-autopilot/history/51"
        ),
    ]
    assert [response.status_code for response in responses] == [200, 200, 200, 200]
    assert all(response.headers["cache-control"] == "private, no-store" for response in responses)


def test_evaluate_requires_idempotency_key() -> None:
    response = client.post(
        "/api/v1/financial/households/10/continuous-autopilot/evaluate",
        json={},
    )
    assert response.status_code == 422


def test_evaluate_rejects_client_controlled_time_categories_and_reserved_key() -> None:
    controlled = client.post(
        "/api/v1/financial/households/10/continuous-autopilot/evaluate",
        headers={"Idempotency-Key": "request-controlled"},
        json={"as_of": NOW.isoformat(), "change_categories": ["MARKET_DATA"]},
    )
    reserved = client.post(
        "/api/v1/financial/households/10/continuous-autopilot/evaluate",
        headers={"Idempotency-Key": "continuous-scheduled:forged"},
        json={},
    )
    assert controlled.status_code == 422
    assert reserved.status_code == 422
    assert reserved.headers["cache-control"] == "private, no-store"


@pytest.mark.parametrize(
    ("error", "expected_status"),
    [
        (service.ContinuousAutopilotConflictError("conflict"), 409),
        (service.ContinuousAutopilotCooldownError(retry_after=47), 429),
        (service.ContinuousAutopilotUnavailableError("provider"), 503),
    ],
)
def test_evaluate_distinguishes_conflict_from_technical_failure(
    monkeypatch, error, expected_status
) -> None:
    async def failed(*_args, **_kwargs):
        raise error

    monkeypatch.setattr(service, "evaluate_continuous_autopilot", failed)
    response = client.post(
        "/api/v1/financial/households/10/continuous-autopilot/evaluate",
        headers={"Idempotency-Key": "request-error"},
        json={},
    )
    assert response.status_code == expected_status
    assert response.headers["cache-control"] == "private, no-store"
    if expected_status == 429:
        assert response.headers["retry-after"] == "47"
    elif expected_status == 503:
        assert response.headers["retry-after"] == "30"


def test_endpoint_requires_authentication() -> None:
    override = app.dependency_overrides.pop(get_current_user)
    try:
        response = client.get(
            "/api/v1/financial/households/10/continuous-autopilot"
        )
    finally:
        app.dependency_overrides[get_current_user] = override
    assert response.status_code == 401


@pytest.mark.parametrize(
    "error",
    [
        state_service.HouseholdNotFoundError("missing"),
        state_service.HouseholdPermissionError("private"),
        state_service.FinancialResourceNotFoundError("other household"),
    ],
)
def test_cross_household_failures_are_defensive_404(monkeypatch, error) -> None:
    async def denied(*_args, **_kwargs):
        raise error

    monkeypatch.setattr(service, "current_continuous_autopilot", denied)
    response = client.get("/api/v1/financial/households/999/continuous-autopilot")
    assert response.status_code == 404
    assert response.json() == {"detail": "Recurso financeiro não encontrado"}
    assert response.headers["cache-control"] == "private, no-store"
