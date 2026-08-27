from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend.app.auth.dependencies import get_current_user
from backend.app.auth.models import User
from backend.app.core.database import get_session
from backend.app.investment_alerts import router as alerts_router
from backend.app.investment_alerts.repository import DuplicateSubscriptionError
from backend.app.investment_alerts.service import (
    SubscriptionLimitError,
    SubscriptionNotFoundError,
    SubscriptionSourceError,
)
from backend.app.main import app


UTC_NOW = datetime(2026, 8, 27, 1, 0, tzinfo=timezone.utc)
DECISION_ID = "37000000-0000-4000-8000-000000000001"
ALERT_ID = "37000000-0000-4000-8000-000000000002"


async def _fake_user():
    return User(
        id=37,
        email="fase37@test.local",
        full_name="Fase 37",
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


def _subscription(**overrides):
    values = {
        "id": 7,
        "asset": "GARE11",
        "market": "FII",
        "budget": Decimal("300"),
        "investor_profile": "CONSERVATIVE",
        "source_decision_id": DECISION_ID,
        "enabled": True,
        "alert_on_action_change": True,
        "alert_on_score_change": True,
        "alert_on_confidence_change": True,
        "alert_on_risk_change": True,
        "alert_on_new_opportunity": True,
        "minimum_score_delta": Decimal("5"),
        "minimum_confidence_delta": Decimal("10"),
        "cooldown_minutes": 180,
        "rule_version": "investment-alerts-v1",
        "created_at": UTC_NOW,
        "updated_at": UTC_NOW,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _alert(**overrides):
    values = {
        "alert_id": ALERT_ID,
        "subscription_id": 7,
        "decision_id": DECISION_ID,
        "asset": "GARE11",
        "alert_type": "NEW_OPPORTUNITY",
        "severity": "HIGH",
        "delivery_channel": "IN_APP",
        "message": "A recomendação mudou de Aguardar para Comprar.",
        "created_at": UTC_NOW,
        "read_at": None,
        "previous_state": {"action": "WAIT", "score": "70", "confidence": "80", "risk_level": "LOW"},
        "current_state": {"action": "BUY", "score": "82", "confidence": "92", "risk_level": "LOW"},
        "rule_version": "investment-alerts-v1",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.mark.parametrize(
    ("method", "path", "json"),
    [
        ("get", "/api/v1/investments/alert-subscriptions", None),
        ("post", "/api/v1/investments/alert-subscriptions", {"asset": "GARE11", "source_decision_id": DECISION_ID}),
        ("get", "/api/v1/investments/alerts", None),
        ("get", f"/api/v1/investments/alerts/{ALERT_ID}", None),
        ("patch", f"/api/v1/investments/alerts/{ALERT_ID}/read", {}),
    ],
)
def test_endpoints_rejeitam_usuario_anonimo(method, path, json):
    previous = dict(app.dependency_overrides)
    try:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides[get_session] = _fake_session
        with TestClient(app) as client:
            response = client.request(method, path, json=json)
        assert response.status_code == 401
    finally:
        _restore(previous)


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/investments/alert-subscriptions",
        "/api/v1/investments/alerts",
        f"/api/v1/investments/alerts/{ALERT_ID}",
    ],
)
def test_endpoints_rejeitam_token_invalido(path):
    previous = dict(app.dependency_overrides)
    try:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides[get_session] = _fake_session
        with TestClient(app) as client:
            response = client.get(path, headers={"Authorization": "Bearer token-invalido-fase-37"})
        assert response.status_code == 401
        assert response.json()["error"] == "Invalid token"
    finally:
        _restore(previous)


def test_listagem_de_monitoramentos_aplica_owner_e_cache_privado(monkeypatch):
    captured = {}

    async def fake_list(_session, *, user_id):
        captured["user_id"] = user_id
        return {"items": [_subscription()], "total": 1, "active": 1, "limit": 20}

    monkeypatch.setattr(alerts_router, "list_monitoring_subscriptions", fake_list)
    previous = _authenticated_overrides()
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/investments/alert-subscriptions")
        assert response.status_code == 200
        assert response.headers["cache-control"] == "private, no-store"
        assert response.json()["items"][0]["asset"] == "GARE11"
        assert captured == {"user_id": 37}
    finally:
        _restore(previous)


def test_criacao_encaminha_somente_asset_e_decisao_auditavel_ao_service(monkeypatch):
    captured = {}

    async def fake_create(_session, *, user_id, payload):
        captured.update({"user_id": user_id, "payload": payload})
        return _subscription()

    monkeypatch.setattr(alerts_router, "create_monitoring_subscription", fake_create)
    previous = _authenticated_overrides()
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/investments/alert-subscriptions",
                json={"asset": "GARE11", "source_decision_id": DECISION_ID},
            )
        assert response.status_code == 201
        assert captured["user_id"] == 37
        assert captured["payload"].asset == "GARE11"
    finally:
        _restore(previous)


def test_criacao_rejeita_score_acao_e_risco_fornecidos_pelo_browser(monkeypatch):
    async def should_not_run(*_args, **_kwargs):
        raise AssertionError("o service não deve confiar em estado financeiro do browser")

    monkeypatch.setattr(alerts_router, "create_monitoring_subscription", should_not_run)
    previous = _authenticated_overrides()
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/investments/alert-subscriptions",
                json={
                    "asset": "GARE11",
                    "source_decision_id": DECISION_ID,
                    "score": 100,
                    "action": "BUY",
                    "risk_level": "LOW",
                },
            )
        assert response.status_code == 422
    finally:
        _restore(previous)


@pytest.mark.parametrize(
    ("error", "expected_status"),
    [
        (DuplicateSubscriptionError("duplicado"), 409),
        (SubscriptionLimitError("limite atingido"), 409),
        (SubscriptionSourceError("decisão de origem inválida"), 422),
    ],
)
def test_criacao_traduz_erros_de_dominio_sem_vazar_detalhes(monkeypatch, error, expected_status):
    async def fail(*_args, **_kwargs):
        raise error

    monkeypatch.setattr(alerts_router, "create_monitoring_subscription", fail)
    previous = _authenticated_overrides()
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/investments/alert-subscriptions",
                json={"asset": "GARE11", "source_decision_id": DECISION_ID},
            )
        assert response.status_code == expected_status
    finally:
        _restore(previous)


def test_atualizacao_encaminha_owner_preferencias_e_disable(monkeypatch):
    captured = {}

    async def fake_update(_session, **kwargs):
        captured.update(kwargs)
        return _subscription(enabled=False, cooldown_minutes=240)

    monkeypatch.setattr(alerts_router, "update_monitoring_subscription", fake_update)
    previous = _authenticated_overrides()
    try:
        with TestClient(app) as client:
            response = client.patch(
                "/api/v1/investments/alert-subscriptions/7",
                json={"enabled": False, "cooldown_minutes": 240},
            )
        assert response.status_code == 200
        assert captured["user_id"] == 37
        assert captured["subscription_id"] == 7
        assert captured["payload"].enabled is False
        assert captured["payload"].cooldown_minutes == 240
        assert response.json()["enabled"] is False
    finally:
        _restore(previous)


def test_monitoramento_alheio_ou_inexistente_retorna_404(monkeypatch):
    async def not_owned(*_args, **_kwargs):
        raise SubscriptionNotFoundError("não encontrado")

    monkeypatch.setattr(alerts_router, "update_monitoring_subscription", not_owned)
    previous = _authenticated_overrides()
    try:
        with TestClient(app) as client:
            response = client.patch(
                "/api/v1/investments/alert-subscriptions/999",
                json={"enabled": False},
            )
        assert response.status_code == 404
        assert response.json()["error"] == "Monitoramento não encontrado"
    finally:
        _restore(previous)


def test_exclusao_encaminha_owner_e_retorna_204(monkeypatch):
    captured = {}

    async def fake_delete(_session, **kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(alerts_router, "remove_monitoring_subscription", fake_delete)
    previous = _authenticated_overrides()
    try:
        with TestClient(app) as client:
            response = client.delete("/api/v1/investments/alert-subscriptions/7")
        assert response.status_code == 204
        assert response.content == b""
        assert captured == {"user_id": 37, "subscription_id": 7}
    finally:
        _restore(previous)


def test_inbox_aplica_paginacao_filtros_owner_e_contador_global_de_nao_lidos(monkeypatch):
    captured = {}

    async def fake_list(_session, **kwargs):
        captured.update(kwargs)
        return {
            "items": [_alert()],
            "page": 2,
            "page_size": 5,
            "total": 6,
            "total_pages": 2,
            "unread_count": 3,
        }

    monkeypatch.setattr(alerts_router, "list_owned_alerts", fake_list)
    previous = _authenticated_overrides()
    try:
        with TestClient(app) as client:
            response = client.get(
                "/api/v1/investments/alerts",
                params={
                    "page": 2,
                    "page_size": 5,
                    "asset": "gare11",
                    "alert_type": "NEW_OPPORTUNITY",
                    "severity": "HIGH",
                    "unread_only": "true",
                    "date_from": "2026-08-01T00:00:00Z",
                    "date_to": "2026-08-27T23:59:59Z",
                },
            )
        assert response.status_code == 200
        assert response.headers["cache-control"] == "private, no-store"
        assert response.json()["unread_count"] == 3
        assert captured["user_id"] == 37
        assert captured["asset"] == "GARE11"
        assert captured["alert_type"] == "NEW_OPPORTUNITY"
        assert captured["severity"] == "HIGH"
        assert captured["unread_only"] is True
    finally:
        _restore(previous)


@pytest.mark.parametrize(
    "params",
    [
        {"asset": "GARE11' OR 1=1 --"},
        {"alert_type": "DROP_TABLE"},
        {"severity": "CRITICAL"},
        {"page_size": 5000},
        {"date_from": "2026-08-01T00:00:00", "date_to": "2026-08-02T00:00:00Z"},
        {"date_from": "2026-08-03T00:00:00Z", "date_to": "2026-08-02T00:00:00Z"},
    ],
)
def test_filtros_invalidos_nao_chegam_ao_repositorio(monkeypatch, params):
    async def should_not_run(*_args, **_kwargs):
        raise AssertionError("repositório não deveria ser consultado")

    monkeypatch.setattr(alerts_router, "list_owned_alerts", should_not_run)
    previous = _authenticated_overrides()
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/investments/alerts", params=params)
        assert response.status_code == 422
    finally:
        _restore(previous)


def test_detalhe_aplica_owner_e_retorna_snapshot_comparativo(monkeypatch):
    captured = {}

    async def fake_get(_session, **kwargs):
        captured.update(kwargs)
        return _alert()

    monkeypatch.setattr(alerts_router, "get_owned_alert", fake_get)
    previous = _authenticated_overrides()
    try:
        with TestClient(app) as client:
            response = client.get(f"/api/v1/investments/alerts/{ALERT_ID}")
        body = response.json()
        assert response.status_code == 200
        assert captured == {"user_id": 37, "alert_id": ALERT_ID}
        assert body["previous_state"]["action"] == "WAIT"
        assert body["current_state"]["action"] == "BUY"
        assert body["decision_id"] == DECISION_ID
    finally:
        _restore(previous)


def test_id_invalido_e_alerta_de_outro_usuario_sao_indistinguiveis(monkeypatch):
    calls = 0

    async def not_owned(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        return None

    monkeypatch.setattr(alerts_router, "get_owned_alert", not_owned)
    previous = _authenticated_overrides()
    try:
        with TestClient(app) as client:
            invalid = client.get("/api/v1/investments/alerts/not-a-uuid")
            foreign = client.get(f"/api/v1/investments/alerts/{ALERT_ID}")
        assert invalid.status_code == foreign.status_code == 404
        assert invalid.json()["error"] == foreign.json()["error"] == "Alerta não encontrado"
        assert calls == 1
    finally:
        _restore(previous)


def test_marcar_lido_e_idempotente_e_aplica_owner(monkeypatch):
    captured = {}

    async def fake_mark(_session, **kwargs):
        captured.update(kwargs)
        return _alert(read_at=kwargs["read_at"])

    monkeypatch.setattr(alerts_router, "mark_owned_alert_read", fake_mark)
    previous = _authenticated_overrides()
    try:
        with TestClient(app) as client:
            response = client.patch(f"/api/v1/investments/alerts/{ALERT_ID}/read", json={})
        assert response.status_code == 200
        assert captured["user_id"] == 37
        assert captured["alert_id"] == ALERT_ID
        assert captured["read_at"].tzinfo is not None
        assert response.json()["read_at"] is not None
    finally:
        _restore(previous)


def test_usuario_nao_marca_alerta_de_outro_usuario_como_lido(monkeypatch):
    async def not_owned(*_args, **_kwargs):
        return None

    monkeypatch.setattr(alerts_router, "mark_owned_alert_read", not_owned)
    previous = _authenticated_overrides()
    try:
        with TestClient(app) as client:
            response = client.patch(f"/api/v1/investments/alerts/{ALERT_ID}/read", json={})
        assert response.status_code == 404
        assert response.json()["error"] == "Alerta não encontrado"
    finally:
        _restore(previous)


def test_metricas_operacionais_sao_autenticadas_e_isoladas_por_usuario(monkeypatch):
    captured = {}

    async def fake_metrics(_session, *, user_id):
        captured["user_id"] = user_id
        return {
            "active_subscriptions": 2,
            "evaluations_performed": 4,
            "alerts_generated": 3,
            "cooldown_suppressed": 1,
            "duplicates_prevented": 2,
            "volume_suppressed": 0,
            "errors": 0,
            "unread_alerts": 1,
            "by_type": {"NEW_OPPORTUNITY": 1, "SCORE_CHANGE": 2},
        }

    monkeypatch.setattr(alerts_router, "alert_metrics", fake_metrics)
    previous = _authenticated_overrides()
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/investments/alerts/metrics")
        assert response.status_code == 200
        assert response.json()["duplicates_prevented"] == 2
        assert captured == {"user_id": 37}
    finally:
        _restore(previous)
