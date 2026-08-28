from __future__ import annotations

from typing import Any


def calculate_robustness_score(
    *,
    summary: dict[str, Any],
    monthly_results: list[dict[str, Any]],
    walk_forward: dict[str, Any],
    sensitivity: dict[str, Any],
    threshold_ranking: list[dict[str, Any]],
) -> dict[str, Any]:
    consolidated = walk_forward.get("consolidated", {})
    total_windows = int(consolidated.get("total_windows", 0))
    positive_windows = int(consolidated.get("positive_test_windows", 0))
    neutral_windows = int(consolidated.get("neutral_test_windows", 0))
    positive_months = sum(float(row.get("net_pnl", 0.0)) > 0 for row in monthly_results)
    month_ratio = positive_months / len(monthly_results) if monthly_results else 0.0
    window_ratio = (positive_windows + 0.5 * neutral_windows) / total_windows if total_windows else 0.0
    sample_factor = min(float(consolidated.get("aggregate_test_trades", 0)) / 200.0, 1.0)
    window_factor = min(total_windows / 5.0, 1.0)

    temporal = 100.0 * (0.55 * month_ratio + 0.45 * window_ratio) * (0.75 + 0.25 * window_factor)
    aggregate_pf = float(consolidated.get("aggregate_test_profit_factor", 0.0))
    aggregate_expectancy = float(consolidated.get("aggregate_test_expectancy", 0.0))
    walk_forward_score = 100.0 * (
        0.40 * min(max(aggregate_pf, 0.0) / 2.0, 1.0)
        + 0.30 * (1.0 if aggregate_expectancy > 0 else 0.0)
        + 0.30 * window_ratio
    ) * (0.70 + 0.30 * sample_factor)
    max_drawdown = float(summary.get("max_drawdown", 0.0))
    drawdown_score = 100.0 * (1.0 - min(max_drawdown / 0.10, 1.0))

    stress_rows = (
        sensitivity.get("cost_increase", [])
        + sensitivity.get("win_rate_reduction", [])
        + sensitivity.get("slippage_increase", [])
    )
    positive_stress = sum(float(row.get("net_profit", 0.0)) > 0 for row in stress_rows)
    sensitivity_score = 100.0 * positive_stress / len(stress_rows) if stress_rows else 0.0

    stable_thresholds = sum(
        row.get("profit_factor", 0) > 1
        and row.get("expectancy", 0) > 0
        and row.get("positive_windows_ratio", 0) >= 0.5
        for row in threshold_ranking
    )
    threshold_ratio = stable_thresholds / len(threshold_ranking) if threshold_ranking else 0.0
    consistency = 100.0 * (0.45 * month_ratio + 0.35 * window_ratio + 0.20 * threshold_ratio)

    components = {
        "temporal_stability": temporal,
        "walk_forward": walk_forward_score,
        "drawdown": drawdown_score,
        "sensitivity": sensitivity_score,
        "consistency": consistency,
    }
    weights = {
        "temporal_stability": 0.25,
        "walk_forward": 0.30,
        "drawdown": 0.15,
        "sensitivity": 0.15,
        "consistency": 0.15,
    }
    score = sum(components[key] * weights[key] for key in weights)
    return {
        "robustness_score": score,
        "classification": classify_robustness(score),
        "components": components,
        "weights": weights,
        "sample_adequacy": {
            "test_trades": int(consolidated.get("aggregate_test_trades", 0)),
            "walk_forward_windows": total_windows,
            "sample_factor": sample_factor,
            "window_factor": window_factor,
        },
    }


def classify_robustness(score: float) -> str:
    if score < 20:
        return "Muito Fraco"
    if score < 40:
        return "Fraco"
    if score < 60:
        return "Regular"
    if score < 80:
        return "Bom"
    return "Excelente"
