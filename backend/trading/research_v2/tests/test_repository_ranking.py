from __future__ import annotations

import json

import pytest

from backend.trading.research_v2.config import ResearchConfig
from backend.trading.research_v2.ranking import aggregate_threshold_grid, rank_thresholds, threshold_regions
from backend.trading.research_v2.repository import ResearchRepository

from .helpers import report_bundle


def test_repository_reads_all_jsons_and_selects_latest(tmp_path) -> None:
    root = tmp_path / "backtests"
    report_bundle(root, "older", timestamp="2026-01-01T00:00:00+00:00")
    latest = report_bundle(root, "latest", timestamp="2026-02-01T00:00:00+00:00")
    config = ResearchConfig(backtesting_output_root=root, output_root=tmp_path / "research", monte_carlo_simulations=100, bootstrap_iterations=100)

    reports = ResearchRepository(config).load_latest()

    assert reports.run_id == "latest"
    assert reports.run_dir == latest
    assert len(reports.trades) == 40
    assert reports.walk_forward_results["windows"]


def test_repository_fails_for_missing_report_and_invalid_temporal_integrity(tmp_path) -> None:
    root = tmp_path / "backtests"
    run_dir = report_bundle(root)
    (run_dir / "trades.json").unlink()
    config = ResearchConfig(backtesting_output_root=root, monte_carlo_simulations=100, bootstrap_iterations=100)
    with pytest.raises(FileNotFoundError, match="trades.json"):
        ResearchRepository(config).load_latest()

    run_dir = report_bundle(tmp_path / "second", "bad")
    metadata_path = run_dir / "run_metadata.json"
    metadata = json.loads(metadata_path.read_text())
    metadata["temporal_integrity_valid"] = False
    metadata_path.write_text(json.dumps(metadata))
    bad_config = ResearchConfig(backtesting_output_root=tmp_path / "second", monte_carlo_simulations=100, bootstrap_iterations=100)
    with pytest.raises(ValueError, match="temporal integrity"):
        ResearchRepository(bad_config).load_latest()


def test_threshold_ranking_uses_grid_robustness_not_isolated_profit(tmp_path) -> None:
    root = tmp_path / "backtests"
    report_bundle(root)
    config = ResearchConfig(backtesting_output_root=root, monte_carlo_simulations=100, bootstrap_iterations=100)
    reports = ResearchRepository(config).load_latest()

    aggregates = aggregate_threshold_grid(reports.walk_forward_results, minimum_trades=10)
    ranking = rank_thresholds(aggregates)
    regions = threshold_regions(ranking)

    assert len(ranking) == 4
    assert ranking[0]["rank"] == 1
    assert ranking[0]["profit_factor"] > 1
    assert ranking[0]["expectancy"] > 0
    assert regions["stable_region"]
    assert any(row["threshold_tp"] == 0.6 and row["threshold_sl"] == 0.6 for row in regions["unstable_region"])
    stable = {(row["threshold_tp"], row["threshold_sl"]) for row in regions["stable_region"]}
    unstable = {(row["threshold_tp"], row["threshold_sl"]) for row in regions["unstable_region"]}
    assert stable.isdisjoint(unstable)
    assert regions["most_robust_tp"] in {0.5, 0.6}
