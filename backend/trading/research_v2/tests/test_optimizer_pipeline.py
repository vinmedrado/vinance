from __future__ import annotations

import json

import pytest

from backend.trading.research_v2.config import ResearchConfig
from backend.trading.research_v2.optimizer import ResearchOptimizer

from .helpers import report_bundle


def test_optimizer_writes_recommendation_ranking_and_strict_json(tmp_path) -> None:
    source_root = tmp_path / "backtests"
    report_bundle(source_root)
    config = ResearchConfig(
        backtesting_output_root=source_root,
        output_root=tmp_path / "research",
        monte_carlo_simulations=100,
        bootstrap_iterations=100,
        minimum_trades=5,
    )
    result = ResearchOptimizer(config).run()

    assert result.ranking
    assert result.recommendation["recommended_tp_threshold"] is not None
    assert result.recommendation["recommended_sl_threshold"] is not None
    assert result.recommendation["ready_for_live_trading"] is False
    assert result.recommendation["recommended_position_size"] <= 0.02
    assert len(result.reports) == 10
    for path in result.reports.values():
        json.loads(path.read_text(encoding="utf-8"), parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))


def test_optimizer_is_idempotent(tmp_path) -> None:
    source_root = tmp_path / "backtests"
    report_bundle(source_root)
    config = ResearchConfig(
        backtesting_output_root=source_root,
        output_root=tmp_path / "research",
        monte_carlo_simulations=100,
        bootstrap_iterations=100,
    )
    first = ResearchOptimizer(config).run()
    first_payloads = {name: path.read_text() for name, path in first.reports.items()}
    second = ResearchOptimizer(config).run()

    assert first.run_id == second.run_id
    assert first_payloads == {name: path.read_text() for name, path in second.reports.items()}
    assert first.recommendation == second.recommendation


def test_paper_only_is_mandatory_and_live_is_never_approved(tmp_path) -> None:
    with pytest.raises(RuntimeError, match="PAPER_ONLY"):
        ResearchConfig(paper_only=False)

    source_root = tmp_path / "backtests"
    report_bundle(source_root)
    config = ResearchConfig(
        backtesting_output_root=source_root,
        output_root=tmp_path / "research",
        monte_carlo_simulations=100,
        bootstrap_iterations=100,
    )
    result = ResearchOptimizer(config).run()
    assert result.metadata["performs_trading"] is False
    assert result.metadata["performs_inference"] is False
    assert result.metadata["trains_models"] is False
    assert result.recommendation["ready_for_live_trading"] is False
