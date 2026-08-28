from __future__ import annotations

import inspect
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from backend.trading.backtesting_v2.baselines import baseline_comparison
from backend.trading.backtesting_v2.config import BacktestingConfig, STOP_LOSS_FIRST, WalkForwardConfig
from backend.trading.backtesting_v2.metrics import calculate_backtest_metrics
from backend.trading.backtesting_v2.models import HistoricalCandle
from backend.trading.backtesting_v2.repository import BacktestingRepository, validate_history
from backend.trading.backtesting_v2.runner import BacktestRunner, deterministic_run_id
from backend.trading.backtesting_v2.simulator import BacktestSimulator, future_window
from backend.trading.backtesting_v2.walk_forward import build_walk_forward_windows
from backend.trading.ml_engine.config import MLEngineConfig
from backend.trading.ml_engine.pipeline import MLEnginePipeline
from backend.trading.ml_engine.tests.helpers import synthetic_dataset
from backend.trading.paper_trading_v2.config import PaperTradingConfig
from backend.trading.paper_trading_v2.portfolio import PortfolioManager
from backend.trading.prediction_engine.models import PredictionResult


def dt(index: int) -> datetime:
    return datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=5 * index)


def candle(index: int, *, close: float = 100.0, high: float | None = None, low: float | None = None, features=None) -> HistoricalCandle:
    return HistoricalCandle(
        candle_id=index + 1,
        symbol="BTCUSDT",
        interval="5m",
        open_time=dt(index),
        open=close,
        high=high if high is not None else close,
        low=low if low is not None else close,
        close=close,
        features=features or {"f1": 1.0, "f2": 2.0},
    )


def prediction(
    *,
    decision: str = "BUY_CANDIDATE",
    confidence: float = 0.80,
    prediction_id: str = "p1",
    candle_id: int = 1,
    target_name: str = "v2_long_tp_100bps_sl_50bps_h_24",
) -> PredictionResult:
    return PredictionResult(
        prediction_id=prediction_id,
        symbol="BTCUSDT",
        interval="5m",
        target_name=target_name,
        candle_id=candle_id,
        open_time=dt(candle_id - 1),
        model_name="hist_gradient_boosting",
        artifact_dir=Path("artifact"),
        predicted_class=1,
        probability_stop_loss=0.10,
        probability_neutral=0.20,
        probability_take_profit=0.70,
        confidence=confidence,
        confidence_level="HIGH",
        decision=decision,
        prediction_engine_version="v2",
        model_version="v2",
        feature_version="v2",
        risk_score=0.10,
        expected_return=0.60,
        expected_drawdown=0.10,
        reason={"paper_only": True},
    )


def test_repository_query_is_ordered_and_has_no_target_leakage() -> None:
    source = inspect.getsource(BacktestingRepository.load_history)
    assert "ORDER BY c.open_time ASC" in source
    assert "crypto_targets" not in source


def test_history_validation_order_empty_duplicate_and_minimum() -> None:
    validate_history((candle(0), candle(1)), min_candles=2)
    with pytest.raises(ValueError, match="empty"):
        validate_history((), min_candles=1)
    with pytest.raises(ValueError, match="strictly ordered"):
        validate_history((candle(1), candle(0)), min_candles=1)
    with pytest.raises(ValueError, match="Duplicate|strictly ordered"):
        validate_history((candle(0), candle(0)), min_candles=1)
    with pytest.raises(ValueError, match="minimum"):
        validate_history((candle(0),), min_candles=2)


def test_paper_only_is_mandatory_and_config_validations() -> None:
    with pytest.raises(RuntimeError, match="PAPER_ONLY"):
        BacktestingConfig(paper_only=False)
    with pytest.raises(RuntimeError, match="PAPER_ONLY"):
        BacktestingConfig(paper_config=PaperTradingConfig(paper_only=False))
    with pytest.raises(ValueError, match="threshold"):
        BacktestingConfig(take_profit_thresholds=(1.5,))
    with pytest.raises(ValueError, match="cannot be negative"):
        BacktestingConfig(paper_config=PaperTradingConfig(fee_bps=-1))


def test_run_id_is_deterministic_and_ignores_timestamp() -> None:
    metadata = {"symbol": "BTCUSDT", "timestamp": "a", "thresholds": {"take_profit": 0.6, "stop_loss": 0.6}}
    changed = {"symbol": "BTCUSDT", "timestamp": "b", "thresholds": {"take_profit": 0.6, "stop_loss": 0.6}}
    assert deterministic_run_id(metadata) == deterministic_run_id(changed)
    assert deterministic_run_id(metadata) != deterministic_run_id({**metadata, "symbol": "ETHUSDT"})


def test_future_window_does_not_feed_inference_and_respects_horizon() -> None:
    candles = tuple(candle(i) for i in range(30))
    future = future_window(candles, 0, "v2_long_tp_100bps_sl_50bps_h_2")
    assert [item.candle_id for item in future] == [2, 3]


def test_open_tp_sl_horizon_intracandle_and_costs() -> None:
    config = BacktestingConfig(
        paper_config=PaperTradingConfig(fee_bps=10, slippage_bps=10, spread_bps=4, cooldown_candles=0),
        intracandle_policy=STOP_LOSS_FIRST,
    )
    simulator = BacktestSimulator(config)
    portfolio = simulator.initial_state()
    result = simulator.execute_signal(
        prediction=prediction(),
        candle=candle(0, close=100),
        future_candles=(candle(1, close=100, high=102, low=99),),
        portfolio=portfolio,
        candle_index=0,
    )
    assert result.opened_position is not None
    assert result.closed_trade is not None
    assert result.closed_trade.exit_reason == "STOP_LOSS"
    assert result.opened_position.entry_price == 100 * (1 + 12 / 10_000)
    assert result.closed_trade.fees > 0

    tp = simulator.execute_signal(
        prediction=prediction(prediction_id="tp", candle_id=2),
        candle=candle(2, close=100),
        future_candles=(candle(3, high=102, low=100),),
        portfolio=simulator.initial_state(),
        candle_index=2,
    )
    assert tp.closed_trade is not None and tp.closed_trade.exit_reason == "TAKE_PROFIT"

    horizon = simulator.execute_signal(
        prediction=prediction(prediction_id="h", candle_id=4, target_name="v2_long_tp_100bps_sl_50bps_h_1"),
        candle=candle(4, close=100),
        future_candles=(candle(5, close=100.1, high=100.2, low=99.9),),
        portfolio=simulator.initial_state(),
        candle_index=4,
    )
    assert horizon.closed_trade is not None and horizon.closed_trade.exit_reason == "HORIZON_EXPIRATION"


def test_risk_controls_cooldown_daily_loss_and_max_open_positions() -> None:
    config = BacktestingConfig(paper_config=PaperTradingConfig(max_open_positions=1, cooldown_candles=2, max_daily_loss=0.01))
    simulator = BacktestSimulator(config)
    portfolio = simulator.initial_state()
    simulator.execute_signal(prediction=prediction(), candle=candle(0), future_candles=(), portfolio=portfolio, candle_index=0)
    blocked = simulator.execute_signal(
        prediction=prediction(prediction_id="p2", candle_id=2),
        candle=candle(1),
        future_candles=(),
        portfolio=portfolio,
        candle_index=1,
    )
    assert blocked.reason == "max_open_positions"
    portfolio.positions.clear()
    cooldown = simulator.execute_signal(
        prediction=prediction(prediction_id="p3", candle_id=3),
        candle=candle(2),
        future_candles=(),
        portfolio=portfolio,
        candle_index=1,
    )
    assert cooldown.reason == "cooldown"
    portfolio.last_trade_index.clear()
    portfolio.daily_results[dt(0).date()] = -200
    daily_loss = simulator.execute_signal(
        prediction=prediction(prediction_id="p4", candle_id=4),
        candle=candle(3),
        future_candles=(),
        portfolio=portfolio,
        candle_index=10,
    )
    assert daily_loss.reason == "max_daily_loss"


def test_metrics_edge_cases_no_trades_all_winners_all_losers() -> None:
    config = BacktestingConfig(paper_config=PaperTradingConfig(fee_bps=0, slippage_bps=0, spread_bps=0, cooldown_candles=0))
    simulator = BacktestSimulator(config)
    empty = simulator.initial_state()
    simulator.portfolio.mark_to_market(empty, timestamp=dt(0), last_price=100)
    no_trades = calculate_backtest_metrics(
        initial_capital=10_000,
        final_capital=empty.equity,
        trades=[],
        equity_curve=empty.equity_curve,
        predictions=[],
        candles=(candle(0), candle(1)),
        blocked_by_confidence=0,
        blocked_by_risk=0,
    )
    assert no_trades["number_of_trades"] == 0
    assert no_trades["sharpe"] == 0.0

    win = simulator.execute_signal(prediction=prediction(), candle=candle(0), future_candles=(candle(1, high=102),), portfolio=simulator.initial_state(), candle_index=0)
    win_metrics = calculate_backtest_metrics(initial_capital=10_000, final_capital=10_100, trades=[win.closed_trade], equity_curve=[], predictions=[], candles=(candle(0), candle(1)), blocked_by_confidence=0, blocked_by_risk=0)
    assert win_metrics["profit_factor"] == float("inf")
    assert win_metrics["winning_trades"] == 1

    loss = simulator.execute_signal(prediction=prediction(prediction_id="l"), candle=candle(0), future_candles=(candle(1, low=99),), portfolio=simulator.initial_state(), candle_index=0)
    loss_metrics = calculate_backtest_metrics(initial_capital=10_000, final_capital=9_900, trades=[loss.closed_trade], equity_curve=[], predictions=[], candles=(candle(0), candle(1)), blocked_by_confidence=0, blocked_by_risk=0)
    assert loss_metrics["losing_trades"] == 1


def test_baselines_random_are_reproducible_and_buy_hold() -> None:
    predictions = [prediction(prediction_id=str(i), decision="BUY_CANDIDATE" if i % 2 == 0 else "HOLD") for i in range(10)]
    one = baseline_comparison(initial_capital=100, final_capital=110, first_close=100, last_close=125, predictions=predictions, seed=42)
    two = baseline_comparison(initial_capital=100, final_capital=110, first_close=100, last_close=125, predictions=predictions, seed=42)
    assert one == two
    assert one["buy_and_hold"]["final_capital"] == 125
    assert one["always_hold"]["final_capital"] == 100


def test_walk_forward_has_no_overlap() -> None:
    windows = build_walk_forward_windows(
        tuple(candle(i) for i in range(100)),
        WalkForwardConfig(window_count=3, min_segment_candles=1),
    )
    assert len(windows) == 3
    for window in windows:
        assert window.train[-1].open_time < window.validation[0].open_time
        assert window.validation[-1].open_time < window.test[0].open_time


class FakeRepository:
    def __init__(self, candles):
        self.candles = candles

    def load_history(self):
        from backend.trading.backtesting_v2.models import BacktestDataset

        return BacktestDataset(tuple(self.candles), "BTCUSDT", "5m", "v2")


def train_artifact(tmp_path):
    dataset = synthetic_dataset(180)
    target_name = "v2_long_tp_100bps_sl_50bps_h_24"
    config = MLEngineConfig(min_samples=120, min_class_count=5, artifacts_root=tmp_path / "ml_engine_v2")
    MLEnginePipeline(type("Repo", (), {"load_dataset": lambda self, **kwargs: dataset})(), config=config).train_target(
        symbol="BTCUSDT",
        interval="5m",
        target_name=target_name,
        models=("logistic_regression",),
    )
    candles = []
    for i, row in dataset.frame.tail(40).reset_index(drop=True).iterrows():
        features = {column: (0.0 if row[column] != row[column] else row[column]) for column in dataset.feature_columns}
        candles.append(candle(i, close=100 + i * 0.01, high=102, low=98, features=features))
    return config.artifacts_root, target_name, candles


def test_runner_infers_candle_by_candle_writes_reports_and_compares_thresholds(tmp_path) -> None:
    artifacts_root, target_name, candles = train_artifact(tmp_path)
    config = BacktestingConfig(
        target_name=target_name,
        artifacts_root=artifacts_root,
        output_root=tmp_path / "reports",
        min_candles=10,
        take_profit_thresholds=(0.50, 0.70),
        stop_loss_thresholds=(0.50,),
        paper_config=PaperTradingConfig(fee_bps=0, slippage_bps=0, spread_bps=0, cooldown_candles=0, min_confidence=0.0),
    )
    result = BacktestRunner(FakeRepository(candles), config).run()

    assert len(result.predictions) == len(candles)
    assert result.metadata["candles_processed"] == len(candles)
    assert len(result.threshold_comparison) == 2
    assert result.metadata["best_threshold_validation"] is not None
    for name in (
        "backtest_summary",
        "trades",
        "equity_curve",
        "drawdown_curve",
        "daily_results",
        "monthly_results",
        "signal_analysis",
        "threshold_comparison",
        "baseline_comparison",
        "walk_forward_results",
        "run_metadata",
    ):
        assert result.report_paths[name].exists()
