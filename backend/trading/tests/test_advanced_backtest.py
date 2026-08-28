import pandas as pd

from backend.trading.backtests.advanced import run_advanced_long_backtest


def test_advanced_backtest_returns_metrics():
    frame = pd.DataFrame({
        "open_time": pd.date_range("2026-01-01", periods=50, freq="5min", tz="UTC"),
        "close": [100 + i * 0.1 for i in range(50)],
        "high": [100.2 + i * 0.1 for i in range(50)],
        "low": [99.8 + i * 0.1 for i in range(50)],
        "probability_up": [0.7] * 10 + [0.5] * 40,
    })
    result = run_advanced_long_backtest(frame)
    assert "return_pct" in result.metrics
    assert "profit_factor" in result.metrics
    assert result.metrics["trades"] >= 1
