from __future__ import annotations

import math
from collections import defaultdict
from statistics import mean
from typing import Any

from .config import ValidationConfig


SCORE_WEIGHTS = {
    "profit_factor": 0.15,
    "sharpe": 0.10,
    "sortino": 0.10,
    "expectancy": 0.10,
    "drawdown": 0.10,
    "robustness": 0.15,
    "walk_forward": 0.15,
    "monte_carlo": 0.075,
    "bootstrap": 0.075,
}


def score_case(case: dict[str, Any]) -> dict[str, Any]:
    oos = case["out_of_sample"]
    reference = case["in_sample"]
    research = case["research"]
    components = {
        "profit_factor": _clamp((float(oos["profit_factor"]) - 1.0) / 2.0 * 100.0),
        "sharpe": _clamp(float(oos["sharpe"]) / 0.10 * 100.0),
        "sortino": _clamp(float(reference["sortino"]) / 0.10 * 100.0),
        "expectancy": _clamp(50.0 + 50.0 * math.tanh(float(oos["expectancy"]))),
        "drawdown": _clamp(100.0 * (1.0 - float(oos["max_drawdown"]) / 0.10)),
        "robustness": _clamp(float(research["robustness_score"])),
        "walk_forward": _walk_forward_score(oos),
        "monte_carlo": _monte_carlo_score(research),
        "bootstrap": _bootstrap_score(research.get("bootstrap", {})),
    }
    score = sum(components[key] * SCORE_WEIGHTS[key] for key in SCORE_WEIGHTS)
    return {**case, "score_components": components, "score_weights": SCORE_WEIGHTS, "score": score, "classification": classify(score)}


def rank_dimension(cases: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for case in cases:
        grouped[str(case[key])].append(case)
    ranking = []
    for value, rows in grouped.items():
        scores = [float(row["score"]) for row in rows]
        oos = [row["out_of_sample"] for row in rows]
        ranking.append(
            {
                key: value,
                "rank": 0,
                "cases": len(rows),
                "score": mean(scores),
                "classification": classify(mean(scores)),
                "oos_trades": sum(int(row["trades"]) for row in oos),
                "oos_net_profit": sum(float(row["net_profit"]) for row in oos),
                "oos_profit_factor_mean": _finite_mean([float(row["profit_factor"]) for row in oos]),
                "oos_expectancy_mean": mean([float(row["expectancy"]) for row in oos]),
                "oos_sharpe_mean": mean([float(row["sharpe"]) for row in oos]),
                "oos_max_drawdown_worst": max(float(row["max_drawdown"]) for row in oos),
            }
        )
    ranking.sort(key=lambda row: (row["score"], row["oos_net_profit"], row[key]), reverse=True)
    for position, row in enumerate(ranking, start=1):
        row["rank"] = position
    return ranking


def campaign_score(case_results: list[dict[str, Any]], coverage: dict[str, Any], config: ValidationConfig) -> dict[str, Any]:
    quality = mean([float(case["score"]) for case in case_results]) if case_results else 0.0
    coverage_components = {
        "assets": len(coverage["validated_assets"]) / len(config.assets),
        "targets": min(len(coverage["validated_targets"]) / config.minimum_targets_continuous, 1.0),
        "models": len(coverage["validated_models"]) / len(config.supported_models),
        "periods": min(len(coverage["validated_periods"]) / config.minimum_periods_continuous, 1.0),
        "artifact_report_pairing": coverage["validated_combinations"] / coverage["artifact_combinations"] if coverage["artifact_combinations"] else 0.0,
    }
    coverage_score = 100.0 * mean(coverage_components.values())
    coverage_multiplier = 0.75 + 0.25 * (coverage_score / 100.0)
    overall = quality * coverage_multiplier
    return {
        "overall_score": overall,
        "classification": classify(overall),
        "strategy_quality_score": quality,
        "coverage_score": coverage_score,
        "coverage_components": coverage_components,
        "coverage_multiplier": coverage_multiplier,
        "overall_formula": "strategy_quality * (0.75 + 0.25 * coverage_ratio)",
    }


def readiness(
    case_results: list[dict[str, Any]],
    coverage: dict[str, Any],
    temporal: dict[str, Any],
    campaign: dict[str, Any],
    config: ValidationConfig,
) -> dict[str, Any]:
    paper_checks = {
        "has_validated_case": bool(case_results),
        "overall_score_sufficient": campaign["overall_score"] >= config.minimum_case_score,
        "all_cases_above_minimum": bool(case_results) and all(case["score"] >= config.minimum_case_score for case in case_results),
        "research_approves_paper": bool(case_results) and all(case["research"]["paper_trading_ready"] for case in case_results),
        "oos_aggregate_positive": sum(case["out_of_sample"]["net_profit"] for case in case_results) > 0,
        "minimum_oos_windows": temporal["total_walk_forward_windows"] >= config.minimum_oos_windows,
    }
    paper_ready = all(paper_checks.values())
    continuous_checks = {
        "paper_trading_ready": paper_ready,
        "continuous_score_sufficient": campaign["overall_score"] >= config.minimum_continuous_score,
        "multi_asset": len(coverage["validated_assets"]) >= config.minimum_assets_continuous,
        "multi_target": len(coverage["validated_targets"]) >= config.minimum_targets_continuous,
        "multi_model": len(coverage["validated_models"]) >= config.minimum_models_continuous,
        "multi_period": len(coverage["validated_periods"]) >= config.minimum_periods_continuous,
        "oos_window_majority_positive": temporal["positive_windows"] > temporal["negative_windows"]
        and temporal["out_of_sample_consistency"] >= 0.5,
    }
    continuous_ready = all(continuous_checks.values())
    return {
        "paper_trading_ready": paper_ready,
        "paper_trading_continuous_ready": continuous_ready,
        "live_trading_ready": False,
        "paper_trading_checks": paper_checks,
        "continuous_checks": continuous_checks,
        "live_trading_block_reason": "Validation V2 never approves live trading automatically.",
    }


def classify(score: float) -> str:
    if score < 40:
        return "Reprovado"
    if score < 55:
        return "Fraco"
    if score < 70:
        return "Regular"
    if score < 85:
        return "Bom"
    return "Excelente"


def _walk_forward_score(oos: dict[str, Any]) -> float:
    total = int(oos.get("total_windows", 0))
    consistency = int(oos.get("positive_windows", 0)) / total if total else 0.0
    pf_score = _clamp((float(oos.get("profit_factor", 0.0)) - 1.0) / 1.5 * 100.0)
    expectancy_score = 100.0 if float(oos.get("expectancy", 0.0)) > 0 else 0.0
    return 0.45 * pf_score + 0.35 * consistency * 100.0 + 0.20 * expectancy_score


def _monte_carlo_score(research: dict[str, Any]) -> float:
    probability = _clamp(float(research.get("monte_carlo_probability_of_profit", 0.0)) * 100.0)
    var_positive = 100.0 if float(research.get("monte_carlo_var_net_profit") or 0.0) > 0 else 0.0
    return 0.70 * probability + 0.30 * var_positive


def _bootstrap_score(bootstrap: dict[str, Any]) -> float:
    checks = []
    for key, threshold in (("net_profit", 0.0), ("profit_factor", 1.0), ("expectancy", 0.0), ("sharpe", 0.0)):
        lower = bootstrap.get(key, {}).get("ci_lower")
        checks.append(lower is not None and float(lower) > threshold)
    return 100.0 * sum(checks) / len(checks)


def _finite_mean(values: list[float]) -> float:
    finite = [value for value in values if math.isfinite(value)]
    if finite:
        return mean(finite)
    return math.inf if any(value > 0 for value in values) else 0.0


def _clamp(value: float) -> float:
    if not math.isfinite(value):
        return 100.0 if value > 0 else 0.0
    return min(max(value, 0.0), 100.0)
