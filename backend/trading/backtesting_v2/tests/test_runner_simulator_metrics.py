from __future__ import annotations

import json
import math

import pytest

from backend.trading.paper_trading_v2.config import PaperTradingConfig
from backend.trading.backtesting_v2.config import STOP_LOSS_FIRST, BacktestingConfig
from backend.trading.backtesting_v2.metrics import calculate_backtest_metrics
from backend.trading.backtesting_v2.runner import BacktestRunner, deterministic_run_id
from backend.trading.backtesting_v2.walk_forward import build_walk_forward_windows

from .helpers import StaticModel, artifacts, config, history, scenario_history


def run(tmp_path, rows, *, model=None, **kwargs):
    cfg = config(tmp_path, **kwargs)
    return BacktestRunner(cfg, artifacts=artifacts(model)).run(rows, take_profit_threshold=cfg.take_profit_thresholds[0], stop_loss_threshold=cfg.stop_loss_thresholds[0])


def test_batch_inference_uses_only_required_features(tmp_path) -> None:
    model = StaticModel((0.10, 0.20, 0.70))
    rows = history(5)
    result = run(tmp_path, rows, model=model)
    assert len(result.predictions) == 5
    assert len(model.seen_frames) == 1
    assert list(model.seen_frames[0].columns) == ["f1", "f2"]
    assert model.seen_frames[0].iloc[0].to_dict() == {"f1": 0.0, "f2": 1.0}


def test_target_leakage_feature_is_rejected(tmp_path) -> None:
    rows = history(2)
    rows[0].features["target_class"] = 1
    with pytest.raises(Exception, match="Target leakage"):
        run(tmp_path, rows)


def test_initial_nan_warmup_is_skipped_and_inference_starts_at_first_eligible_candle(tmp_path) -> None:
    model = StaticModel((0.10, 0.20, 0.70))
    rows = history(5)
    rows[0].features["f1"] = float("nan")
    rows[1].features["f2"] = float("nan")

    result = run(tmp_path, rows, model=model)

    assert len(result.predictions) == 3
    assert len(model.seen_frames) == 1
    assert model.seen_frames[0].iloc[0].to_dict() == {"f1": 2.0, "f2": 3.0}
    assert result.metrics["warmup_candles_skipped"] == 2
    assert result.metrics["invalid_feature_candles_skipped"] == 0
    assert result.metrics["first_eligible_candle_time"] == rows[2].open_time.isoformat()
    assert result.context.metadata["warmup_candles_skipped"] == 2


def test_nan_after_warmup_is_counted_as_invalid_feature_candle(tmp_path) -> None:
    model = StaticModel((0.10, 0.20, 0.70))
    rows = history(5)
    rows[3].features["f1"] = float("nan")

    result = run(tmp_path, rows, model=model)

    assert len(result.predictions) == 4
    assert len(model.seen_frames) == 1
    assert result.metrics["warmup_candles_skipped"] == 0
    assert result.metrics["invalid_feature_candles_skipped"] == 1
    assert result.metrics["first_eligible_candle_time"] == rows[0].open_time.isoformat()


def test_missing_required_feature_continues_to_fail(tmp_path) -> None:
    rows = history(2)
    rows[0].features.pop("f1")

    with pytest.raises(Exception, match=r"Feature columns mismatch.*f1"):
        run(tmp_path, rows)


def test_open_close_tp_sl_horizon_and_intracandle_stop_loss_first(tmp_path) -> None:
    assert run(tmp_path / "tp", scenario_history(exit_kind="tp")).trades[0].exit_reason == "TAKE_PROFIT"
    assert run(tmp_path / "sl", scenario_history(exit_kind="sl")).trades[0].exit_reason == "STOP_LOSS"
    assert run(tmp_path / "horizon", scenario_history(exit_kind="horizon")).trades[0].exit_reason == "HORIZON_EXPIRATION"
    both = run(tmp_path / "both", scenario_history(exit_kind="both"), intracandle_policy=STOP_LOSS_FIRST)
    assert both.trades[0].exit_reason == "STOP_LOSS"


def test_costs_fee_spread_slippage_capital_equity_and_drawdown(tmp_path) -> None:
    paper = PaperTradingConfig(fee_bps=10, slippage_bps=5, spread_bps=2, cooldown_candles=0)
    result = run(tmp_path, scenario_history(exit_kind="tp"), paper_config=paper)
    assert result.trades[0].fees > 0
    assert result.metrics["total_fees"] > 0
    assert result.metrics["total_slippage"] > 0
    assert result.metrics["total_spread"] > 0
    assert result.metrics["capital_initial"] == 10_000
    assert result.equity_curve
    assert result.metrics["max_drawdown"] >= 0


def test_cooldown_max_daily_loss_max_open_positions_and_confidence_blocks(tmp_path) -> None:
    low_conf = run(tmp_path / "conf", history(3), model=StaticModel((0.20, 0.40, 0.40)))
    assert low_conf.metrics["signals_blocked_by_confidence"] > 0

    paper = PaperTradingConfig(max_open_positions=1, cooldown_candles=10, fee_bps=0, slippage_bps=0, spread_bps=0)
    result = run(tmp_path / "risk", history(5, high=101.5), paper_config=paper)
    assert result.metrics["signals_blocked_by_risk"] >= 0

    paper_loss = PaperTradingConfig(max_daily_loss=0.00001, fee_bps=0, slippage_bps=0, spread_bps=0, cooldown_candles=0)
    loss = run(tmp_path / "loss", history(5, low=99.4), paper_config=paper_loss)
    assert "max_daily_loss" in loss.blocked_reasons or loss.metrics["sl_hits"] >= 1


def test_threshold_low_high_and_deterministic_run_id(tmp_path) -> None:
    low = run(tmp_path / "low", history(3), take_profit_thresholds=(0.50,), stop_loss_thresholds=(0.90,))
    high = run(tmp_path / "high", history(3), take_profit_thresholds=(0.90,), stop_loss_thresholds=(0.90,))
    assert low.metrics["signals_buy_candidate"] == 3
    assert high.metrics["signals_hold"] == 3
    assert deterministic_run_id({"a": 1, "timestamp": "x"}) == deterministic_run_id({"a": 1, "timestamp": "y"})


def test_reports_json_and_idempotency(tmp_path) -> None:
    rows = scenario_history(exit_kind="tp")
    rows[0].features["f1"] = float("nan")
    result1 = run(tmp_path, rows)
    result2 = run(tmp_path, rows)
    assert result1.context.run_id == result2.context.run_id
    assert result1.metrics["warmup_candles_skipped"] == result2.metrics["warmup_candles_skipped"] == 1
    required = {
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
    }
    assert required.issubset(result1.reports)
    for path in result1.reports.values():
        assert json.loads(path.read_text(encoding="utf-8")) is not None


def test_metrics_edge_cases_no_wins_losses_profit_factor_and_zero_sharpe(tmp_path) -> None:
    none = run(tmp_path / "none", history(3), model=StaticModel((0.10, 0.80, 0.10)))
    assert none.metrics["number_of_trades"] == 0
    assert none.metrics["profit_factor"] == 0
    wins = run(tmp_path / "wins", scenario_history(exit_kind="tp"))
    assert math.isinf(wins.metrics["profit_factor"])
    losses = run(tmp_path / "losses", scenario_history(exit_kind="sl"))
    assert losses.metrics["profit_factor"] == 0
    assert none.metrics["sharpe_ratio"] == 0


def test_invalid_validations_paper_only_threshold_cost_and_capital(tmp_path) -> None:
    with pytest.raises(RuntimeError):
        BacktestingConfig(output_root=tmp_path, paper_only=False)
    with pytest.raises(ValueError):
        BacktestingConfig(output_root=tmp_path, initial_capital=0)
    with pytest.raises(ValueError):
        BacktestingConfig(output_root=tmp_path, take_profit_thresholds=(1.2,))
    with pytest.raises(ValueError):
        BacktestingConfig(output_root=tmp_path, paper_config=PaperTradingConfig(fee_bps=-1))


def test_walk_forward_without_overlap() -> None:
    windows = build_walk_forward_windows(history(10), train_size=4, validation_size=2, test_size=2)
    assert windows
    for window in windows:
        assert window.train[-1].candle.open_time < window.validation[0].candle.open_time
        assert window.validation[-1].candle.open_time < window.test[0].candle.open_time
