from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from typing import Any

from .config import WalkForwardConfig
from .models import HistoricalCandle


@dataclass(frozen=True)
class WalkForwardWindow:
    train: list[HistoricalCandle]
    validation: list[HistoricalCandle]
    test: list[HistoricalCandle]
    index: int
    train_start_index: int
    train_end_index: int
    validation_start_index: int
    validation_end_index: int
    test_start_index: int
    test_end_index: int


def build_walk_forward_windows(
    history: list[HistoricalCandle],
    config: WalkForwardConfig | None = None,
    *,
    train_size: int | None = None,
    validation_size: int | None = None,
    test_size: int | None = None,
    step_size: int | None = None,
) -> list[WalkForwardWindow]:
    config = config or WalkForwardConfig(
        train_size=train_size,
        validation_size=validation_size,
        test_size=test_size,
        step_size=step_size,
        window_count=max(len(history), 1),
        min_segment_candles=1,
    )
    if not config.enabled:
        return []
    train_size, validation_size, test_size = _resolve_sizes(len(history), config)
    if min(train_size, validation_size, test_size) < config.min_segment_candles:
        return []
    advance = config.step_size or validation_size + test_size
    if advance < validation_size + test_size:
        raise ValueError("walk-forward step_size cannot overlap validation or test periods")

    windows: list[WalkForwardWindow] = []
    cursor = train_size
    for index in range(config.window_count):
        validation_start = cursor
        validation_end = validation_start + validation_size
        test_start = validation_end
        test_end = test_start + test_size
        if test_end > len(history):
            break
        train_start = 0 if config.mode == "expanding" else max(0, cursor - train_size)
        train_end = cursor
        train = history[train_start:train_end]
        validation = history[validation_start:validation_end]
        test = history[test_start:test_end]
        _validate_no_overlap(train, validation, test)
        windows.append(
            WalkForwardWindow(
                train=train,
                validation=validation,
                test=test,
                index=index,
                train_start_index=train_start,
                train_end_index=train_end,
                validation_start_index=validation_start,
                validation_end_index=validation_end,
                test_start_index=test_start,
                test_end_index=test_end,
            )
        )
        cursor += advance
    return windows


def select_validation_threshold(
    rows: list[dict[str, Any]],
    criterion: str = "sharpe_drawdown_net_profit",
) -> dict[str, Any]:
    if not rows:
        raise ValueError("validation threshold results must not be empty")
    qualified = [
        row
        for row in rows
        if row["expectancy"] > 0 and row["profit_factor"] > 1
    ]
    candidates = qualified or rows
    if criterion in {"net_profit", "profit_factor", "expectancy"}:
        return max(
            candidates,
            key=lambda row: (
                row[criterion],
                row["sharpe"],
                -row["max_drawdown"],
                row["net_profit"],
            ),
        )
    return max(
        candidates,
        key=lambda row: (
            row["sharpe"],
            -row["max_drawdown"],
            row["net_profit"],
        ),
    )


def consolidate_walk_forward(
    rows: list[dict[str, Any]],
    test_trades: list[Any],
) -> dict[str, Any]:
    pnls = [trade.net_pnl for trade in test_trades]
    wins = [value for value in pnls if value > 0]
    losses = [value for value in pnls if value < 0]
    gross_profit = sum(wins)
    gross_loss = sum(losses)
    threshold_frequency = Counter(
        f"{row['threshold_tp_selected']:.2f}/{row['threshold_sl_selected']:.2f}"
        for row in rows
    )
    total_trades = len(pnls)
    aggregate_net = sum(pnls)
    weighted_sharpe = _weighted_average(
        [(row["sharpe_test"], row["trades_test"]) for row in rows]
    )
    return {
        "total_windows": len(rows),
        "positive_test_windows": sum(row["net_profit_test"] > 0 for row in rows),
        "negative_test_windows": sum(row["net_profit_test"] < 0 for row in rows),
        "neutral_test_windows": sum(row["net_profit_test"] == 0 for row in rows),
        "aggregate_test_trades": total_trades,
        "aggregate_test_net_profit": aggregate_net,
        "aggregate_test_profit_factor": (
            gross_profit / abs(gross_loss)
            if gross_loss
            else (math.inf if gross_profit else 0.0)
        ),
        "aggregate_test_win_rate": len(wins) / total_trades if total_trades else 0.0,
        "aggregate_test_expectancy": aggregate_net / total_trades if total_trades else 0.0,
        "aggregate_test_sharpe": weighted_sharpe,
        "aggregate_test_max_drawdown": max(
            (row["max_drawdown_test"] for row in rows),
            default=0.0,
        ),
        "threshold_selection_frequency": dict(sorted(threshold_frequency.items())),
        "out_of_sample_positive": aggregate_net > 0,
    }


def summarize_walk_forward(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "windows": rows,
        "window_count": len(rows),
        "total_net_profit": sum(row.get("net_profit_test", row.get("test_net_profit", 0.0)) for row in rows),
    }


def _resolve_sizes(total: int, config: WalkForwardConfig) -> tuple[int, int, int]:
    if config.train_size is not None:
        return config.train_size, config.validation_size or 0, config.test_size or 0
    unit = total // (4 + 2 * config.window_count)
    return 4 * unit, unit, unit


def _weighted_average(values: list[tuple[float, int]]) -> float:
    total_weight = sum(weight for _, weight in values)
    if not total_weight:
        return 0.0
    return sum(value * weight for value, weight in values) / total_weight


def _validate_no_overlap(
    train: list[HistoricalCandle],
    validation: list[HistoricalCandle],
    test: list[HistoricalCandle],
) -> None:
    groups = [train, validation, test]
    seen: set[int] = set()
    for group in groups:
        ids = {item.candle.candle_id for item in group}
        if seen.intersection(ids):
            raise ValueError("walk-forward windows contain overlapping candle ids")
        seen.update(ids)
    for left, right in ((train, validation), (validation, test)):
        if left and right and left[-1].candle.open_time >= right[0].candle.open_time:
            raise ValueError("walk-forward windows must preserve temporal order without overlap")
