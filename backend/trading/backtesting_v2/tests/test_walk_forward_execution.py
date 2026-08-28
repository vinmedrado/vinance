from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from backend.trading.backtesting_v2.config import BacktestingConfig, WalkForwardConfig
from backend.trading.backtesting_v2.models import HistoricalCandle
from backend.trading.backtesting_v2.runner import BacktestRunner
from backend.trading.backtesting_v2.walk_forward import (
    build_walk_forward_windows,
    select_validation_threshold,
)
from backend.trading.paper_trading_v2.config import PaperTradingConfig
from backend.trading.paper_trading_v2.models import MarketCandle

from .helpers import StaticModel, artifacts, config


def _history(count: int, *, adverse_from: int | None = None) -> list[HistoricalCandle]:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows = []
    for index in range(count):
        price = 100 + index * 0.01
        adverse = adverse_from is not None and index >= adverse_from
        rows.append(
            HistoricalCandle(
                MarketCandle(
                    index + 1,
                    "BTCUSDT",
                    "5m",
                    start + timedelta(minutes=5 * index),
                    price,
                    price if adverse else price * 1.02,
                    price * 0.98 if adverse else price,
                    price,
                ),
                {"f1": float(index), "f2": float(index + 1)},
            )
        )
    return rows


def _walk_config(*, windows: int = 1) -> WalkForwardConfig:
    return WalkForwardConfig(
        window_count=windows,
        train_size=20,
        validation_size=10,
        test_size=10,
        min_segment_candles=1,
        take_profit_thresholds=(0.50, 0.80),
        stop_loss_thresholds=(0.50,),
    )


def _runner_config(tmp_path, *, walk_forward: WalkForwardConfig) -> BacktestingConfig:
    return config(
        tmp_path,
        walk_forward=walk_forward,
        paper_config=PaperTradingConfig(
            fee_bps=0,
            slippage_bps=0,
            spread_bps=0,
            cooldown_candles=0,
            min_confidence=0,
            max_open_positions=1,
        ),
    )


def test_expanding_windows_are_chronological_without_validation_test_overlap() -> None:
    rows = _history(100)
    windows = build_walk_forward_windows(
        rows,
        WalkForwardConfig(window_count=3, min_segment_candles=1),
    )

    assert len(windows) == 3
    used_validation_test: set[int] = set()
    for window in windows:
        assert window.train[-1].open_time < window.validation[0].open_time
        assert window.validation[-1].open_time < window.test[0].open_time
        current = {item.candle_id for item in window.validation + window.test}
        assert not used_validation_test.intersection(current)
        used_validation_test.update(current)


def test_threshold_selection_uses_positive_expectancy_pf_then_sharpe_and_drawdown() -> None:
    rows = [
        {"threshold_tp": 0.50, "threshold_sl": 0.50, "expectancy": 1, "profit_factor": 2, "sharpe": 0.5, "max_drawdown": 0.10, "net_profit": 10},
        {"threshold_tp": 0.55, "threshold_sl": 0.50, "expectancy": 1, "profit_factor": 2, "sharpe": 0.5, "max_drawdown": 0.05, "net_profit": 5},
        {"threshold_tp": 0.60, "threshold_sl": 0.50, "expectancy": -1, "profit_factor": 3, "sharpe": 0.9, "max_drawdown": 0.01, "net_profit": -1},
    ]

    selected = select_validation_threshold(rows)
    assert selected["threshold_tp"] == 0.55


def test_walk_forward_report_has_windows_metrics_and_oos_consolidation(tmp_path) -> None:
    cfg = _runner_config(tmp_path, walk_forward=_walk_config(windows=2))
    result = BacktestRunner(cfg, artifacts=artifacts(StaticModel((0.10, 0.20, 0.70)))).run(_history(60))
    payload = result.walk_forward_results

    assert len(payload["windows"]) == 2
    assert payload["consolidated"]["total_windows"] == 2
    assert payload["consolidated"]["aggregate_test_trades"] > 0
    assert payload["consolidated"]["out_of_sample_positive"] is True
    assert all(window["threshold_selected_from"] == "validation" for window in payload["windows"])
    assert all(len(window["validation_threshold_results"]) == 2 for window in payload["windows"])
    required = {
        "trades_validation",
        "trades_test",
        "net_profit_validation",
        "net_profit_test",
        "profit_factor_validation",
        "profit_factor_test",
        "win_rate_validation",
        "win_rate_test",
        "expectancy_validation",
        "expectancy_test",
        "sharpe_validation",
        "sharpe_test",
        "max_drawdown_validation",
        "max_drawdown_test",
        "capital_start_test",
        "capital_end_test",
    }
    assert all(required.issubset(window) for window in payload["windows"])
    saved = json.loads(result.reports["walk_forward_results"].read_text(encoding="utf-8"))
    assert saved["windows"]


def test_selected_validation_threshold_is_applied_to_negative_test_without_reoptimization(tmp_path) -> None:
    cfg = _runner_config(tmp_path, walk_forward=_walk_config())
    result = BacktestRunner(cfg, artifacts=artifacts(StaticModel((0.10, 0.20, 0.70)))).run(
        _history(40, adverse_from=30)
    )
    window = result.walk_forward_results["windows"][0]

    assert window["threshold_tp_selected"] == 0.50
    assert window["net_profit_validation"] > 0
    assert window["net_profit_test"] < 0
    assert result.walk_forward_results["consolidated"]["negative_test_windows"] == 1
    assert result.walk_forward_results["consolidated"]["out_of_sample_positive"] is False


def test_walk_forward_window_without_trades_is_reported(tmp_path) -> None:
    cfg = _runner_config(tmp_path, walk_forward=_walk_config())
    result = BacktestRunner(cfg, artifacts=artifacts(StaticModel((0.10, 0.80, 0.10)))).run(_history(40))
    window = result.walk_forward_results["windows"][0]

    assert window["trades_validation"] == 0
    assert window["trades_test"] == 0
    assert result.walk_forward_results["consolidated"]["aggregate_test_trades"] == 0


def test_walk_forward_is_idempotent_and_paper_only_remains_required(tmp_path) -> None:
    cfg = _runner_config(tmp_path, walk_forward=_walk_config())
    rows = _history(40)
    first = BacktestRunner(cfg, artifacts=artifacts(StaticModel())).run(rows)
    second = BacktestRunner(cfg, artifacts=artifacts(StaticModel())).run(rows)

    assert first.context.run_id == second.context.run_id
    assert first.walk_forward_results == second.walk_forward_results
    with pytest.raises(RuntimeError, match="PAPER_ONLY"):
        BacktestingConfig(paper_only=False)
