from __future__ import annotations

import hashlib
import json
import math
from typing import Any

from .analyzer import (
    bootstrap_analysis,
    monte_carlo_analysis,
    sensitivity_analysis,
    stability_heatmaps,
)
from .config import ResearchConfig
from .models import BacktestReports, ResearchResult
from .ranking import RANKING_WEIGHTS, aggregate_threshold_grid, rank_thresholds, threshold_regions
from .reports import ResearchReportWriter
from .repository import ResearchRepository
from .robustness import calculate_robustness_score


class ResearchOptimizer:
    def __init__(self, config: ResearchConfig, repository: ResearchRepository | None = None) -> None:
        self.config = config
        self.repository = repository or ResearchRepository(config)

    def run(self, reports: BacktestReports | None = None) -> ResearchResult:
        source = reports or self.repository.load_latest()
        aggregates = aggregate_threshold_grid(
            source.walk_forward_results,
            minimum_trades=self.config.minimum_trades,
        )
        ranking = rank_thresholds(aggregates)
        regions = threshold_regions(ranking)
        threshold_analysis = {
            **regions,
            "grid_size": len(ranking),
            "ranking_weights": RANKING_WEIGHTS,
            "threshold_metrics_source": "walk_forward.validation_threshold_results",
            "data_quality": {
                "sortino_by_threshold_available": False,
                "sortino_ranking_treatment": "neutral contribution because Backtesting V2 does not persist it per threshold",
                "test_set_used_for_selection": False,
            },
        }

        sensitivity = sensitivity_analysis(
            source.trades,
            source.summary,
            source.run_metadata,
            seed=self.config.seed,
        )
        monte_carlo = monte_carlo_analysis(
            source.trades,
            initial_capital=float(source.summary["capital_initial"]),
            simulations=self.config.monte_carlo_simulations,
            confidence_level=self.config.confidence_level,
            seed=self.config.seed,
        )
        bootstrap = bootstrap_analysis(
            source.trades,
            initial_capital=float(source.summary["capital_initial"]),
            iterations=self.config.bootstrap_iterations,
            confidence_level=self.config.confidence_level,
            seed=self.config.seed + 1,
        )
        heatmaps = stability_heatmaps(source.trades, source.signal_analysis)
        robustness = calculate_robustness_score(
            summary=source.summary,
            monthly_results=source.monthly_results,
            walk_forward=source.walk_forward_results,
            sensitivity=sensitivity,
            threshold_ranking=ranking,
        )
        recommendation = _recommend(source, ranking, robustness, monte_carlo, heatmaps)
        run_id = _research_run_id(source.run_id, self.config)
        output_dir = self.config.output_root / run_id
        metadata = {
            "engine_version": self.config.engine_version,
            "research_run_id": run_id,
            "source_backtest_run_id": source.run_id,
            "source_backtest_dir": str(source.run_dir),
            "source_timestamp": source.run_metadata.get("timestamp"),
            "symbol": source.run_metadata.get("symbol"),
            "interval": source.run_metadata.get("interval"),
            "target_name": source.run_metadata.get("target_name"),
            "model_name": source.run_metadata.get("model_name"),
            "seed": self.config.seed,
            "monte_carlo_simulations": self.config.monte_carlo_simulations,
            "bootstrap_iterations": self.config.bootstrap_iterations,
            "confidence_level": self.config.confidence_level,
            "paper_only": True,
            "performs_trading": False,
            "performs_inference": False,
            "trains_models": False,
        }
        result = ResearchResult(
            run_id=run_id,
            source_run_id=source.run_id,
            output_dir=output_dir,
            threshold_analysis=threshold_analysis,
            robustness=robustness,
            sensitivity=sensitivity,
            monte_carlo=monte_carlo,
            bootstrap=bootstrap,
            heatmaps=heatmaps,
            ranking=ranking,
            recommendation=recommendation,
            metadata=metadata,
        )
        result.reports = ResearchReportWriter().write(result, overwrite=self.config.overwrite)
        return result


def _recommend(
    source: BacktestReports,
    ranking: list[dict[str, Any]],
    robustness: dict[str, Any],
    monte_carlo: dict[str, Any],
    heatmaps: dict[str, Any],
) -> dict[str, Any]:
    current_thresholds = source.run_metadata.get("thresholds", {})
    best = ranking[0] if ranking else {
        "threshold_tp": current_thresholds.get("take_profit"),
        "threshold_sl": current_thresholds.get("stop_loss"),
        "profit_factor": source.summary.get("profit_factor", 0.0),
        "expectancy": source.summary.get("expectancy", 0.0),
    }
    score = float(robustness["robustness_score"])
    consolidated = source.walk_forward_results.get("consolidated", {})
    negative_windows = int(consolidated.get("negative_test_windows", 0))
    positive_windows = int(consolidated.get("positive_test_windows", 0))
    if score < 40 or float(consolidated.get("aggregate_test_profit_factor", 0.0)) < 1:
        risk_level = "ALTO"
    elif negative_windows >= positive_windows or monte_carlo.get("probability_of_profit", 0.0) < 0.75:
        risk_level = "MODERADO"
    else:
        risk_level = "BAIXO"
    current_fraction = float(source.run_metadata.get("risk", {}).get("fixed_fraction", 0.01))
    recommended_position_size = (
        min(current_fraction, 0.02)
        if score >= 75
        else min(current_fraction, 0.01)
        if score >= 50
        else min(current_fraction, 0.005)
    )
    data_coverage = 4 / 6  # Month, weekday, hour and duration available; confidence/volatility PnL absent.
    confidence_score = score * (0.80 + 0.20 * data_coverage)
    total_windows = int(consolidated.get("total_windows", 0))
    minimum_positive_windows = max(2, math.ceil(total_windows / 2)) if total_windows else 2
    readiness_checks = {
        "robustness_at_least_60": score >= 60,
        "aggregate_oos_positive": consolidated.get("out_of_sample_positive") is True,
        "aggregate_profit_factor_above_1": float(consolidated.get("aggregate_test_profit_factor", 0.0)) > 1,
        "aggregate_expectancy_positive": float(consolidated.get("aggregate_test_expectancy", 0.0)) > 0,
        "at_least_100_oos_trades": int(consolidated.get("aggregate_test_trades", 0)) >= 100,
        "positive_window_majority": positive_windows >= minimum_positive_windows and positive_windows > negative_windows,
        "temporal_integrity_valid": source.run_metadata.get("temporal_integrity_valid") is True,
    }
    paper_ready = bool(
        all(readiness_checks.values())
    )
    return {
        "recommended_tp_threshold": best.get("threshold_tp"),
        "recommended_sl_threshold": best.get("threshold_sl"),
        "recommended_confidence": source.run_metadata.get("risk", {}).get("min_confidence"),
        "recommended_position_size": recommended_position_size,
        "risk_level": risk_level,
        "expected_profit_factor": best.get("profit_factor"),
        "expected_expectancy": best.get("expectancy"),
        "confidence_score": confidence_score,
        "ready_for_paper_trading": paper_ready,
        "paper_trading_readiness_checks": readiness_checks,
        "ready_for_live_trading": False,
        "live_trading_block_reason": "Research V2 never approves live trading automatically.",
        "confidence_recommendation_basis": "Current backtest minimum confidence retained because trade-level confidence PnL is unavailable.",
        "data_coverage": {
            "available_stability_dimensions": ["month", "day_of_week", "hour", "duration"],
            "unavailable_pnl_dimensions": ["confidence", "volatility"],
            "coverage_ratio": data_coverage,
        },
    }


def _research_run_id(source_run_id: str, config: ResearchConfig) -> str:
    payload = {
        "source_run_id": source_run_id,
        "config": config.deterministic_payload(),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]
