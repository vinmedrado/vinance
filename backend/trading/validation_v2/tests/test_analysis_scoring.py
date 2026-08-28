from __future__ import annotations

from backend.trading.validation_v2.analyzer import analyze_case, consolidate_temporal, cross_validation_summary
from backend.trading.validation_v2.config import ValidationConfig
from backend.trading.validation_v2.repository import ValidationRepository
from backend.trading.validation_v2.scoring import campaign_score, classify, rank_dimension, score_case

from .helpers import validation_fixture


def _inputs(tmp_path):
    paths = validation_fixture(tmp_path)
    config = ValidationConfig(manifest_path=paths["manifest"], backtesting_output_root=paths["backtests"], research_output_root=paths["research"], output_root=paths["output"])
    return ValidationRepository(config).load(), config


def test_cross_validation_separates_reference_validation_and_oos(tmp_path) -> None:
    inputs, _ = _inputs(tmp_path)
    cases = [analyze_case(case) for case in inputs.cases]
    summary = cross_validation_summary(cases)

    assert set(summary["phases"]) == {"in_sample", "validation", "out_of_sample"}
    assert summary["phases"]["validation"]["trades"] > 0
    assert summary["phases"]["out_of_sample"]["trades"] > 0
    assert "profit_factor_gap_oos_vs_reference" in summary["generalization"]


def test_temporal_robustness_consolidates_all_walk_forward_windows(tmp_path) -> None:
    inputs, _ = _inputs(tmp_path)
    temporal = consolidate_temporal([analyze_case(case) for case in inputs.cases])

    assert temporal["total_walk_forward_windows"] == 9
    assert temporal["positive_windows"] == 4
    assert temporal["negative_windows"] == 2
    assert 0 <= temporal["stability_score_mean"] <= 100
    assert temporal["net_profit_std"] > 0


def test_case_score_and_rankings_order_positive_cases_above_negative(tmp_path) -> None:
    inputs, _ = _inputs(tmp_path)
    cases = [score_case(analyze_case(case)) for case in inputs.cases]
    asset_ranking = rank_dimension(cases, "symbol")
    model_ranking = rank_dimension(cases, "model_name")
    target_ranking = rank_dimension(cases, "target_name")

    positive_scores = [case["score"] for case in cases if case["out_of_sample"]["net_profit"] > 0]
    negative_score = next(case["score"] for case in cases if case["out_of_sample"]["net_profit"] < 0)
    assert min(positive_scores) > negative_score
    assert asset_ranking[0]["symbol"] == "BTCUSDT"
    assert model_ranking and target_ranking


def test_campaign_score_includes_coverage_penalty_and_classification(tmp_path) -> None:
    inputs, config = _inputs(tmp_path)
    cases = [score_case(analyze_case(case)) for case in inputs.cases]
    result = campaign_score(cases, inputs.coverage, config)

    assert 0 <= result["overall_score"] <= 100
    assert result["overall_score"] < result["strategy_quality_score"]
    assert result["classification"] == classify(result["overall_score"])
