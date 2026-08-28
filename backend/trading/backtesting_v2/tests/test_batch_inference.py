from __future__ import annotations

import pytest

from backend.trading.backtesting_v2.runner import BacktestRunner
from backend.trading.backtesting_v2.simulator import BacktestingPaperExecutor, horizon_for_target
from backend.trading.paper_trading_v2.portfolio import PortfolioManager
from backend.trading.prediction_engine.config import PredictionEngineConfig
from backend.trading.prediction_engine.models import PredictionInput
from backend.trading.prediction_engine.predictor import PredictionPredictor

from .helpers import StaticModel, artifacts, config, history


def _single_candle_predictions(rows, loaded, cfg):
    predictor = PredictionPredictor(
        PredictionEngineConfig(
            feature_version=cfg.feature_version,
            prediction_engine_version=cfg.prediction_engine_version,
            artifacts_root=cfg.artifacts_root,
            take_profit_threshold=cfg.take_profit_thresholds[0],
            stop_loss_threshold=cfg.stop_loss_thresholds[0],
            paper_only=True,
        )
    )
    return [
        predictor.predict(
            PredictionInput(
                candle_id=item.candle_id,
                symbol=item.symbol,
                interval=item.interval,
                open_time=item.open_time,
                close=item.close,
                features=item.features,
            ),
            loaded,
        )
        for item in rows
    ]


def test_batch_predictions_match_single_candle_predictions(tmp_path) -> None:
    rows = history(6)
    for item in rows:
        item.features["legitimate_extra"] = 123.0
    cfg = config(tmp_path)
    batch = BacktestRunner(cfg, artifacts=artifacts(StaticModel())).run(rows)
    singles = _single_candle_predictions(rows, artifacts(StaticModel()), cfg)

    assert len(batch.predictions) == len(singles)
    for actual, expected in zip(batch.predictions, singles):
        assert actual.candle_id == expected.candle_id
        assert actual.predicted_class == expected.predicted_class
        assert actual.decision == expected.decision
        assert actual.probability_stop_loss == pytest.approx(expected.probability_stop_loss)
        assert actual.probability_neutral == pytest.approx(expected.probability_neutral)
        assert actual.probability_take_profit == pytest.approx(expected.probability_take_profit)
        assert actual.confidence == pytest.approx(expected.confidence)


def test_batch_work_is_performed_once_for_multiple_thresholds(tmp_path) -> None:
    model = StaticModel((0.10, 0.20, 0.70))
    loaded = artifacts(model)
    cfg = config(
        tmp_path,
        take_profit_thresholds=(0.50, 0.70),
        stop_loss_thresholds=(0.50, 0.70),
    )

    result = BacktestRunner(cfg, artifacts=loaded).run(history(8))

    assert loaded.preprocessing.transform_calls == 1
    assert model.predict_calls == 1
    assert model.predict_proba_calls == 1
    assert len(model.seen_frames) == 1
    assert len(result.prediction_cache) == 8
    assert len(result.threshold_comparison) == 4


def test_batch_financial_result_matches_sequential_prediction_flow(tmp_path) -> None:
    rows = history(6, high=101.5, low=100.0)
    cfg = config(tmp_path / "batch")
    batch = BacktestRunner(cfg, artifacts=artifacts(StaticModel())).run(rows)

    loaded = artifacts(StaticModel())
    sequential_predictions = _single_candle_predictions(rows, loaded, cfg)
    executor = BacktestingPaperExecutor(cfg.paper_config, intracandle_policy=cfg.intracandle_policy)
    manager = PortfolioManager(cfg.paper_config)
    portfolio = manager.initial_state()
    horizon = horizon_for_target(cfg.target_name)
    for index, (item, prediction) in enumerate(zip(rows, sequential_predictions)):
        executor.execute(
            prediction=prediction,
            entry_candle=item.candle,
            future_candles=[future.candle for future in rows[index + 1 : index + 1 + horizon]],
            portfolio=portfolio,
            candle_index=index,
        )
        manager.mark_to_market(portfolio, timestamp=item.open_time, last_price=item.close)

    assert batch.metrics["capital_final"] == pytest.approx(portfolio.equity)
    assert len(batch.trades) == len(portfolio.trades)
    assert [trade.exit_reason for trade in batch.trades] == [trade.exit_reason for trade in portfolio.trades]
    assert [trade.net_pnl for trade in batch.trades] == pytest.approx(
        [trade.net_pnl for trade in portfolio.trades]
    )


def test_max_candles_limits_ordered_history_without_changing_default(tmp_path) -> None:
    rows = history(7)
    limited = BacktestRunner(
        config(tmp_path / "limited", max_candles=3),
        artifacts=artifacts(StaticModel()),
    ).run(rows)
    complete = BacktestRunner(
        config(tmp_path / "complete"),
        artifacts=artifacts(StaticModel()),
    ).run(rows)

    assert len(limited.predictions) == 3
    assert limited.context.end_time == rows[2].open_time
    assert limited.context.metadata["candles"] == 3
    assert len(complete.predictions) == 7


def test_stage_timings_are_reported(tmp_path) -> None:
    result = BacktestRunner(config(tmp_path), artifacts=artifacts(StaticModel())).run(history(4))
    expected = {
        "load_history_seconds",
        "eligibility_filter_seconds",
        "preprocessing_seconds",
        "inference_seconds",
        "simulation_seconds",
        "walk_forward_seconds",
        "reports_seconds",
        "total_seconds",
    }
    assert expected == set(result.timings)
    assert all(result.timings[name] >= 0 for name in expected)
    assert expected.issubset(result.metrics)
    assert expected.issubset(result.context.metadata)
