from __future__ import annotations

import pandas as pd

from backend.trading.feature_store.volatility import add_atr, add_bollinger, add_donchian, add_keltner
from backend.trading.feature_store.volume import add_cmf, add_mfi, add_obv, add_vwap


def sample_candles(rows: int = 80) -> pd.DataFrame:
    close = pd.Series([100 + index * 0.5 for index in range(rows)], dtype=float)
    return pd.DataFrame(
        {
            "open_time": pd.date_range("2026-01-01", periods=rows, freq="5min", tz="UTC"),
            "open": close - 0.2,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": pd.Series([1000 + index * 10 for index in range(rows)], dtype=float),
        }
    )


def test_volatility_indicators_create_expected_columns() -> None:
    frame = sample_candles()
    frame = add_atr(frame)
    frame = add_bollinger(frame)
    frame = add_donchian(frame)
    frame = add_keltner(frame)

    expected = {
        "atr_14",
        "atr_pct_14",
        "bollinger_mid_20_2_0",
        "bollinger_upper_20_2_0",
        "donchian_upper_20",
        "keltner_upper_20_10_2_0",
    }
    assert expected.issubset(frame.columns)
    assert frame["atr_14"].dropna().gt(0).all()


def test_volume_indicators_create_expected_columns() -> None:
    frame = sample_candles()
    frame = add_vwap(frame)
    frame = add_obv(frame)
    frame = add_mfi(frame)
    frame = add_cmf(frame)

    expected = {"vwap_20", "vwap_distance_20", "obv", "obv_change_20", "mfi_14", "cmf_20"}
    assert expected.issubset(frame.columns)
    assert frame["vwap_20"].dropna().gt(0).all()
    assert frame["obv"].iloc[-1] > frame["obv"].iloc[0]
