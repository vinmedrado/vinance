from __future__ import annotations

import pandas as pd
from pandas.testing import assert_series_equal

from backend.trading.feature_store.builder import FeatureBuilder
from backend.trading.feature_store.registry import feature_columns, get_feature_set, registry_documentation


def sample_candles(rows: int = 320) -> pd.DataFrame:
    close = pd.Series([100 + index * 0.1 + (index % 7) * 0.03 for index in range(rows)], dtype=float)
    return pd.DataFrame(
        {
            "id": range(1, rows + 1),
            "exchange": "binance",
            "symbol": "BTCUSDT",
            "interval": "5m",
            "open_time": pd.date_range("2026-01-01", periods=rows, freq="5min", tz="UTC"),
            "close_time": pd.date_range("2026-01-01 00:04:59", periods=rows, freq="5min", tz="UTC"),
            "open": close - 0.1,
            "high": close + 0.8,
            "low": close - 0.7,
            "close": close,
            "volume": pd.Series([1000 + (index % 20) * 15 for index in range(rows)], dtype=float),
            "quote_volume": pd.Series([100_000 + index for index in range(rows)], dtype=float),
            "trades": 100,
        }
    )


def test_registry_exposes_stable_feature_columns() -> None:
    columns = feature_columns()
    docs = registry_documentation()
    assert len(get_feature_set().definitions) >= 22
    assert len(columns) >= 50
    assert len(docs) == len(get_feature_set().definitions)
    assert {"ema_21", "rsi_14", "atr_14", "macd_12_26", "vwap_20", "supertrend_10_3_0"}.issubset(columns)


def test_builder_creates_feature_store_v2_frame() -> None:
    result = FeatureBuilder().build(sample_candles())
    assert result.version == "v2"
    assert len(result.feature_columns) >= 50
    assert set(result.feature_columns).issubset(result.frame.columns)
    assert result.frame["log_return_1"].dropna().notna().all()
    assert result.frame[list(result.feature_columns)].iloc[-1].notna().sum() >= 45


def test_builder_does_not_use_future_candles_for_past_features() -> None:
    candles = sample_candles()
    baseline = FeatureBuilder().build(candles).frame

    changed = candles.copy()
    changed.loc[250:, "close"] = changed.loc[250:, "close"] * 3
    changed.loc[250:, "high"] = changed.loc[250:, "high"] * 3
    changed.loc[250:, "low"] = changed.loc[250:, "low"] * 3
    mutated = FeatureBuilder().build(changed).frame

    for column in ("ema_21", "rsi_14", "atr_14", "macd_12_26", "vwap_20", "bollinger_mid_20_2_0"):
        assert_series_equal(
            baseline.loc[:240, column],
            mutated.loc[:240, column],
            check_names=False,
        )
