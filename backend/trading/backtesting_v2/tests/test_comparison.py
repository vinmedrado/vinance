from __future__ import annotations

from backend.trading.backtesting_v2.comparison import baseline_comparison, compare_thresholds, select_best_validation_threshold
from backend.trading.backtesting_v2.runner import BacktestRunner

from .helpers import FEATURE_COLUMNS, artifacts, config, history


def test_threshold_comparison_and_best_validation_selection(tmp_path) -> None:
    cfg = config(tmp_path, take_profit_thresholds=(0.50, 0.70), stop_loss_thresholds=(0.50, 0.70))
    rows_history = history(4, high=101.5)
    for item in rows_history:
        item.features = {column: 0.0 for column in FEATURE_COLUMNS}
    rows = compare_thresholds(cfg, rows_history, artifacts=artifacts())
    assert len(rows) == 4
    best = select_best_validation_threshold(rows)
    assert best in rows


def test_baselines_buy_hold_and_random_are_reproducible(tmp_path) -> None:
    cfg = config(tmp_path)
    rows = history(5, high=101.5)
    result = BacktestRunner(cfg, artifacts=artifacts()).run(rows, take_profit_threshold=0.60, stop_loss_threshold=0.60)
    first = baseline_comparison(result, rows, seed=42)
    second = baseline_comparison(result, rows, seed=42)
    assert first == second
    names = {item["baseline"] for item in first}
    assert {"buy_and_hold", "always_hold", "random_same_signal_count", "majority_class_hold", "model_without_confidence_filter"} <= names
