from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime
from statistics import mean
from typing import Any, Iterable

import numpy as np


def pnl_metrics(pnls: Iterable[float], initial_capital: float) -> dict[str, float | int]:
    values = np.asarray(list(pnls), dtype=float)
    if values.size == 0:
        return {
            "trades": 0,
            "net_profit": 0.0,
            "return": 0.0,
            "profit_factor": 0.0,
            "expectancy": 0.0,
            "win_rate": 0.0,
            "sharpe": 0.0,
            "max_drawdown": 0.0,
        }
    wins = values[values > 0]
    losses = values[values < 0]
    gross_profit = float(wins.sum())
    gross_loss = float(losses.sum())
    equity = initial_capital + np.cumsum(values)
    peaks = np.maximum.accumulate(np.concatenate(([initial_capital], equity)))
    drawdowns = (peaks[1:] - equity) / np.maximum(peaks[1:], 1e-12)
    std = float(values.std())
    return {
        "trades": int(values.size),
        "net_profit": float(values.sum()),
        "return": float(values.sum() / initial_capital),
        "profit_factor": gross_profit / abs(gross_loss) if gross_loss else (math.inf if gross_profit else 0.0),
        "expectancy": float(values.mean()),
        "win_rate": float(wins.size / values.size),
        "sharpe": float(values.mean() / std) if std else 0.0,
        "max_drawdown": float(drawdowns.max()) if drawdowns.size else 0.0,
    }


def sensitivity_analysis(
    trades: list[dict[str, Any]],
    summary: dict[str, Any],
    metadata: dict[str, Any],
    *,
    seed: int,
) -> dict[str, Any]:
    pnls = np.asarray([float(trade["net_pnl"]) for trade in trades], dtype=float)
    initial = float(summary["capital_initial"])
    costs = float(summary.get("total_fees", 0.0)) + float(summary.get("total_slippage", 0.0)) + float(
        summary.get("total_spread", 0.0)
    )
    cost_rows = []
    for increase in (0.25, 0.50, 1.00):
        adjusted = _distribute_extra_cost(pnls, costs * increase)
        cost_rows.append({"cost_increase": increase, **pnl_metrics(adjusted, initial)})

    slippage_rows = []
    base_slippage_bps = float(metadata.get("costs", {}).get("slippage_bps", 0.0))
    current_slippage = float(summary.get("total_slippage", 0.0))
    for extra_pct in (0.0002, 0.0005, 0.0010):
        extra_bps = extra_pct * 10_000
        extra_cost = current_slippage * extra_bps / base_slippage_bps if base_slippage_bps > 0 else 0.0
        adjusted = _distribute_extra_cost(pnls, extra_cost)
        slippage_rows.append(
            {
                "additional_slippage_pct": extra_pct,
                "additional_slippage_bps": extra_bps,
                "estimated_additional_cost": extra_cost,
                "available": base_slippage_bps > 0,
                **pnl_metrics(adjusted, initial),
            }
        )

    win_rate_rows = []
    rng = np.random.default_rng(seed)
    win_indexes = np.flatnonzero(pnls > 0)
    average_loss = float(pnls[pnls < 0].mean()) if np.any(pnls < 0) else -abs(float(pnls.mean() or 1.0))
    order = rng.permutation(win_indexes)
    for reduction in (0.02, 0.05, 0.10):
        changed = pnls.copy()
        flip_count = min(len(order), int(math.ceil(len(pnls) * reduction)))
        changed[order[:flip_count]] = average_loss
        win_rate_rows.append(
            {
                "win_rate_reduction": reduction,
                "wins_converted_to_losses": flip_count,
                **pnl_metrics(changed, initial),
            }
        )

    return {
        "methodology": {
            "costs": "Existing aggregate fees, slippage and spread are increased and allocated equally per trade.",
            "slippage": "Additional slippage is scaled from reported slippage bps and allocated equally per trade.",
            "win_rate": "A deterministic seeded sample of winners is replaced by the historical average loss.",
        },
        "base": pnl_metrics(pnls, initial),
        "cost_increase": cost_rows,
        "win_rate_reduction": win_rate_rows,
        "slippage_increase": slippage_rows,
    }


def monte_carlo_analysis(
    trades: list[dict[str, Any]],
    *,
    initial_capital: float,
    simulations: int,
    confidence_level: float,
    seed: int,
) -> dict[str, Any]:
    pnls = np.asarray([float(trade["net_pnl"]) for trade in trades], dtype=float)
    if pnls.size == 0:
        return {"simulations": simulations, "trades_per_simulation": 0, "available": False}
    rng = np.random.default_rng(seed)
    samples = rng.choice(pnls, size=(simulations, pnls.size), replace=True)
    net_profits = samples.sum(axis=1)
    final_capitals = initial_capital + net_profits
    drawdowns = np.asarray([_max_drawdown(row, initial_capital) for row in samples])
    alpha = 1.0 - confidence_level
    var_value = float(np.quantile(net_profits, alpha))
    tail = net_profits[net_profits <= var_value]
    return {
        "available": True,
        "simulations": simulations,
        "trades_per_simulation": int(pnls.size),
        "seed": seed,
        "capital_final": _distribution(final_capitals, confidence_level),
        "net_profit": _distribution(net_profits, confidence_level),
        "drawdown_expected": float(drawdowns.mean()),
        "drawdown_median": float(np.median(drawdowns)),
        "drawdown_p95": float(np.quantile(drawdowns, 0.95)),
        "var_net_profit": var_value,
        "cvar_net_profit": float(tail.mean()) if tail.size else var_value,
        "worst_final_capital": float(final_capitals.min()),
        "best_final_capital": float(final_capitals.max()),
        "probability_of_profit": float(np.mean(net_profits > 0)),
    }


def bootstrap_analysis(
    trades: list[dict[str, Any]],
    *,
    initial_capital: float,
    iterations: int,
    confidence_level: float,
    seed: int,
) -> dict[str, Any]:
    pnls = np.asarray([float(trade["net_pnl"]) for trade in trades], dtype=float)
    if pnls.size == 0:
        return {"iterations": iterations, "available": False}
    rng = np.random.default_rng(seed)
    samples = rng.choice(pnls, size=(iterations, pnls.size), replace=True)
    metrics = [pnl_metrics(row, initial_capital) for row in samples]
    return {
        "available": True,
        "iterations": iterations,
        "confidence_level": confidence_level,
        "seed": seed,
        "methodology": "Seeded trade-level bootstrap; Sharpe is unannualized mean trade PnL divided by trade PnL standard deviation.",
        "net_profit": _metric_interval(metrics, "net_profit", confidence_level),
        "profit_factor": _metric_interval(metrics, "profit_factor", confidence_level),
        "expectancy": _metric_interval(metrics, "expectancy", confidence_level),
        "sharpe": _metric_interval(metrics, "sharpe", confidence_level),
    }


def stability_heatmaps(trades: list[dict[str, Any]], signal_analysis: dict[str, Any]) -> dict[str, Any]:
    groups: dict[str, dict[str, list[float]]] = {
        "month": defaultdict(list),
        "day_of_week": defaultdict(list),
        "hour": defaultdict(list),
        "duration": defaultdict(list),
    }
    for trade in trades:
        exit_time = _parse_time(str(trade["exit_time"]))
        pnl = float(trade["net_pnl"])
        groups["month"][exit_time.strftime("%Y-%m")].append(pnl)
        groups["day_of_week"][exit_time.strftime("%A")].append(pnl)
        groups["hour"][f"{exit_time.hour:02d}"].append(pnl)
        groups["duration"][_duration_bucket(int(trade.get("holding_candles", 0)))].append(pnl)
    return {
        "month": _heatmap(groups["month"]),
        "day_of_week": _heatmap(groups["day_of_week"]),
        "hour": _heatmap(groups["hour"]),
        "duration": _heatmap(groups["duration"]),
        "confidence": {
            "available_for_pnl": False,
            "reason": "Backtesting V2 persists confidence counts but does not link confidence to trades.",
            "signal_counts": signal_analysis.get("by_confidence", {}),
        },
        "volatility": {
            "available_for_pnl": False,
            "reason": "Backtesting V2 does not persist a volatility regime for each trade.",
            "signal_counts": signal_analysis.get("by_volatility_regime", {}),
        },
    }


def _distribute_extra_cost(pnls: np.ndarray, extra_cost: float) -> np.ndarray:
    if pnls.size == 0:
        return pnls.copy()
    return pnls - extra_cost / pnls.size


def _max_drawdown(pnls: np.ndarray, initial_capital: float) -> float:
    equity = initial_capital + np.cumsum(pnls)
    peaks = np.maximum.accumulate(np.concatenate(([initial_capital], equity)))[1:]
    return float(np.max((peaks - equity) / np.maximum(peaks, 1e-12)))


def _distribution(values: np.ndarray, confidence_level: float) -> dict[str, float]:
    alpha = (1.0 - confidence_level) / 2.0
    return {
        "mean": float(values.mean()),
        "median": float(np.median(values)),
        "std": float(values.std()),
        "minimum": float(values.min()),
        "maximum": float(values.max()),
        "ci_lower": float(np.quantile(values, alpha)),
        "ci_upper": float(np.quantile(values, 1.0 - alpha)),
    }


def _metric_interval(metrics: list[dict[str, Any]], key: str, confidence_level: float) -> dict[str, float | None]:
    values = np.asarray([float(row[key]) for row in metrics], dtype=float)
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return {"mean": None, "median": None, "ci_lower": None, "ci_upper": None, "finite_samples": 0}
    alpha = (1.0 - confidence_level) / 2.0
    return {
        "mean": float(finite.mean()),
        "median": float(np.median(finite)),
        "ci_lower": float(np.quantile(finite, alpha)),
        "ci_upper": float(np.quantile(finite, 1.0 - alpha)),
        "finite_samples": int(finite.size),
    }


def _heatmap(grouped: dict[str, list[float]]) -> list[dict[str, Any]]:
    rows = []
    for bucket in sorted(grouped):
        values = grouped[bucket]
        rows.append(
            {
                "bucket": bucket,
                "trades": len(values),
                "net_profit": float(sum(values)),
                "expectancy": float(mean(values)),
                "win_rate": sum(value > 0 for value in values) / len(values),
            }
        )
    return rows


def _duration_bucket(candles: int) -> str:
    if candles <= 6:
        return "01-06"
    if candles <= 12:
        return "07-12"
    if candles <= 18:
        return "13-18"
    return "19+"


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
