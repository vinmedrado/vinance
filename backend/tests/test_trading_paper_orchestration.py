from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from backend.trading.model_registry import RegistryEntry
from backend.trading.paper_orchestration.service import build_signal_plan
from backend.trading.prediction_engine.models import PredictionResult


def test_cli_sanitizes_database_failures(monkeypatch, capsys) -> None:
    from backend.trading.paper_orchestration import cli

    def fail_without_exposing_connection(*_args, **_kwargs):
        raise RuntimeError("postgresql://user:private-password@database/vinance")

    monkeypatch.setattr(cli, "create_sync_engine", fail_without_exposing_connection)
    monkeypatch.setattr("sys.argv", ["paper-orchestration", "status"])

    assert cli.main() == 2
    captured = capsys.readouterr()
    assert "TRADING_ORCHESTRATION_UNAVAILABLE" in captured.err
    assert "private-password" not in captured.err


def _entry(**overrides) -> RegistryEntry:
    values = {
        "model_id": "model-1",
        "version": "model-v1",
        "symbol": "BTCUSDT",
        "interval": "5m",
        "target_version": "v2",
        "target_name": "v2_long_tp_100bps_sl_50bps_h_24",
        "feature_version": "v2",
        "model_name": "random_forest",
        "artifact_checksum": "abc",
        "created_at": "2026-10-26T00:00:00+00:00",
        "trained_until": "2026-10-25T00:00:00+00:00",
        "validation_status": "PAPER_READY",
        "promotion_status": "PAPER_ACTIVE",
        "metrics": {},
        "artifact_dir": Path("artifacts/model-1"),
        "validation_run_id": "validation-1",
    }
    values.update(overrides)
    return RegistryEntry(**values)


def _prediction(now: datetime, **overrides) -> PredictionResult:
    values = {
        "prediction_id": "prediction-1",
        "symbol": "BTCUSDT",
        "interval": "5m",
        "target_name": "v2_long_tp_100bps_sl_50bps_h_24",
        "candle_id": 1,
        "open_time": now - timedelta(minutes=5),
        "model_name": "random_forest",
        "artifact_dir": Path("artifacts/model-1"),
        "predicted_class": 1,
        "probability_stop_loss": 0.1,
        "probability_neutral": 0.1,
        "probability_take_profit": 0.8,
        "confidence": 0.8,
        "confidence_level": "HIGH",
        "decision": "BUY_CANDIDATE",
        "prediction_engine_version": "v2",
        "model_version": "model-v1",
        "feature_version": "v2",
        "risk_score": 0.1,
        "expected_return": 0.7,
        "expected_drawdown": 0.1,
        "reason": {"decision_reason": "test evidence"},
    }
    values.update(overrides)
    return PredictionResult(**values)


def test_current_promoted_prediction_becomes_approved_paper_signal() -> None:
    now = datetime(2026, 10, 26, tzinfo=timezone.utc)
    plan = build_signal_plan(
        entry=_entry(),
        result=_prediction(now),
        reference_price="100",
        now=now,
    )
    assert plan.guardrail_status == "APPROVED"
    assert plan.side == "BUY_CANDIDATE"
    assert plan.stop_price == pytest.approx(99.5)
    assert plan.target_price == pytest.approx(101)
    assert plan.reason["paper_only"] is True
    assert plan.reason["continuous_scheduler_enabled"] is False


def test_stale_prediction_is_persistable_but_never_an_opportunity() -> None:
    now = datetime(2026, 10, 26, tzinfo=timezone.utc)
    plan = build_signal_plan(
        entry=_entry(),
        result=_prediction(now, open_time=now - timedelta(days=1)),
        reference_price=100,
        now=now,
    )
    assert plan.guardrail_status == "BLOCKED"
    assert plan.reason["fresh"] is False


@pytest.mark.parametrize("price", [0, -1, float("nan"), float("inf")])
def test_invalid_market_price_fails_closed(price: float) -> None:
    now = datetime(2026, 10, 26, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="finite positive"):
        build_signal_plan(
            entry=_entry(),
            result=_prediction(now),
            reference_price=price,
            now=now,
        )


def test_registry_prediction_mismatch_and_unready_model_fail_closed() -> None:
    now = datetime(2026, 10, 26, tzinfo=timezone.utc)
    with pytest.raises(RuntimeError, match="does not match"):
        build_signal_plan(
            entry=_entry(),
            result=_prediction(now, model_version="other"),
            reference_price=100,
            now=now,
        )
    with pytest.raises(RuntimeError, match="PAPER_READY"):
        build_signal_plan(
            entry=_entry(promotion_status="PAPER_CANDIDATE"),
            result=_prediction(now),
            reference_price=100,
            now=now,
        )
