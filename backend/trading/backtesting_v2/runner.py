from __future__ import annotations

import hashlib
import json
import math
import subprocess
import time
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd

from backend.trading.ml_engine.config import PROHIBITED_FEATURE_COLUMNS
from backend.trading.prediction_engine.config import PredictionEngineConfig
from backend.trading.prediction_engine.decision import confidence_level, decide
from backend.trading.prediction_engine.errors import PredictionFeatureError
from backend.trading.prediction_engine.loader import PredictionArtifactLoader
from backend.trading.prediction_engine.models import (
    LoadedArtifacts,
    PredictionProbabilities,
    PredictionResult,
)

from .config import BacktestingConfig
from .metrics import calculate_backtest_metrics, daily_results, drawdown_curve, monthly_results, signal_analysis
from .models import (
    BacktestDataset,
    BacktestResult,
    BacktestRunContext,
    HistoricalCandle,
    HistoricalPrediction,
)
from .repository import validate_history
from .reports import BacktestingReportWriter
from .simulator import BacktestSimulator, validate_temporal_integrity
from .walk_forward import (
    build_walk_forward_windows,
    consolidate_walk_forward,
    select_validation_threshold,
)


@dataclass
class _SimulationOutcome:
    portfolio: Any
    predictions: list[PredictionResult]
    blocked: dict[str, int]
    metrics: dict[str, Any]
    seconds: float
    temporal_integrity: dict[str, int | bool]


class BacktestRunner:
    def __init__(
        self,
        config_or_repository,
        config: BacktestingConfig | None = None,
        *,
        artifacts: LoadedArtifacts | None = None,
        report_writer: BacktestingReportWriter | None = None,
    ) -> None:
        if isinstance(config_or_repository, BacktestingConfig):
            self.repository = None
            config = config_or_repository
        else:
            self.repository = config_or_repository
            config = config or BacktestingConfig()
        self.config = config
        prediction_config = PredictionEngineConfig(
            feature_version=config.feature_version,
            prediction_engine_version=config.prediction_engine_version,
            artifacts_root=config.artifacts_root,
            take_profit_threshold=config.take_profit_thresholds[0],
            stop_loss_threshold=config.stop_loss_thresholds[0],
            paper_only=True,
        )
        self.loader = PredictionArtifactLoader(prediction_config)
        self.artifacts = artifacts
        self.report_writer = report_writer or BacktestingReportWriter(config)
        self._commit = config.commit_hash or _commit_hash()
        self._timestamp = config.timestamp or datetime.now(timezone.utc).isoformat()

    def load_artifacts(self) -> LoadedArtifacts:
        if self.artifacts is None:
            entry = self.loader.select_best_model(
                symbol=self.config.symbol,
                interval=self.config.interval,
                target_name=self.config.target_name,
            )
            self.artifacts = self.loader.load_artifacts(entry)
        return self.artifacts

    def run(
        self,
        history: list[HistoricalCandle] | tuple[HistoricalCandle, ...] | None = None,
        *,
        take_profit_threshold: float | None = None,
        stop_loss_threshold: float | None = None,
    ) -> BacktestResult:
        total_started = time.perf_counter()
        history, load_history_seconds = self._load_history(history)
        validate_history(history, min_period_candles=self.config.min_period_candles)
        artifacts = self.load_artifacts()

        eligibility_started = time.perf_counter()
        feature_frame, eligible_records, eligibility = _eligible_feature_batch(history, artifacts.feature_columns)
        eligibility_filter_seconds = time.perf_counter() - eligibility_started

        preprocessing_seconds = 0.0
        inference_seconds = 0.0
        prediction_cache: tuple[HistoricalPrediction, ...] = ()
        if eligible_records:
            preprocessing_started = time.perf_counter()
            transformed = artifacts.preprocessing.transform(feature_frame)
            preprocessing_seconds = time.perf_counter() - preprocessing_started

            inference_started = time.perf_counter()
            prediction_cache = _batch_inference(artifacts, transformed, eligible_records)
            inference_seconds = time.perf_counter() - inference_started

        primary_pair = (
            self.config.take_profit_thresholds[0] if take_profit_threshold is None else take_profit_threshold,
            self.config.stop_loss_thresholds[0] if stop_loss_threshold is None else stop_loss_threshold,
        )
        threshold_pairs = [primary_pair]
        threshold_pairs.extend(pair for pair in self.config.threshold_pairs if pair != primary_pair)

        simulation_started = time.perf_counter()
        outcomes: dict[tuple[float, float], _SimulationOutcome] = {}
        for pair in threshold_pairs:
            pair_started = time.perf_counter()
            predictions = _materialize_predictions(
                prediction_cache,
                history,
                artifacts,
                self.config,
                take_profit_threshold=pair[0],
                stop_loss_threshold=pair[1],
            )
            portfolio, blocked, temporal_integrity = self._simulate(
                history,
                prediction_cache,
                predictions,
                show_progress=self.config.show_progress and pair == primary_pair,
            )
            metrics = calculate_backtest_metrics(
                trades=portfolio.trades,
                equity_curve=portfolio.equity_curve,
                predictions=predictions,
                blocked_reasons=blocked,
                initial_capital=portfolio.initial_capital,
                paper_config=self.config.paper_config,
                start_time=history[0].candle.open_time,
                end_time=history[-1].candle.open_time,
            )
            metrics.update(eligibility)
            metrics["candles_eligible"] = len(prediction_cache)
            metrics.update(temporal_integrity)
            outcomes[pair] = _SimulationOutcome(
                portfolio=portfolio,
                predictions=predictions,
                blocked=blocked,
                metrics=metrics,
                seconds=time.perf_counter() - pair_started,
                temporal_integrity=temporal_integrity,
            )
        simulation_seconds = time.perf_counter() - simulation_started

        primary = outcomes[primary_pair]
        run_context = self._context(history, artifacts, *primary_pair)
        run_context.metadata.update(eligibility)
        run_context.metadata["candles_eligible"] = len(prediction_cache)
        run_context.metadata.update(primary.temporal_integrity)
        result = BacktestResult(
            context=run_context,
            metrics=primary.metrics,
            trades=primary.portfolio.trades,
            equity_curve=primary.portfolio.equity_curve,
            drawdown_curve=drawdown_curve(primary.portfolio.equity_curve),
            daily_results=daily_results(primary.portfolio.trades, primary.portfolio.initial_capital),
            monthly_results=monthly_results(primary.portfolio.trades, primary.portfolio.initial_capital),
            signal_analysis=signal_analysis(primary.predictions, primary.portfolio.trades),
            predictions=primary.predictions,
            blocked_reasons=primary.blocked,
            prediction_cache=prediction_cache,
        )
        result.threshold_comparison = [
            _threshold_row(self._context(history, artifacts, *pair), pair, outcome)
            for pair, outcome in outcomes.items()
        ]
        result.context.metadata["best_threshold_validation"] = _select_best_threshold(result.threshold_comparison)

        from .comparison import baseline_comparison

        result.baseline_comparison = baseline_comparison(result, history, seed=self.config.seed)
        walk_forward_started = time.perf_counter()
        result.walk_forward_results = self._run_walk_forward(history, prediction_cache, artifacts)
        walk_forward_seconds = time.perf_counter() - walk_forward_started
        timings = {
            "load_history_seconds": load_history_seconds,
            "eligibility_filter_seconds": eligibility_filter_seconds,
            "preprocessing_seconds": preprocessing_seconds,
            "inference_seconds": inference_seconds,
            "simulation_seconds": simulation_seconds,
            "walk_forward_seconds": walk_forward_seconds,
            "reports_seconds": 0.0,
            "total_seconds": 0.0,
        }
        result.timings = timings
        result.metrics.update(timings)
        result.context.metadata.update(timings)

        reports_started = time.perf_counter()
        result.reports = self.report_writer.write_run(result, overwrite=self.config.overwrite)
        timings["reports_seconds"] = time.perf_counter() - reports_started
        timings["total_seconds"] = time.perf_counter() - total_started
        result.metrics.update(timings)
        result.context.metadata.update(timings)
        self.report_writer.write_named(
            result.context.output_dir,
            "backtest_summary",
            result.metrics,
            overwrite=True,
        )
        self.report_writer.write_named(
            result.context.output_dir,
            "run_metadata",
            result.context.metadata | {
                "run_id": result.context.run_id,
                "candles_processed": len(history),
            },
            overwrite=True,
        )
        return result

    def _load_history(
        self,
        history: list[HistoricalCandle] | tuple[HistoricalCandle, ...] | None,
    ) -> tuple[list[HistoricalCandle], float]:
        load_history_seconds = 0.0
        if history is None:
            if self.repository is None:
                raise ValueError("history must be provided when no repository is configured")
            started = time.perf_counter()
            loaded = self.repository.load_history()
            load_history_seconds = time.perf_counter() - started
            history = list(loaded.candles if isinstance(loaded, BacktestDataset) else loaded)
        else:
            history = list(history)
        if self.config.max_candles is not None:
            history = history[: self.config.max_candles]
        return history, load_history_seconds

    def _simulate(
        self,
        history: list[HistoricalCandle],
        prediction_cache: tuple[HistoricalPrediction, ...],
        predictions: list[PredictionResult],
        *,
        show_progress: bool,
        index_offset: int = 0,
    ) -> tuple[Any, dict[str, int], dict[str, int | bool]]:
        simulator = BacktestSimulator(self.config)
        portfolio = simulator.initial_state()
        blocked: dict[str, int] = {}
        prediction_by_index = {
            cached.history_index: prediction for cached, prediction in zip(prediction_cache, predictions)
        }
        checkpoints = (25, 50, 75, 100)
        next_checkpoint = 0

        for local_index, item in enumerate(history):
            index = index_offset + local_index
            prediction = prediction_by_index.get(index)
            try:
                execution = simulator.process_candle(
                    portfolio=portfolio,
                    candle=item,
                    candle_index=index,
                    prediction=prediction,
                )
            except ValueError as exc:
                reason = "confidence" if "below minimum" in str(exc) else "validation"
                blocked[reason] = blocked.get(reason, 0) + 1
            else:
                if prediction is not None:
                    if execution.opened_position is None and execution.reason not in {
                        "decision_hold",
                        "decision_avoid",
                    }:
                        blocked[execution.reason] = blocked.get(execution.reason, 0) + 1
            if show_progress:
                completed = (local_index + 1) * 100 / len(history)
                while next_checkpoint < len(checkpoints) and completed >= checkpoints[next_checkpoint]:
                    print(f"backtesting_v2 simulation {checkpoints[next_checkpoint]}%")
                    next_checkpoint += 1
        temporal_integrity = validate_temporal_integrity(portfolio.equity_curve)
        return portfolio, blocked, temporal_integrity

    def _run_walk_forward(
        self,
        history: list[HistoricalCandle],
        prediction_cache: tuple[HistoricalPrediction, ...],
        artifacts: LoadedArtifacts,
    ) -> dict[str, Any]:
        config = self.config.walk_forward
        if config.retrain_per_window:
            raise NotImplementedError("Walk-forward retraining is not enabled; the current model must remain frozen.")
        windows = build_walk_forward_windows(history, config)
        rows: list[dict[str, Any]] = []
        aggregate_test_trades: list[Any] = []

        for window in windows:
            validation_cache = tuple(
                item
                for item in prediction_cache
                if window.validation_start_index <= item.history_index < window.validation_end_index
            )
            validation_rows: list[dict[str, Any]] = []
            validation_outcomes: dict[tuple[float, float], _SimulationOutcome] = {}
            for tp, sl in config.threshold_pairs:
                predictions = _materialize_predictions(
                    validation_cache,
                    history,
                    artifacts,
                    self.config,
                    take_profit_threshold=tp,
                    stop_loss_threshold=sl,
                )
                started = time.perf_counter()
                portfolio, blocked, integrity = self._simulate(
                    window.validation,
                    validation_cache,
                    predictions,
                    show_progress=False,
                    index_offset=window.validation_start_index,
                )
                metrics = calculate_backtest_metrics(
                    trades=portfolio.trades,
                    equity_curve=portfolio.equity_curve,
                    predictions=predictions,
                    blocked_reasons=blocked,
                    initial_capital=portfolio.initial_capital,
                    paper_config=self.config.paper_config,
                    start_time=window.validation[0].open_time,
                    end_time=window.validation[-1].open_time,
                )
                metrics.update(integrity)
                outcome = _SimulationOutcome(
                    portfolio=portfolio,
                    predictions=predictions,
                    blocked=blocked,
                    metrics=metrics,
                    seconds=time.perf_counter() - started,
                    temporal_integrity=integrity,
                )
                validation_outcomes[(tp, sl)] = outcome
                validation_rows.append(
                    {
                        "threshold_tp": tp,
                        "threshold_sl": sl,
                        "trades": metrics["number_of_trades"],
                        "net_profit": metrics["net_profit"],
                        "profit_factor": metrics["profit_factor"],
                        "win_rate": metrics["win_rate"],
                        "expectancy": metrics["expectancy"],
                        "sharpe": metrics["sharpe"],
                        "max_drawdown": metrics["max_drawdown"],
                    }
                )

            selected = select_validation_threshold(
                validation_rows,
                criterion=config.selection_criterion,
            )
            selected_pair = (selected["threshold_tp"], selected["threshold_sl"])
            selected_validation = validation_outcomes[selected_pair]
            test_cache = tuple(
                item
                for item in prediction_cache
                if window.test_start_index <= item.history_index < window.test_end_index
            )
            test_predictions = _materialize_predictions(
                test_cache,
                history,
                artifacts,
                self.config,
                take_profit_threshold=selected_pair[0],
                stop_loss_threshold=selected_pair[1],
            )
            test_portfolio, test_blocked, test_integrity = self._simulate(
                window.test,
                test_cache,
                test_predictions,
                show_progress=False,
                index_offset=window.test_start_index,
            )
            test_metrics = calculate_backtest_metrics(
                trades=test_portfolio.trades,
                equity_curve=test_portfolio.equity_curve,
                predictions=test_predictions,
                blocked_reasons=test_blocked,
                initial_capital=test_portfolio.initial_capital,
                paper_config=self.config.paper_config,
                start_time=window.test[0].open_time,
                end_time=window.test[-1].open_time,
            )
            test_metrics.update(test_integrity)
            aggregate_test_trades.extend(test_portfolio.trades)
            rows.append(
                {
                    "window_id": window.index + 1,
                    "train_start": window.train[0].open_time.isoformat(),
                    "train_end": window.train[-1].open_time.isoformat(),
                    "validation_start": window.validation[0].open_time.isoformat(),
                    "validation_end": window.validation[-1].open_time.isoformat(),
                    "test_start": window.test[0].open_time.isoformat(),
                    "test_end": window.test[-1].open_time.isoformat(),
                    "candles_train": len(window.train),
                    "candles_validation": len(window.validation),
                    "candles_test": len(window.test),
                    "threshold_tp_selected": selected_pair[0],
                    "threshold_sl_selected": selected_pair[1],
                    "threshold_selected_from": "validation",
                    "model_retrained": False,
                    "trades_validation": selected_validation.metrics["number_of_trades"],
                    "trades_test": test_metrics["number_of_trades"],
                    "net_profit_validation": selected_validation.metrics["net_profit"],
                    "net_profit_test": test_metrics["net_profit"],
                    "profit_factor_validation": selected_validation.metrics["profit_factor"],
                    "profit_factor_test": test_metrics["profit_factor"],
                    "win_rate_validation": selected_validation.metrics["win_rate"],
                    "win_rate_test": test_metrics["win_rate"],
                    "expectancy_validation": selected_validation.metrics["expectancy"],
                    "expectancy_test": test_metrics["expectancy"],
                    "sharpe_validation": selected_validation.metrics["sharpe"],
                    "sharpe_test": test_metrics["sharpe"],
                    "max_drawdown_validation": selected_validation.metrics["max_drawdown"],
                    "max_drawdown_test": test_metrics["max_drawdown"],
                    "capital_start_test": test_portfolio.initial_capital,
                    "capital_end_test": test_metrics["capital_final"],
                    "temporal_integrity_validation": selected_validation.temporal_integrity,
                    "temporal_integrity_test": test_integrity,
                    "validation_threshold_results": validation_rows,
                }
            )

        return {
            "configuration": {
                "mode": config.mode,
                "window_count_requested": config.window_count,
                "selection_criterion": config.selection_criterion,
                "take_profit_thresholds": list(config.take_profit_thresholds),
                "stop_loss_thresholds": list(config.stop_loss_thresholds),
                "model_frozen": True,
            },
            "windows": rows,
            "consolidated": consolidate_walk_forward(rows, aggregate_test_trades),
        }

    def _context(
        self,
        history: list[HistoricalCandle],
        artifacts: LoadedArtifacts,
        take_profit_threshold: float,
        stop_loss_threshold: float,
    ) -> BacktestRunContext:
        model_version = str(artifacts.metadata.get("model_version") or artifacts.metadata.get("ml_engine_version"))
        metadata = {
            "engine_version": self.config.engine_version,
            "symbol": self.config.symbol,
            "interval": self.config.interval,
            "target_name": self.config.target_name,
            "model_name": artifacts.entry.model_name,
            "model_version": model_version,
            "ml_engine_version": artifacts.entry.ml_engine_version,
            "feature_version": self.config.feature_version,
            "prediction_engine_version": self.config.prediction_engine_version,
            "paper_trading_engine_version": self.config.paper_config.engine_version,
            "period_start": history[0].candle.open_time.isoformat(),
            "period_end": history[-1].candle.open_time.isoformat(),
            "candles": len(history),
            "max_candles": self.config.max_candles,
            "thresholds": {
                "take_profit": take_profit_threshold,
                "stop_loss": stop_loss_threshold,
            },
            "costs": {
                "fee_bps": self.config.paper_config.fee_bps,
                "slippage_bps": self.config.paper_config.slippage_bps,
                "spread_bps": self.config.paper_config.spread_bps,
            },
            "risk": {
                "fixed_fraction": self.config.paper_config.fixed_fraction,
                "min_confidence": self.config.paper_config.min_confidence,
                "cooldown_candles": self.config.paper_config.cooldown_candles,
                "max_open_positions": self.config.paper_config.max_open_positions,
                "max_daily_loss": self.config.paper_config.max_daily_loss,
                "max_capital_per_trade": self.config.paper_config.max_capital_per_trade,
                "max_position_size": self.config.paper_config.max_position_size,
            },
            "intracandle_policy": self.config.intracandle_policy,
            "walk_forward": {
                "enabled": self.config.walk_forward.enabled,
                "mode": self.config.walk_forward.mode,
                "window_count": self.config.walk_forward.window_count,
                "take_profit_thresholds": list(self.config.walk_forward.take_profit_thresholds),
                "stop_loss_thresholds": list(self.config.walk_forward.stop_loss_thresholds),
                "selection_criterion": self.config.walk_forward.selection_criterion,
                "model_frozen": not self.config.walk_forward.retrain_per_window,
            },
            "seed": self.config.seed,
            "timestamp": self._timestamp,
            "commit_hash": self._commit,
        }
        run_id = deterministic_run_id(metadata)
        return BacktestRunContext(
            run_id=run_id,
            symbol=self.config.symbol,
            interval=self.config.interval,
            target_name=self.config.target_name,
            model_name=artifacts.entry.model_name,
            model_version=model_version,
            feature_version=self.config.feature_version,
            prediction_engine_version=self.config.prediction_engine_version,
            paper_trading_engine_version=self.config.paper_config.engine_version,
            start_time=history[0].candle.open_time,
            end_time=history[-1].candle.open_time,
            take_profit_threshold=take_profit_threshold,
            stop_loss_threshold=stop_loss_threshold,
            output_dir=self.config.output_root / run_id,
            metadata=metadata,
        )


def _eligible_feature_batch(
    history: list[HistoricalCandle],
    feature_columns: tuple[str, ...],
) -> tuple[pd.DataFrame, tuple[tuple[int, HistoricalCandle], ...], dict[str, Any]]:
    required = set(feature_columns)
    rows: list[dict[str, Any]] = []
    for item in history:
        features = item.features
        leaked = sorted(set(features).intersection(PROHIBITED_FEATURE_COLUMNS))
        if leaked:
            raise PredictionFeatureError(f"Target leakage columns are not allowed for inference: {leaked}")
        missing = sorted(required.difference(features))
        if missing:
            extra = sorted(set(features).difference(required))
            raise PredictionFeatureError(f"Feature columns mismatch. missing={missing} extra={extra}")
        rows.append({column: features[column] for column in feature_columns})

    frame = pd.DataFrame(rows, columns=list(feature_columns))
    if frame.empty:
        valid_mask = np.zeros(0, dtype=bool)
    else:
        numeric = frame.apply(pd.to_numeric, errors="coerce")
        values = numeric.to_numpy(dtype=float, na_value=np.nan)
        valid_mask = np.isfinite(values).all(axis=1)

    valid_positions = np.flatnonzero(valid_mask)
    if len(valid_positions):
        first_valid = int(valid_positions[0])
        warmup_skipped = first_valid
        invalid_skipped = int((~valid_mask[first_valid + 1 :]).sum())
        first_eligible = history[first_valid].candle.open_time.isoformat()
    else:
        warmup_skipped = len(history)
        invalid_skipped = 0
        first_eligible = None
    eligible_records = tuple((index, history[index]) for index in valid_positions)
    eligible_frame = frame.loc[valid_mask, list(feature_columns)].reset_index(drop=True)
    metadata = {
        "warmup_candles_skipped": warmup_skipped,
        "invalid_feature_candles_skipped": invalid_skipped,
        "first_eligible_candle_time": first_eligible,
    }
    return eligible_frame, eligible_records, metadata


def _batch_inference(
    artifacts: LoadedArtifacts,
    transformed: Any,
    eligible_records: tuple[tuple[int, HistoricalCandle], ...],
) -> tuple[HistoricalPrediction, ...]:
    predicted = np.asarray(artifacts.model.predict(transformed)).reshape(-1)
    expected_rows = len(eligible_records)
    if len(predicted) != expected_rows:
        raise ValueError(f"Model returned {len(predicted)} predictions for {expected_rows} eligible candles")

    if hasattr(artifacts.model, "predict_proba"):
        raw_probabilities = np.asarray(artifacts.model.predict_proba(transformed), dtype=float)
        classes = getattr(artifacts.model, "classes_", None)
        if classes is None and hasattr(artifacts.model, "estimator"):
            classes = getattr(artifacts.model.estimator, "classes_", None)
        if classes is None:
            classes = np.array([-1, 0, 1])
        classes = np.asarray(classes).reshape(-1)
        if raw_probabilities.shape != (expected_rows, len(classes)):
            raise ValueError(
                "Model returned invalid probability output: "
                f"shape={raw_probabilities.shape}, expected=({expected_rows}, {len(classes)})"
            )
    else:
        classes = np.array([-1, 0, 1])
        raw_probabilities = np.zeros((expected_rows, 3), dtype=float)
        class_indexes = {int(label): index for index, label in enumerate(classes)}
        for row_index, label in enumerate(predicted):
            raw_probabilities[row_index, class_indexes[int(label)]] = 1.0

    class_indexes = {int(label): index for index, label in enumerate(classes)}
    cached: list[HistoricalPrediction] = []
    for row_index, (history_index, item) in enumerate(eligible_records):
        stop_loss = float(raw_probabilities[row_index, class_indexes[-1]]) if -1 in class_indexes else 0.0
        neutral = float(raw_probabilities[row_index, class_indexes[0]]) if 0 in class_indexes else 0.0
        take_profit = float(raw_probabilities[row_index, class_indexes[1]]) if 1 in class_indexes else 0.0
        confidence = max(stop_loss, neutral, take_profit)
        cached.append(
            HistoricalPrediction(
                history_index=history_index,
                candle_id=item.candle.candle_id,
                open_time=item.candle.open_time,
                predicted_class=int(predicted[row_index]),
                probability_stop_loss=stop_loss,
                probability_neutral=neutral,
                probability_take_profit=take_profit,
                confidence=confidence,
                confidence_level=confidence_level(confidence),
            )
        )
    return tuple(cached)


def _materialize_predictions(
    cached_predictions: tuple[HistoricalPrediction, ...],
    history: list[HistoricalCandle],
    artifacts: LoadedArtifacts,
    config: BacktestingConfig,
    *,
    take_profit_threshold: float,
    stop_loss_threshold: float,
) -> list[PredictionResult]:
    prediction_config = PredictionEngineConfig(
        feature_version=config.feature_version,
        prediction_engine_version=config.prediction_engine_version,
        artifacts_root=config.artifacts_root,
        take_profit_threshold=take_profit_threshold,
        stop_loss_threshold=stop_loss_threshold,
        paper_only=True,
    )
    model_version = str(artifacts.metadata.get("model_version") or artifacts.metadata.get("ml_engine_version"))
    predictions: list[PredictionResult] = []
    required = set(artifacts.feature_columns)
    for cached in cached_predictions:
        probabilities = PredictionProbabilities(
            probability_stop_loss=cached.probability_stop_loss,
            probability_neutral=cached.probability_neutral,
            probability_take_profit=cached.probability_take_profit,
        )
        decision = decide(probabilities, prediction_config)
        predictions.append(
            PredictionResult(
                prediction_id=_prediction_id(
                    symbol=config.symbol,
                    interval=config.interval,
                    target_name=artifacts.entry.target_name,
                    model_name=artifacts.entry.model_name,
                    candle_id=cached.candle_id,
                    model_version=model_version,
                    engine_version=config.prediction_engine_version,
                ),
                symbol=config.symbol,
                interval=config.interval,
                target_name=artifacts.entry.target_name,
                candle_id=cached.candle_id,
                open_time=cached.open_time,
                model_name=artifacts.entry.model_name,
                artifact_dir=artifacts.entry.artifact_dir,
                predicted_class=cached.predicted_class,
                probability_stop_loss=cached.probability_stop_loss,
                probability_neutral=cached.probability_neutral,
                probability_take_profit=cached.probability_take_profit,
                confidence=cached.confidence,
                confidence_level=cached.confidence_level,
                decision=decision,
                prediction_engine_version=config.prediction_engine_version,
                model_version=model_version,
                feature_version=config.feature_version,
                risk_score=cached.probability_stop_loss,
                expected_return=cached.probability_take_profit - cached.probability_stop_loss,
                expected_drawdown=cached.probability_stop_loss,
                loaded_manifest=artifacts.entry.metadata,
                reason={
                    "paper_only": True,
                    "feature_version": config.feature_version,
                    "ml_engine_version": artifacts.entry.ml_engine_version,
                    "artifact_generated_at": artifacts.entry.generated_at,
                    "take_profit_threshold": take_profit_threshold,
                    "stop_loss_threshold": stop_loss_threshold,
                    "decision_reason": _decision_reason(decision, probabilities, prediction_config),
                    "ignored_extra_features": sorted(
                        set(history[cached.history_index].features).difference(required)
                    ),
                },
            )
        )
    return predictions


def _threshold_row(
    context: BacktestRunContext,
    pair: tuple[float, float],
    outcome: _SimulationOutcome,
) -> dict[str, Any]:
    return {
        "run_id": context.run_id,
        "take_profit_threshold": pair[0],
        "stop_loss_threshold": pair[1],
        "capital_final": outcome.metrics["capital_final"],
        "total_return": outcome.metrics["total_return"],
        "net_profit": outcome.metrics["net_profit"],
        "profit_factor": outcome.metrics["profit_factor"],
        "win_rate": outcome.metrics["win_rate"],
        "number_of_trades": outcome.metrics["number_of_trades"],
        "simulation_seconds": outcome.seconds,
    }


def _select_best_threshold(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not rows:
        return None
    return sorted(
        rows,
        key=lambda row: (row["net_profit"], row["profit_factor"], -row["number_of_trades"]),
        reverse=True,
    )[0]


def deterministic_run_id(metadata: dict[str, Any]) -> str:
    stable = dict(metadata)
    stable.pop("timestamp", None)
    payload = json.dumps(stable, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


def _prediction_id(
    *,
    symbol: str,
    interval: str,
    target_name: str,
    model_name: str,
    candle_id: int,
    model_version: str,
    engine_version: str,
) -> str:
    raw = f"{symbol}|{interval}|{target_name}|{model_name}|{candle_id}|{model_version}|{engine_version}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def _decision_reason(
    decision: str,
    probabilities: PredictionProbabilities,
    config: PredictionEngineConfig,
) -> str:
    if decision == "AVOID":
        return f"probability_stop_loss >= {config.stop_loss_threshold}"
    if decision == "BUY_CANDIDATE":
        return f"probability_take_profit >= {config.take_profit_threshold}"
    return "no probability threshold reached"


def _has_valid_required_features(features: dict[str, Any], feature_columns: tuple[str, ...]) -> bool:
    leaked = sorted(set(features).intersection(PROHIBITED_FEATURE_COLUMNS))
    if leaked:
        raise PredictionFeatureError(f"Target leakage columns are not allowed for inference: {leaked}")
    missing = sorted(set(feature_columns).difference(features))
    if missing:
        extra = sorted(set(features).difference(feature_columns))
        raise PredictionFeatureError(f"Feature columns mismatch. missing={missing} extra={extra}")
    for column in feature_columns:
        try:
            numeric = pd.to_numeric(pd.Series([features[column]]), errors="coerce").iloc[0]
            if pd.isna(numeric) or not math.isfinite(float(numeric)):
                return False
        except (TypeError, ValueError, OverflowError):
            return False
    return True


def run_threshold(config: BacktestingConfig, history: list[HistoricalCandle], tp: float, sl: float) -> BacktestResult:
    runner = BacktestRunner(replace(config, take_profit_thresholds=(tp,), stop_loss_thresholds=(sl,)))
    return runner.run(history, take_profit_threshold=tp, stop_loss_threshold=sl)


def _commit_hash() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception:
        return None
    value = result.stdout.strip()
    return value or None
