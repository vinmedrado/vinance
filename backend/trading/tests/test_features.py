import pandas as pd

from ..features.builder import build_features


def test_build_features_creates_expected_columns() -> None:
    frame = pd.DataFrame({
        "open_time": pd.date_range("2026-01-01", periods=30, freq="5min", tz="UTC"),
        "open": range(1, 31),
        "high": range(2, 32),
        "low": [max(0.5, x - 1) for x in range(1, 31)],
        "close": range(1, 31),
        "volume": range(100, 130),
    })
    result = build_features(frame)
    assert {"return_1", "ema_9", "rsi_14"}.issubset(result.columns)
