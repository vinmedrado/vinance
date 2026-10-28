from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.app.trading import router as trading_router_module
from backend.app.trading.router import router as trading_router
from backend.app.trading.schemas import PaperAccountCreate, PaperOrderCreate
from backend.app.main import app
from backend.app.trading.service import _event_read, _public_signal_reason


def test_trading_router_is_authenticated_product_surface() -> None:
    routes = {
        (method, route.path)
        for route in trading_router.routes
        for method in getattr(route, "methods", set())
    }
    required = {
        ("GET", "/trading/overview"),
        ("GET", "/trading/risk-budget"),
        ("GET", "/trading/opportunities"),
        ("GET", "/trading/signals"),
        ("POST", "/trading/paper/account"),
        ("GET", "/trading/paper/account"),
        ("POST", "/trading/paper/orders"),
        ("GET", "/trading/paper/positions"),
        ("GET", "/trading/paper/events"),
        ("GET", "/trading/backtests"),
        ("GET", "/trading/health"),
    }
    assert required.issubset(routes)


def test_trading_surface_rejects_unauthenticated_requests() -> None:
    with TestClient(app) as client:
        assert client.get("/api/v1/trading/health").status_code == 401
        assert client.post(
            "/api/v1/trading/paper/account",
            json={"ownership_scope": "PERSONAL", "paper_only": True},
        ).status_code == 401


@pytest.mark.asyncio
async def test_trading_mutations_use_a_per_user_rate_limit(monkeypatch) -> None:
    captured = {}

    async def fake_limit(scope, identifier, limit, **kwargs):
        captured.update(
            scope=scope,
            identifier=identifier,
            limit=limit,
            kwargs=kwargs,
        )

    monkeypatch.setattr(trading_router_module, "enforce_auth_rate_limit", fake_limit)
    await trading_router_module._limit_mutation(42, "create-order")

    assert captured["scope"] == "trading-create-order"
    assert captured["identifier"] == "42"
    assert captured["limit"] > 0


def test_request_schema_has_no_live_or_broker_execution_field() -> None:
    fields = set(PaperOrderCreate.model_fields)
    assert "mode" not in fields
    assert "broker" not in fields
    assert "exchange_api_key" not in fields
    assert "live" not in fields


def test_requests_reject_live_household_and_client_selected_owner() -> None:
    with pytest.raises(ValidationError):
        PaperAccountCreate(ownership_scope="HOUSEHOLD")
    with pytest.raises(ValidationError):
        PaperOrderCreate(
            idempotency_key="paper-live-1",
            signal_id=1,
            symbol="BTCUSDT",
            side="BUY",
            notional="100",
            paper_only=False,
        )
    with pytest.raises(ValidationError):
        PaperOrderCreate(
            idempotency_key="paper-live-2",
            signal_id=1,
            symbol="BTCUSDT",
            side="BUY",
            notional="100",
            mode="LIVE",
        )
    with pytest.raises(ValidationError):
        PaperOrderCreate(
            idempotency_key="paper-owner-1",
            signal_id=1,
            symbol="BTCUSDT",
            side="BUY",
            notional="100",
            owner_user_id=999,
        )


def test_client_cannot_override_signal_owned_stop_or_target() -> None:
    with pytest.raises(ValidationError):
        PaperOrderCreate(
            idempotency_key="paper-risk-1",
            signal_id=1,
            symbol="BTCUSDT",
            side="BUY",
            notional="100",
            stop_price="95",
        )


def test_trading_main_alembic_is_not_modified_to_own_external_tables() -> None:
    ownership = Path("backend/alembic/schema_ownership.py").read_text(encoding="utf-8")
    for table in (
        "crypto_candles",
        "crypto_features",
        "crypto_targets",
        "trading_signals",
        "paper_trades",
        "backtest_runs",
    ):
        assert table in ownership


def test_signal_reason_projection_does_not_expose_internal_or_secret_fields() -> None:
    projected = _public_signal_reason(
        {
            "model_id": "btc-5m-v1",
            "confidence": 0.81,
            "reasons": ["Sinal atual e aprovado pelos guardrails."],
            "artifact_path": "C:/private/models/model.joblib",
            "api_key": "must-not-leak",
            "raw_features": {"private": True},
            "reasons": [
                "Sinal atual e aprovado pelos guardrails.",
                {"secret": "nested"},
                "token=must-not-leak",
            ],
        }
    )

    assert projected == {
        "confidence": 0.81,
        "model_id": "btc-5m-v1",
        "reasons": ["Sinal atual e aprovado pelos guardrails."],
    }


def test_event_projection_never_exposes_idempotency_or_unexpected_json() -> None:
    projected = _event_read(
        {
            "id": 1,
            "owner_user_id": 7,
            "paper_account_id": 2,
            "event_type": "PAPER_ORDER_CANCELLED",
            "signal_id": None,
            "prediction_id": None,
            "order_id": 3,
            "position_id": None,
            "symbol": "BTCUSDT",
            "event_payload": {
                "status": "CANCELLED",
                "paper_only": True,
                "idempotency_key": "private-nonce",
                "api_key": "must-not-leak",
            },
            "decision_context": {"reason": "USER_REQUESTED", "secret": "x"},
            "risk_context": {"real_trading_capital": "0.00", "password": "x"},
            "correlation_id": "test-correlation",
            "created_at": datetime.now(timezone.utc),
        }
    )

    assert projected.event_payload == {"paper_only": True, "status": "CANCELLED"}
    assert projected.decision_context == {"reason": "USER_REQUESTED"}
    assert projected.risk_context == {"real_trading_capital": "0.00"}
