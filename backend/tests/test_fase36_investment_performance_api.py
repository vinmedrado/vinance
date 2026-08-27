from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from backend.app.auth.dependencies import get_current_user
from backend.app.auth.models import User
from backend.app.core.database import get_session
from backend.app.investment_performance import router as performance_router
from backend.app.main import app


DECISION_ID = "36000000-0000-4000-8000-000000000001"
UTC_NOW = datetime(2026, 8, 26, 12, 0, tzinfo=timezone.utc)


def _empty_summary(**overrides):
    values = {
        "as_of": UTC_NOW,
        "selected_horizon": None,
        "total_decisions": 0,
        "eligible_decisions": 0,
        "evaluated": 0,
        "pending": 0,
        "average_return_pct": None,
        "median_return_pct": None,
        "positive_pct": None,
        "negative_pct": None,
        "directional_accuracy_pct": None,
        "directional_sample": 0,
        "by_horizon": [],
        "by_action": [],
        "by_asset": [],
        "by_risk": [],
        "by_confidence": [],
        "by_score_band": [],
        "by_profile": [],
        "by_rule_version": [],
        "by_recommendation_engine_version": [],
        "by_score_version": [],
        "by_guardrail_version": [],
        "by_version_cohort": [],
        "mixed_versions": False,
        "calibration": [],
        "calibration_summary": {
            "monotonic_directional_accuracy": None,
            "high_low_separation_pct": None,
            "interpretation": "INSUFFICIENT_SAMPLE",
        },
        "timeline": [],
    }
    values.update(overrides)
    return values


def _detail(**overrides):
    values = {
        "decision_id": DECISION_ID,
        "asset": "PETR4",
        "action": "BUY",
        "decision_created_at": UTC_NOW,
        "risk_level": "LOW",
        "confidence": "90",
        "trend": "UPTREND",
        "recommendation_score": "85",
        "investor_profile": "MODERATE",
        "rule_version": "investment-decision-presentation-v1",
        "recommendation_engine_version": "budget-advisor-v1",
        "score_version": "vinance_score_v1",
        "guardrail_version": "vinance_guardrail_v1",
        "reference_price": "100",
        "reference_price_timestamp": UTC_NOW,
        "price_source": "decision_snapshot",
        "evaluations": [],
        "pending_horizons": ["1d", "7d", "30d"],
        "eligible_pending_horizons": [],
        "immature_horizons": ["1d", "7d", "30d"],
    }
    values.update(overrides)
    return values


async def _fake_user():
    return User(
        id=36,
        email="fase36@test.local",
        full_name="Fase 36",
        hashed_password="x",
        is_active=True,
    )


async def _fake_session():
    yield object()


def _authenticated_overrides():
    previous = dict(app.dependency_overrides)
    app.dependency_overrides[get_current_user] = _fake_user
    app.dependency_overrides[get_session] = _fake_session
    return previous


def _restore(previous):
    app.dependency_overrides.clear()
    app.dependency_overrides.update(previous)


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/investments/performance",
        f"/api/v1/investments/decisions/{DECISION_ID}/performance",
    ],
)
def test_endpoints_rejeitam_anonimo_com_401(path):
    previous = dict(app.dependency_overrides)
    try:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides[get_session] = _fake_session
        with TestClient(app) as client:
            response = client.get(path)
        assert response.status_code == 401
    finally:
        _restore(previous)


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/investments/performance",
        f"/api/v1/investments/decisions/{DECISION_ID}/performance",
    ],
)
def test_endpoints_rejeitam_token_invalido_com_401(path):
    previous = dict(app.dependency_overrides)
    try:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides[get_session] = _fake_session
        with TestClient(app) as client:
            response = client.get(path, headers={"Authorization": "Bearer token-invalido"})
        assert response.status_code == 401
        assert response.json()["error"] == "Invalid token"
    finally:
        _restore(previous)


def test_summary_encaminha_owner_e_todos_os_filtros_seguros(monkeypatch):
    captured = {}

    async def fake_summary(_session, **kwargs):
        captured.update(kwargs)
        return _empty_summary(selected_horizon=kwargs["horizon"])

    monkeypatch.setattr(performance_router, "get_performance_summary", fake_summary)
    previous = _authenticated_overrides()
    try:
        with TestClient(app) as client:
            response = client.get(
                "/api/v1/investments/performance",
                params={
                    "asset": "petr4",
                    "action": "BUY",
                    "horizon": "7d",
                    "risk_level": "LOW",
                    "investor_profile": "MODERATE",
                    "rule_version": "investment-decision-presentation-v1",
                    "recommendation_engine_version": "budget-advisor-v1",
                    "date_from": "2026-01-01T00:00:00Z",
                    "date_to": "2026-08-26T23:59:59Z",
                },
            )
        assert response.status_code == 200
        assert response.headers["cache-control"] == "private, no-store"
        assert response.json()["selected_horizon"] == "7d"
        assert captured["user_id"] == 36
        assert captured["asset"] == "petr4"
        assert captured["action"] == "BUY"
        assert captured["horizon"] == "7d"
        assert captured["risk_level"] == "LOW"
        assert captured["investor_profile"] == "MODERATE"
    finally:
        _restore(previous)


@pytest.mark.parametrize(
    "params",
    [
        {"asset": "PETR4' OR 1=1 --"},
        {"rule_version": "v1;DROP TABLE"},
        {"horizon": "365d"},
        {"date_from": "2026-01-01T00:00:00", "date_to": "2026-02-01T00:00:00Z"},
        {"date_from": "2026-02-01T00:00:00Z", "date_to": "2026-01-01T00:00:00Z"},
    ],
)
def test_filtros_invalidos_sao_rejeitados_sem_consultar_service(monkeypatch, params):
    async def should_not_run(*_args, **_kwargs):
        raise AssertionError("service não deveria ser consultado")

    monkeypatch.setattr(performance_router, "get_performance_summary", should_not_run)
    previous = _authenticated_overrides()
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/investments/performance", params=params)
        assert response.status_code == 422
    finally:
        _restore(previous)


def test_detail_aplica_owner_e_retorna_estado_parcial_sem_fabricar_resultados(monkeypatch):
    captured = {}

    async def fake_detail(_session, **kwargs):
        captured.update(kwargs)
        return _detail()

    monkeypatch.setattr(performance_router, "get_decision_performance", fake_detail)
    previous = _authenticated_overrides()
    try:
        with TestClient(app) as client:
            response = client.get(
                f"/api/v1/investments/decisions/{DECISION_ID}/performance"
            )
        body = response.json()
        assert response.status_code == 200
        assert response.headers["cache-control"] == "private, no-store"
        assert captured == {"user_id": 36, "decision_id": DECISION_ID}
        assert body["evaluations"] == []
        assert body["pending_horizons"] == ["1d", "7d", "30d"]
    finally:
        _restore(previous)


def test_id_invalido_e_decisao_de_outro_usuario_sao_indistinguiveis(monkeypatch):
    calls = 0

    async def not_owned(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        return None

    monkeypatch.setattr(performance_router, "get_decision_performance", not_owned)
    previous = _authenticated_overrides()
    try:
        with TestClient(app) as client:
            invalid = client.get(
                "/api/v1/investments/decisions/not-a-uuid/performance"
            )
            foreign = client.get(
                f"/api/v1/investments/decisions/{DECISION_ID}/performance"
            )
        assert invalid.status_code == foreign.status_code == 404
        assert invalid.json()["error"] == foreign.json()["error"] == "Decisão não encontrada"
        assert calls == 1
    finally:
        _restore(previous)
