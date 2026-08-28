from __future__ import annotations

import math
from statistics import mean, pstdev
from typing import Any

from .models import ValidationCase


def analyze_case(case: ValidationCase) -> dict[str, Any]:
    summary = case.backtest_summary
    windows = case.walk_forward.get("windows", [])
    consolidated = case.walk_forward.get("consolidated", {})
    validation = _aggregate_phase(windows, "validation")
    out_of_sample = {
        "trades": int(consolidated.get("aggregate_test_trades", 0)),
        "net_profit": float(consolidated.get("aggregate_test_net_profit", 0.0)),
        "profit_factor": float(consolidated.get("aggregate_test_profit_factor", 0.0)),
        "win_rate": float(consolidated.get("aggregate_test_win_rate", 0.0)),
        "expectancy": float(consolidated.get("aggregate_test_expectancy", 0.0)),
        "sharpe": float(consolidated.get("aggregate_test_sharpe", 0.0)),
        "sortino": None,
        "max_drawdown": float(consolidated.get("aggregate_test_max_drawdown", 0.0)),
        "positive_windows": int(consolidated.get("positive_test_windows", 0)),
        "negative_windows": int(consolidated.get("negative_test_windows", 0)),
        "neutral_windows": int(consolidated.get("neutral_test_windows", 0)),
        "total_windows": int(consolidated.get("total_windows", len(windows))),
    }
    in_sample = {
        "scope": "full_backtest_reference",
        "trades": int(summary.get("number_of_trades", 0)),
        "net_profit": float(summary.get("net_profit", 0.0)),
        "profit_factor": float(summary.get("profit_factor", 0.0)),
        "win_rate": float(summary.get("win_rate", 0.0)),
        "expectancy": float(summary.get("expectancy", 0.0)),
        "sharpe": float(summary.get("sharpe", summary.get("sharpe_ratio", 0.0))),
        "sortino": float(summary.get("sortino", summary.get("sortino_ratio", 0.0))),
        "max_drawdown": float(summary.get("max_drawdown", 0.0)),
    }
    temporal = temporal_case_analysis(windows)
    return {
        "case_id": case.source_backtest_run_id,
        "research_run_id": case.source_research_run_id,
        "symbol": case.symbol,
        "interval": case.interval,
        "target_name": case.target_name,
        "model_name": case.model_name,
        "period_start": case.period_start,
        "period_end": case.period_end,
        "in_sample": in_sample,
        "validation": validation,
        "out_of_sample": out_of_sample,
        "generalization_gap": {
            "profit_factor": out_of_sample["profit_factor"] - in_sample["profit_factor"],
            "expectancy": out_of_sample["expectancy"] - in_sample["expectancy"],
            "sharpe": out_of_sample["sharpe"] - in_sample["sharpe"],
            "max_drawdown": out_of_sample["max_drawdown"] - in_sample["max_drawdown"],
        },
        "temporal": temporal,
        "research": {
            "robustness_score": float(case.robustness.get("robustness_score", 0.0)),
            "robustness_classification": case.robustness.get("classification"),
            "monte_carlo_probability_of_profit": float(case.monte_carlo.get("probability_of_profit", 0.0)),
            "monte_carlo_var_net_profit": case.monte_carlo.get("var_net_profit"),
            "bootstrap": case.bootstrap,
            "paper_trading_ready": bool(case.recommendation.get("ready_for_paper_trading", False)),
        },
    }


def temporal_case_analysis(windows: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    for window in windows:
        rows.append(
            {
                "window_id": window.get("window_id"),
                "net_profit": float(window.get("net_profit_test", 0.0)),
                "profit_factor": float(window.get("profit_factor_test", 0.0)),
                "expectancy": float(window.get("expectancy_test", 0.0)),
                "sharpe": float(window.get("sharpe_test", 0.0)),
                "max_drawdown": float(window.get("max_drawdown_test", 0.0)),
                "trades": int(window.get("trades_test", 0)),
            }
        )
    net_values = [row["net_profit"] for row in rows]
    positive = sum(value > 0 for value in net_values)
    negative = sum(value < 0 for value in net_values)
    neutral = len(rows) - positive - negative
    consistency = positive / len(rows) if rows else 0.0
    net_mean = mean(net_values) if net_values else 0.0
    net_std = pstdev(net_values) if len(net_values) > 1 else 0.0
    stability = 100.0 * consistency / (1.0 + net_std / max(abs(net_mean), 1e-12)) if rows else 0.0
    return {
        "windows": rows,
        "window_count": len(rows),
        "positive_windows": positive,
        "negative_windows": negative,
        "neutral_windows": neutral,
        "consistency": consistency,
        "stability_score": stability,
        "net_profit_mean": net_mean,
        "net_profit_std": net_std,
        "profit_factor_mean": _finite_mean([row["profit_factor"] for row in rows]),
        "profit_factor_std": _finite_std([row["profit_factor"] for row in rows]),
        "expectancy_mean": mean([row["expectancy"] for row in rows]) if rows else 0.0,
        "expectancy_std": pstdev([row["expectancy"] for row in rows]) if len(rows) > 1 else 0.0,
        "sharpe_mean": mean([row["sharpe"] for row in rows]) if rows else 0.0,
        "sharpe_std": pstdev([row["sharpe"] for row in rows]) if len(rows) > 1 else 0.0,
        "max_drawdown_mean": mean([row["max_drawdown"] for row in rows]) if rows else 0.0,
        "max_drawdown_worst": max((row["max_drawdown"] for row in rows), default=0.0),
    }


def consolidate_temporal(case_results: list[dict[str, Any]]) -> dict[str, Any]:
    windows = [window for case in case_results for window in case["temporal"]["windows"]]
    net_values = [float(row["net_profit"]) for row in windows]
    positive = sum(value > 0 for value in net_values)
    negative = sum(value < 0 for value in net_values)
    neutral = len(windows) - positive - negative
    consistency = positive / len(windows) if windows else 0.0
    stabilities = [float(case["temporal"]["stability_score"]) for case in case_results]
    return {
        "case_count": len(case_results),
        "total_walk_forward_windows": len(windows),
        "positive_windows": positive,
        "negative_windows": negative,
        "neutral_windows": neutral,
        "out_of_sample_consistency": consistency,
        "net_profit_mean": mean(net_values) if net_values else 0.0,
        "net_profit_std": pstdev(net_values) if len(net_values) > 1 else 0.0,
        "profit_factor_mean": _finite_mean([row["profit_factor"] for row in windows]),
        "profit_factor_std": _finite_std([row["profit_factor"] for row in windows]),
        "expectancy_mean": mean([row["expectancy"] for row in windows]) if windows else 0.0,
        "expectancy_std": pstdev([row["expectancy"] for row in windows]) if len(windows) > 1 else 0.0,
        "sharpe_mean": mean([row["sharpe"] for row in windows]) if windows else 0.0,
        "sharpe_std": pstdev([row["sharpe"] for row in windows]) if len(windows) > 1 else 0.0,
        "max_drawdown_worst": max((row["max_drawdown"] for row in windows), default=0.0),
        "stability_score_mean": mean(stabilities) if stabilities else 0.0,
        "stability_score_std": pstdev(stabilities) if len(stabilities) > 1 else 0.0,
    }


def cross_validation_summary(case_results: list[dict[str, Any]]) -> dict[str, Any]:
    phases = {}
    for phase in ("in_sample", "validation", "out_of_sample"):
        rows = [case[phase] for case in case_results]
        phases[phase] = {
            "cases": len(rows),
            "trades": sum(int(row.get("trades", 0)) for row in rows),
            "net_profit": sum(float(row.get("net_profit", 0.0)) for row in rows),
            "profit_factor_mean": _finite_mean([float(row.get("profit_factor", 0.0)) for row in rows]),
            "expectancy_mean": mean([float(row.get("expectancy", 0.0)) for row in rows]) if rows else 0.0,
            "sharpe_mean": mean([float(row.get("sharpe", 0.0)) for row in rows]) if rows else 0.0,
            "max_drawdown_worst": max((float(row.get("max_drawdown", 0.0)) for row in rows), default=0.0),
        }
    return {
        "methodology": "The full backtest is an in-sample reference; validation and OOS metrics come only from chronological walk-forward windows.",
        "phases": phases,
        "generalization": {
            "profit_factor_gap_oos_vs_reference": phases["out_of_sample"]["profit_factor_mean"] - phases["in_sample"]["profit_factor_mean"],
            "expectancy_gap_oos_vs_reference": phases["out_of_sample"]["expectancy_mean"] - phases["in_sample"]["expectancy_mean"],
            "sharpe_gap_oos_vs_reference": phases["out_of_sample"]["sharpe_mean"] - phases["in_sample"]["sharpe_mean"],
        },
    }


def _aggregate_phase(windows: list[dict[str, Any]], phase: str) -> dict[str, Any]:
    suffix = "validation" if phase == "validation" else "test"
    trades = [int(row.get(f"trades_{suffix}", 0)) for row in windows]
    total_trades = sum(trades)
    weights = [max(value, 1) for value in trades]
    return {
        "trades": total_trades,
        "net_profit": sum(float(row.get(f"net_profit_{suffix}", 0.0)) for row in windows),
        "profit_factor": _weighted_finite_mean([float(row.get(f"profit_factor_{suffix}", 0.0)) for row in windows], weights),
        "win_rate": _weighted_mean([float(row.get(f"win_rate_{suffix}", 0.0)) for row in windows], weights),
        "expectancy": _weighted_mean([float(row.get(f"expectancy_{suffix}", 0.0)) for row in windows], weights),
        "sharpe": _weighted_mean([float(row.get(f"sharpe_{suffix}", 0.0)) for row in windows], weights),
        "sortino": None,
        "max_drawdown": max((float(row.get(f"max_drawdown_{suffix}", 0.0)) for row in windows), default=0.0),
    }


def _weighted_mean(values: list[float], weights: list[int]) -> float:
    return sum(value * weight for value, weight in zip(values, weights)) / sum(weights) if weights else 0.0


def _weighted_finite_mean(values: list[float], weights: list[int]) -> float:
    pairs = [(value, weight) for value, weight in zip(values, weights) if math.isfinite(value)]
    if not pairs:
        return math.inf if any(value > 0 for value in values) else 0.0
    return sum(value * weight for value, weight in pairs) / sum(weight for _, weight in pairs)


def _finite_mean(values: list[float]) -> float:
    finite = [value for value in values if math.isfinite(value)]
    if finite:
        return mean(finite)
    return math.inf if any(value > 0 for value in values) else 0.0


def _finite_std(values: list[float]) -> float:
    finite = [value for value in values if math.isfinite(value)]
    return pstdev(finite) if len(finite) > 1 else 0.0
