from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from backend.trading.backtesting_v2.models import HistoricalCandle
from backend.trading.backtesting_v2.runner import BacktestRunner
from backend.trading.backtesting_v2.simulator import (
    equity_temporal_integrity,
    validate_temporal_integrity,
)
from backend.trading.paper_trading_v2.config import PaperTradingConfig
from backend.trading.paper_trading_v2.models import MarketCandle, PortfolioSnapshot

from .helpers import StaticModel, artifacts, config


def _causal_history() -> list[HistoricalCandle]:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    values = [
        (100.0, 100.0, 100.0),
        (100.0, 100.2, 99.9),
        (100.0, 102.0, 100.0),
        (100.0, 100.2, 99.9),
    ]
    return [
        HistoricalCandle(
            MarketCandle(
                index + 1,
                "BTCUSDT",
                "5m",
                start + timedelta(minutes=5 * index),
                close,
                high,
                low,
                close,
            ),
            {"f1": float(index), "f2": float(index + 1)},
        )
        for index, (close, high, low) in enumerate(values)
    ]


def _run(tmp_path):
    paper = PaperTradingConfig(
        fee_bps=0,
        slippage_bps=0,
        spread_bps=0,
        cooldown_candles=0,
        max_open_positions=1,
    )
    return BacktestRunner(
        config(tmp_path, paper_config=paper),
        artifacts=artifacts(StaticModel((0.10, 0.20, 0.70))),
    ).run(_causal_history())


def test_equity_curve_is_strictly_ordered_and_consolidated_per_candle(tmp_path) -> None:
    result = _run(tmp_path)
    timestamps = [snapshot.timestamp for snapshot in result.equity_curve]

    assert timestamps == sorted(timestamps)
    assert len(timestamps) == len(set(timestamps)) == 4
    assert result.metrics["equity_records_total"] == 4
    assert result.metrics["equity_unique_timestamps"] == 4
    assert result.metrics["equity_duplicate_timestamps"] == 0
    assert result.metrics["equity_time_regressions"] == 0
    assert result.metrics["temporal_integrity_valid"] is True


def test_future_exit_does_not_change_past_equity_and_close_is_after_open(tmp_path) -> None:
    result = _run(tmp_path)

    assert result.equity_curve[0].cumulative_profit == 0
    assert result.equity_curve[1].cumulative_profit == 0
    assert result.equity_curve[2].cumulative_profit > 0
    assert all(trade.exit_time > trade.entry_time for trade in result.trades)


def test_close_and_new_open_on_same_candle_have_one_post_event_snapshot(tmp_path) -> None:
    result = _run(tmp_path)
    event_time = _causal_history()[2].open_time
    same_time = [snapshot for snapshot in result.equity_curve if snapshot.timestamp == event_time]

    assert len(same_time) == 1
    assert any(trade.exit_time == event_time for trade in result.trades)
    assert same_time[0].invested_capital > 0


def test_last_equity_matches_final_capital_and_metadata(tmp_path) -> None:
    result = _run(tmp_path)

    assert result.equity_curve[-1].equity == pytest.approx(result.metrics["capital_final"])
    assert result.context.metadata["temporal_integrity_valid"] is True
    assert result.context.metadata["equity_time_regressions"] == 0


def test_duplicate_timestamp_is_counted_without_regression() -> None:
    timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
    curve = [
        PortfolioSnapshot(timestamp, 100, 100, 0, 0, 0, 0, 0),
        PortfolioSnapshot(timestamp, 101, 101, 0, 1, 0, 0, 0.01),
    ]

    integrity = equity_temporal_integrity(curve)
    assert integrity["equity_duplicate_timestamps"] == 1
    assert integrity["equity_time_regressions"] == 0
    assert integrity["temporal_integrity_valid"] is True


def test_temporal_validation_fails_on_artificial_regression() -> None:
    later = datetime(2026, 1, 1, 0, 5, tzinfo=timezone.utc)
    earlier = later - timedelta(minutes=5)
    curve = [
        PortfolioSnapshot(later, 100, 100, 0, 0, 0, 0, 0),
        PortfolioSnapshot(earlier, 100, 100, 0, 0, 0, 0, 0),
    ]

    with pytest.raises(ValueError, match="temporal regressions"):
        validate_temporal_integrity(curve)
