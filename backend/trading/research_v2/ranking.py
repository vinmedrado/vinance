from __future__ import annotations

import math
from collections import defaultdict
from statistics import mean, median, pstdev
from typing import Any


RANKING_WEIGHTS = {
    "profit_factor": 0.30,
    "expectancy": 0.20,
    "sharpe": 0.20,
    "sortino": 0.10,
    "drawdown": 0.10,
    "robustness": 0.10,
}


def aggregate_threshold_grid(walk_forward: dict[str, Any], *, minimum_trades: int) -> list[dict[str, Any]]:
    grouped: dict[tuple[float, float], list[dict[str, Any]]] = defaultdict(list)
    windows = walk_forward.get("windows", [])
    for window in windows:
        for row in window.get("validation_threshold_results", []):
            key = (float(row["threshold_tp"]), float(row["threshold_sl"]))
            grouped[key].append(row)

    aggregates = []
    for (tp, sl), rows in sorted(grouped.items()):
        trades = sum(int(row.get("trades", 0)) for row in rows)
        expectancies = [float(row.get("expectancy", 0.0)) for row in rows]
        sharpes = [float(row.get("sharpe", 0.0)) for row in rows]
        drawdowns = [float(row.get("max_drawdown", 0.0)) for row in rows]
        pfs = [float(row.get("profit_factor", 0.0)) for row in rows]
        net_profits = [float(row.get("net_profit", 0.0)) for row in rows]
        weights = [max(int(row.get("trades", 0)), 1) for row in rows]
        consistency = sum(exp > 0 and pf > 1 for exp, pf in zip(expectancies, pfs)) / len(rows)
        variation = _coefficient_of_variation(expectancies)
        sample_score = min(trades / max(minimum_trades * len(rows), 1), 1.0)
        drawdown_score = 1.0 - min(mean(drawdowns) / 0.05, 1.0)
        sensitivity_score = 1.0 / (1.0 + variation)
        pf_value = _finite_median(pfs)
        robustness = 100.0 * (
            0.35 * consistency
            + 0.20 * sample_score
            + 0.20 * drawdown_score
            + 0.15 * sensitivity_score
            + 0.10 * min(_bounded(pf_value) / 2.0, 1.0)
        )
        aggregates.append(
            {
                "threshold_tp": tp,
                "threshold_sl": sl,
                "windows": len(rows),
                "trades": trades,
                "net_profit": float(sum(net_profits)),
                "profit_factor": pf_value,
                "expectancy": _weighted_mean(expectancies, weights),
                "sharpe": _weighted_mean(sharpes, weights),
                "sortino": None,
                "sortino_available": False,
                "max_drawdown": max(drawdowns, default=0.0),
                "mean_drawdown": mean(drawdowns) if drawdowns else 0.0,
                "positive_windows_ratio": consistency,
                "expectancy_variation": variation,
                "threshold_robustness_score": robustness,
            }
        )
    return aggregates


def rank_thresholds(aggregates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not aggregates:
        return []
    scores = {
        "profit_factor": _normalize([_bounded(row["profit_factor"]) for row in aggregates]),
        "expectancy": _normalize([float(row["expectancy"]) for row in aggregates]),
        "sharpe": _normalize([float(row["sharpe"]) for row in aggregates]),
        "drawdown": _normalize([float(row["max_drawdown"]) for row in aggregates], inverse=True),
        "robustness": _normalize([float(row["threshold_robustness_score"]) for row in aggregates]),
    }
    ranked = []
    for index, row in enumerate(aggregates):
        components = {
            "profit_factor": scores["profit_factor"][index],
            "expectancy": scores["expectancy"][index],
            "sharpe": scores["sharpe"][index],
            "sortino": 0.5,
            "drawdown": scores["drawdown"][index],
            "robustness": scores["robustness"][index],
        }
        composite = 100.0 * sum(RANKING_WEIGHTS[key] * components[key] for key in RANKING_WEIGHTS)
        ranked.append({**row, "ranking_components": components, "composite_score": composite})
    ranked.sort(
        key=lambda row: (
            row["composite_score"],
            row["threshold_robustness_score"],
            row["trades"],
            -row["max_drawdown"],
        ),
        reverse=True,
    )
    for position, row in enumerate(ranked, start=1):
        row["rank"] = position
    return ranked


def threshold_regions(ranking: list[dict[str, Any]]) -> dict[str, Any]:
    if not ranking:
        return {
            "most_robust_tp": None,
            "most_robust_sl": None,
            "stable_region": [],
            "unstable_region": [],
        }
    composite_median = median(row["composite_score"] for row in ranking)
    stable_floor = max(composite_median, 40.0)
    stable = [
        _pair(row)
        for row in ranking
        if row["composite_score"] >= stable_floor
        and row["profit_factor"] > 1
        and row["expectancy"] > 0
        and row["positive_windows_ratio"] >= 0.5
    ]
    unstable = [
        _pair(row)
        for row in ranking
        if row["profit_factor"] <= 1
        or row["expectancy"] <= 0
        or row["positive_windows_ratio"] < 0.5
        or row["composite_score"] < 40
    ]
    tp_values = sorted({float(row["threshold_tp"]) for row in ranking})
    sl_values = sorted({float(row["threshold_sl"]) for row in ranking})
    return {
        "most_robust_tp": _best_dimension(ranking, "threshold_tp"),
        "most_robust_sl": _best_dimension(ranking, "threshold_sl"),
        "stable_region": stable,
        "unstable_region": unstable,
        "stable_region_size": len(stable),
        "unstable_region_size": len(unstable),
        "flat_dimensions": {
            "tp_threshold": _dimension_is_flat(ranking, "threshold_tp", tp_values),
            "sl_threshold": _dimension_is_flat(ranking, "threshold_sl", sl_values),
        },
        "region_definition": {
            "stable": "score >= max(grid median, 40), PF > 1, positive expectancy and >= 50% positive validation windows",
            "unstable": "PF <= 1, non-positive expectancy, < 50% positive windows or score < 40",
        },
    }


def _best_dimension(rows: list[dict[str, Any]], key: str) -> float:
    grouped: dict[float, list[float]] = defaultdict(list)
    for row in rows:
        grouped[float(row[key])].append(float(row["composite_score"]))
    return max(grouped, key=lambda value: (mean(grouped[value]), -value))


def _dimension_is_flat(rows: list[dict[str, Any]], key: str, values: list[float]) -> bool:
    if len(values) < 2:
        return True
    grouped: dict[float, list[float]] = defaultdict(list)
    for row in rows:
        grouped[float(row[key])].append(float(row["composite_score"]))
    averages = [mean(grouped[value]) for value in values]
    return max(averages) - min(averages) < 1e-9


def _pair(row: dict[str, Any]) -> dict[str, float]:
    return {
        "threshold_tp": float(row["threshold_tp"]),
        "threshold_sl": float(row["threshold_sl"]),
        "composite_score": float(row["composite_score"]),
    }


def _normalize(values: list[float], *, inverse: bool = False) -> list[float]:
    low, high = min(values), max(values)
    if math.isclose(low, high):
        return [0.5] * len(values)
    normalized = [(value - low) / (high - low) for value in values]
    return [1.0 - value for value in normalized] if inverse else normalized


def _bounded(value: float) -> float:
    return 10.0 if not math.isfinite(value) else max(min(value, 10.0), 0.0)


def _finite_median(values: list[float]) -> float:
    finite = [value for value in values if math.isfinite(value)]
    if finite:
        return median(finite)
    return math.inf if any(value > 0 for value in values) else 0.0


def _weighted_mean(values: list[float], weights: list[int]) -> float:
    total = sum(weights)
    return sum(value * weight for value, weight in zip(values, weights)) / total if total else 0.0


def _coefficient_of_variation(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    center = abs(mean(values))
    spread = pstdev(values)
    return spread / center if center > 1e-12 else (10.0 if spread else 0.0)
