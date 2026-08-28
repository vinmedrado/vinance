from __future__ import annotations

import random
from typing import Any

from backend.trading.prediction_engine.decision import BUY_CANDIDATE, HOLD
from backend.trading.prediction_engine.models import LoadedArtifacts

from .config import BacktestingConfig
from .models import BacktestResult, HistoricalCandle
from .runner import BacktestRunner


def compare_thresholds(
    config: BacktestingConfig,
    history: list[HistoricalCandle],
    *,
    artifacts: LoadedArtifacts | None = None,
) -> list[dict[str, Any]]:
    return BacktestRunner(config, artifacts=artifacts).run(history).threshold_comparison


def select_best_validation_threshold(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not rows:
        return None
    return sorted(rows, key=lambda row: (row["net_profit"], row["profit_factor"], -row["number_of_trades"]), reverse=True)[0]


def baseline_comparison(result: BacktestResult, history: list[HistoricalCandle], *, seed: int) -> list[dict[str, Any]]:
    buy_signals = result.metrics.get("signals_buy_candidate", 0)
    return [
        _buy_and_hold(history, result.metrics["capital_initial"]),
        {
            "baseline": "always_hold",
            "capital_final": result.metrics["capital_initial"],
            "total_return": 0.0,
            "number_of_trades": 0,
        },
        _random_entry(history, result.metrics["capital_initial"], buy_signals, seed=seed),
        {
            "baseline": "majority_class_hold",
            "capital_final": result.metrics["capital_initial"],
            "total_return": 0.0,
            "number_of_trades": 0,
        },
        {
            "baseline": "model_without_confidence_filter",
            "capital_final": result.metrics["capital_final"],
            "total_return": result.metrics["total_return"],
            "number_of_trades": result.metrics["number_of_trades"],
        },
    ]


def _buy_and_hold(history: list[HistoricalCandle], initial_capital: float) -> dict[str, Any]:
    if not history:
        final = initial_capital
    else:
        first = history[0].candle.close
        last = history[-1].candle.close
        final = initial_capital * (last / first) if first else initial_capital
    return {
        "baseline": "buy_and_hold",
        "capital_final": final,
        "total_return": final / initial_capital - 1,
        "number_of_trades": 1 if history else 0,
    }


def _random_entry(history: list[HistoricalCandle], initial_capital: float, count: int, *, seed: int) -> dict[str, Any]:
    rng = random.Random(seed)
    if not history or count <= 0:
        return {"baseline": "random_same_signal_count", "capital_final": initial_capital, "total_return": 0.0, "number_of_trades": 0}
    indexes = sorted(rng.sample(range(len(history)), k=min(count, len(history))))
    pnl = 0.0
    for index in indexes:
        entry = history[index].candle.close
        exit_index = min(index + 1, len(history) - 1)
        exit_price = history[exit_index].candle.close
        pnl += initial_capital * 0.02 * (exit_price / entry - 1)
    final = initial_capital + pnl
    return {
        "baseline": "random_same_signal_count",
        "capital_final": final,
        "total_return": final / initial_capital - 1,
        "number_of_trades": len(indexes),
    }
