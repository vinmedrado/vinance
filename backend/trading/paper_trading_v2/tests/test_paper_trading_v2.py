from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from backend.trading.paper_trading_v2.config import PaperTradingConfig
from backend.trading.paper_trading_v2.executor import PaperTradingExecutor
from backend.trading.paper_trading_v2.models import MarketCandle
from backend.trading.paper_trading_v2.pipeline import PaperTradingPipeline
from backend.trading.paper_trading_v2.portfolio import PortfolioManager
from backend.trading.paper_trading_v2.reports import calculate_metrics
from backend.trading.prediction_engine.models import PredictionResult


def prediction(
    *,
    decision: str = "BUY_CANDIDATE",
    confidence: float = 0.80,
    prediction_id: str = "pred-1",
    candle_id: int = 1,
    model_version: str = "v2",
    feature_version: str = "v2",
    target_name: str = "v2_long_tp_100bps_sl_50bps_h_24",
    paper_only: bool = True,
) -> PredictionResult:
    return PredictionResult(
        prediction_id=prediction_id,
        symbol="BTCUSDT",
        interval="5m",
        target_name=target_name,
        candle_id=candle_id,
        open_time=dt(0),
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
        model_version=model_version,
        feature_version=feature_version,
        risk_score=0.10,
        expected_return=0.60,
        expected_drawdown=0.10,
        position_size=None,
        loaded_manifest={"model_name": "hist_gradient_boosting"},
        reason={"paper_only": paper_only},
    )


def candle(index: int, *, close: float = 100.0, high: float | None = None, low: float | None = None) -> MarketCandle:
    return MarketCandle(
        candle_id=index + 1,
        symbol="BTCUSDT",
        interval="5m",
        open_time=dt(index),
        open=close,
        high=high if high is not None else close,
        low=low if low is not None else close,
        close=close,
    )


def dt(minutes: int):
    return datetime(2026, 1, 1, 12, minutes, tzinfo=timezone.utc)


def state(config: PaperTradingConfig):
    return PortfolioManager(config).initial_state()


def test_open_position_and_control_capital() -> None:
    config = PaperTradingConfig(initial_capital=10_000, fixed_fraction=0.02, fee_bps=0, slippage_bps=0, spread_bps=0)
    portfolio = state(config)
    result = PaperTradingExecutor(config).execute(
        prediction=prediction(),
        entry_candle=candle(0),
        future_candles=[],
        portfolio=portfolio,
    )

    assert result.opened_position is not None
    assert result.opened_position.notional == 200
    assert result.opened_position.quantity == 2
    assert portfolio.cash == 9_800
    assert portfolio.invested_capital == 200


def test_hold_and_avoid_do_not_open() -> None:
    config = PaperTradingConfig()
    for decision in ("HOLD", "AVOID"):
        portfolio = state(config)
        result = PaperTradingExecutor(config).execute(
            prediction=prediction(decision=decision),
            entry_candle=candle(0),
            future_candles=[],
            portfolio=portfolio,
        )
        assert result.opened_position is None
        assert portfolio.positions == []


def test_idempotency_and_duplicate_prediction() -> None:
    config = PaperTradingConfig(fee_bps=0, slippage_bps=0, spread_bps=0)
    portfolio = state(config)
    executor = PaperTradingExecutor(config)
    executor.execute(prediction=prediction(), entry_candle=candle(0), future_candles=[], portfolio=portfolio)
    result = executor.execute(prediction=prediction(), entry_candle=candle(0), future_candles=[], portfolio=portfolio)

    assert result.opened_position is None
    assert result.reason == "duplicate_prediction"
    assert len(portfolio.positions) == 1


def test_risk_controls_max_positions_daily_loss_and_cooldown() -> None:
    config = PaperTradingConfig(max_open_positions=1, cooldown_candles=2, max_daily_loss=0.01)
    portfolio = state(config)
    executor = PaperTradingExecutor(config)
    executor.execute(prediction=prediction(prediction_id="p1"), entry_candle=candle(0), future_candles=[], portfolio=portfolio, candle_index=0)

    max_pos = executor.execute(prediction=prediction(prediction_id="p2", candle_id=2), entry_candle=candle(1), future_candles=[], portfolio=portfolio, candle_index=1)
    assert max_pos.reason == "max_open_positions"

    portfolio.positions.clear()
    cooldown = executor.execute(prediction=prediction(prediction_id="p3", candle_id=3), entry_candle=candle(2), future_candles=[], portfolio=portfolio, candle_index=1)
    assert cooldown.reason == "cooldown"

    portfolio.last_trade_index.clear()
    portfolio.daily_results[dt(0).date()] = -200
    daily_loss = executor.execute(prediction=prediction(prediction_id="p4", candle_id=4), entry_candle=candle(3), future_candles=[], portfolio=portfolio, candle_index=10)
    assert daily_loss.reason == "max_daily_loss"


def test_slippage_spread_and_fee_affect_prices_and_pnl() -> None:
    config = PaperTradingConfig(fixed_fraction=0.02, slippage_bps=10, spread_bps=4, fee_bps=10)
    portfolio = state(config)
    result = PaperTradingExecutor(config).execute(
        prediction=prediction(),
        entry_candle=candle(0, close=100),
        future_candles=[candle(1, close=101, high=102, low=100)],
        portfolio=portfolio,
    )

    assert result.opened_position is not None
    assert result.closed_trade is not None
    assert result.opened_position.entry_price == 100 * (1 + 12 / 10_000)
    assert result.closed_trade.fees > 0


def test_close_by_take_profit_stop_loss_and_horizon() -> None:
    config = PaperTradingConfig(fee_bps=0, slippage_bps=0, spread_bps=0, cooldown_candles=0)

    tp_result = PaperTradingExecutor(config).execute(
        prediction=prediction(prediction_id="tp"),
        entry_candle=candle(0, close=100),
        future_candles=[candle(1, close=100, high=101.5, low=100)],
        portfolio=state(config),
    )
    assert tp_result.closed_trade is not None
    assert tp_result.closed_trade.exit_reason == "TAKE_PROFIT"

    sl_result = PaperTradingExecutor(config).execute(
        prediction=prediction(prediction_id="sl"),
        entry_candle=candle(0, close=100),
        future_candles=[candle(1, close=100, high=100, low=99.4)],
        portfolio=state(config),
    )
    assert sl_result.closed_trade is not None
    assert sl_result.closed_trade.exit_reason == "STOP_LOSS"

    horizon_result = PaperTradingExecutor(config).execute(
        prediction=prediction(prediction_id="horizon", target_name="v2_long_tp_100bps_sl_50bps_h_2"),
        entry_candle=candle(0, close=100),
        future_candles=[candle(1, close=100.1, high=100.2, low=99.9), candle(2, close=100.2, high=100.3, low=99.9)],
        portfolio=state(config),
    )
    assert horizon_result.closed_trade is not None
    assert horizon_result.closed_trade.exit_reason == "HORIZON_EXPIRATION"


def test_portfolio_equity_curve_drawdown_and_metrics() -> None:
    config = PaperTradingConfig(fee_bps=0, slippage_bps=0, spread_bps=0)
    portfolio = state(config)
    result = PaperTradingExecutor(config).execute(
        prediction=prediction(),
        entry_candle=candle(0, close=100),
        future_candles=[candle(1, close=99.5, high=100, low=99.4)],
        portfolio=portfolio,
    )

    assert result.closed_trade is not None
    assert portfolio.equity_curve
    assert portfolio.max_drawdown >= 0
    metrics = calculate_metrics(portfolio.trades, portfolio.equity_curve, portfolio.initial_capital)
    assert metrics["number_of_trades"] == 1
    assert metrics["losing_trades"] == 1


def test_pipeline_writes_reports(tmp_path) -> None:
    class FakeRepository:
        def load_entry_candle(self, *, candle_id: int, symbol: str, interval: str):
            return candle(0, close=100)

        def load_future_candles(self, *, symbol: str, interval: str, after_open_time, limit: int):
            return [candle(1, high=101.5, low=100, close=101)]

    config = PaperTradingConfig(output_root=tmp_path, fee_bps=0, slippage_bps=0, spread_bps=0)
    result = PaperTradingPipeline(FakeRepository(), config=config).run_prediction(prediction())

    assert result.reports["positions"].exists()
    assert result.reports["equity_curve"].exists()
    assert result.reports["portfolio_summary"].exists()
    assert result.reports["daily_results"].exists()
    assert result.reports["trade_log"].exists()


def test_paper_only_and_version_validations() -> None:
    config = PaperTradingConfig()
    executor = PaperTradingExecutor(config)
    cases = [
        prediction(paper_only=False),
        prediction(feature_version="v1"),
        prediction(target_name="v1_long_tp_100bps_sl_50bps_h_24"),
        prediction(model_version=""),
        prediction(confidence=0.10),
    ]
    for item in cases:
        try:
            executor.execute(prediction=item, entry_candle=candle(0), future_candles=[], portfolio=state(config))
        except (RuntimeError, ValueError):
            pass
        else:
            raise AssertionError("Expected validation failure")
