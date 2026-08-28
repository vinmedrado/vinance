from __future__ import annotations

from backend.trading.research_v2.analyzer import (
    bootstrap_analysis,
    monte_carlo_analysis,
    sensitivity_analysis,
    stability_heatmaps,
)
from backend.trading.research_v2.config import ResearchConfig
from backend.trading.research_v2.repository import ResearchRepository
from backend.trading.research_v2.robustness import calculate_robustness_score, classify_robustness

from .helpers import report_bundle


def _reports(tmp_path):
    root = tmp_path / "backtests"
    report_bundle(root)
    config = ResearchConfig(backtesting_output_root=root, monte_carlo_simulations=100, bootstrap_iterations=100)
    return ResearchRepository(config).load_latest()


def test_monte_carlo_is_reproducible_and_reports_risk_distribution(tmp_path) -> None:
    reports = _reports(tmp_path)
    kwargs = dict(initial_capital=10_000, simulations=200, confidence_level=0.95, seed=7)
    first = monte_carlo_analysis(reports.trades, **kwargs)
    second = monte_carlo_analysis(reports.trades, **kwargs)

    assert first == second
    assert first["capital_final"]["ci_lower"] < first["capital_final"]["ci_upper"]
    assert first["cvar_net_profit"] <= first["var_net_profit"]
    assert 0 <= first["probability_of_profit"] <= 1


def test_bootstrap_has_95_percent_intervals_and_is_reproducible(tmp_path) -> None:
    reports = _reports(tmp_path)
    kwargs = dict(initial_capital=10_000, iterations=200, confidence_level=0.95, seed=8)
    first = bootstrap_analysis(reports.trades, **kwargs)
    second = bootstrap_analysis(reports.trades, **kwargs)

    assert first == second
    for key in ("net_profit", "profit_factor", "expectancy", "sharpe"):
        assert first[key]["ci_lower"] <= first[key]["median"] <= first[key]["ci_upper"]


def test_sensitivity_cost_slippage_and_win_rate_stress_results(tmp_path) -> None:
    reports = _reports(tmp_path)
    result = sensitivity_analysis(reports.trades, reports.summary, reports.run_metadata, seed=42)

    assert len(result["cost_increase"]) == 3
    assert len(result["win_rate_reduction"]) == 3
    assert len(result["slippage_increase"]) == 3
    assert result["cost_increase"][2]["net_profit"] < result["cost_increase"][0]["net_profit"]
    assert result["win_rate_reduction"][2]["win_rate"] < result["base"]["win_rate"]
    assert result["slippage_increase"][2]["net_profit"] < result["slippage_increase"][0]["net_profit"]


def test_heatmaps_cover_available_dimensions_and_disclose_missing_data(tmp_path) -> None:
    reports = _reports(tmp_path)
    heatmaps = stability_heatmaps(reports.trades, reports.signal_analysis)

    assert heatmaps["month"]
    assert heatmaps["day_of_week"]
    assert heatmaps["hour"]
    assert heatmaps["duration"]
    assert heatmaps["confidence"]["available_for_pnl"] is False
    assert heatmaps["volatility"]["available_for_pnl"] is False


def test_robustness_score_is_bounded_and_classified() -> None:
    result = calculate_robustness_score(
        summary={"max_drawdown": 0.02},
        monthly_results=[{"net_pnl": 10}, {"net_pnl": -2}, {"net_pnl": 5}],
        walk_forward={"consolidated": {"total_windows": 3, "positive_test_windows": 2, "negative_test_windows": 1, "neutral_test_windows": 0, "aggregate_test_trades": 150, "aggregate_test_profit_factor": 1.5, "aggregate_test_expectancy": 0.2}},
        sensitivity={"cost_increase": [{"net_profit": 1}], "win_rate_reduction": [{"net_profit": -1}], "slippage_increase": [{"net_profit": 1}]},
        threshold_ranking=[{"profit_factor": 1.5, "expectancy": 0.2, "positive_windows_ratio": 0.7}],
    )
    assert 0 <= result["robustness_score"] <= 100
    assert result["classification"] == classify_robustness(result["robustness_score"])
