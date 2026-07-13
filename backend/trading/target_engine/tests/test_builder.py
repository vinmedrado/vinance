from __future__ import annotations

import pandas as pd
from pandas.testing import assert_series_equal

from backend.trading.target_engine.builder import TargetBuilder
from backend.trading.target_engine.config import TargetEngineConfig, TargetSpec


def candles_from_prices(close: list[float], high: list[float] | None = None, low: list[float] | None = None) -> pd.DataFrame:
    rows = len(close)
    return pd.DataFrame(
        {
            "id": range(1, rows + 1),
            "exchange": "binance",
            "symbol": "BTCUSDT",
            "interval": "5m",
            "open_time": pd.date_range("2026-01-01", periods=rows, freq="5min", tz="UTC"),
            "high": high or close,
            "low": low or close,
            "close": close,
        }
    )


def test_long_target_take_profit_before_stop_loss() -> None:
    config = TargetEngineConfig(specs=(TargetSpec("long", horizon_candles=3, take_profit_pct=0.01, stop_loss_pct=0.01),))
    frame = candles_from_prices(
        close=[100, 100.5, 101.2, 99.0],
        high=[100, 100.7, 101.1, 99.2],
        low=[100, 99.5, 100.8, 98.5],
    )
    result = TargetBuilder(config).build(frame).frame
    prefix = config.specs[0].name
    assert result.loc[0, f"{prefix}_class"] == 1
    assert result.loc[0, f"{prefix}_time_to_event"] == 2
    assert round(result.loc[0, f"{prefix}_exit_return"], 4) == 0.0100


def test_short_target_stop_loss_before_take_profit() -> None:
    config = TargetEngineConfig(specs=(TargetSpec("short", horizon_candles=3, take_profit_pct=0.01, stop_loss_pct=0.01),))
    frame = candles_from_prices(
        close=[100, 101.5, 98.0, 97.0],
        high=[100, 101.1, 98.2, 97.2],
        low=[100, 99.5, 98.0, 96.8],
    )
    result = TargetBuilder(config).build(frame).frame
    prefix = config.specs[0].name
    assert result.loc[0, f"{prefix}_class"] == -1
    assert result.loc[0, f"{prefix}_time_to_event"] == 1
    assert round(result.loc[0, f"{prefix}_exit_return"], 4) == -0.0099


def test_no_event_uses_horizon_close_return() -> None:
    config = TargetEngineConfig(specs=(TargetSpec("long", horizon_candles=2, take_profit_pct=0.10, stop_loss_pct=0.10),))
    frame = candles_from_prices(close=[100, 101, 102], high=[100, 101, 102], low=[100, 101, 102])
    result = TargetBuilder(config).build(frame).frame
    prefix = config.specs[0].name
    assert result.loc[0, f"{prefix}_class"] == 0
    assert result.loc[0, f"{prefix}_time_to_event"] == 2
    assert round(result.loc[0, f"{prefix}_exit_return"], 4) == 0.0200


def test_future_changes_do_not_change_earlier_labels_outside_horizon() -> None:
    config = TargetEngineConfig(specs=(TargetSpec("long", horizon_candles=5, take_profit_pct=0.02, stop_loss_pct=0.02),))
    close = [100 + index * 0.05 for index in range(40)]
    frame = candles_from_prices(close=close, high=[value + 0.1 for value in close], low=[value - 0.1 for value in close])
    baseline = TargetBuilder(config).build(frame).frame

    changed = frame.copy()
    changed.loc[20:, "high"] = changed.loc[20:, "high"] * 3
    changed.loc[20:, "low"] = changed.loc[20:, "low"] * 0.3
    changed_result = TargetBuilder(config).build(changed).frame

    prefix = config.specs[0].name
    for column in (f"{prefix}_class", f"{prefix}_time_to_event", f"{prefix}_exit_return"):
        assert_series_equal(baseline.loc[:14, column], changed_result.loc[:14, column], check_names=False)
