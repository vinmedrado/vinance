
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.final_ranking_service import (
    VALID_MARKETS,
    classify_final,
    compute_data_completeness_score,
    compute_final_score,
    get_ranked_assets_by_market,
    normalize_weights,
)


def assert_score_range(value, name):
    if value is None:
        return
    assert 0 <= float(value) <= 100, f"{name} fora de 0-100: {value}"


def test_weight_normalization():
    weights = normalize_weights({"ml": 4, "backtest": 3, "risk": 2, "quality": 1})
    assert abs(sum(weights.values()) - 1.0) < 0.001, weights


def test_completeness():
    assert compute_data_completeness_score(1, 1, 1, 1) == 100
    assert compute_data_completeness_score(1, 1, 1, None) == 75
    assert compute_data_completeness_score(1, 1, None, None) == 50
    assert compute_data_completeness_score(1, None, None, None) == 25


def test_classification_caps():
    assert classify_final(90, 50, True) == "Neutra"
    assert classify_final(90, 100, False) == "Evitar"
    assert classify_final(80, 100, True) == "Forte"


def test_final_score_range():
    score = compute_final_score({"ml_score": 100, "backtest_score": 80, "risk_score": 60, "data_quality_score": 50})
    assert_score_range(score, "score_final")


def test_market_rankings():
    for market in VALID_MARKETS:
        rows = get_ranked_assets_by_market(market, limit=20, tenant_id=None, include_ineligible=True)
        scores = [r["score_final"] for r in rows]
        assert scores == sorted(scores, reverse=True), f"{market} não está ordenado"
        for row in rows:
            for key in ["score_final", "ml_score", "backtest_score", "risk_score", "data_quality_score", "data_completeness_score"]:
                assert_score_range(row.get(key), f"{market}.{row.get('ticker')}.{key}")
            if row.get("data_completeness_score", 0) < 75:
                assert row.get("classification") != "Forte", f"{row.get('ticker')} incompleto não pode ser Forte"


def test_include_ineligible_flag():
    for market in VALID_MARKETS:
        eligible = get_ranked_assets_by_market(market, limit=100, tenant_id=None, include_ineligible=False)
        all_rows = get_ranked_assets_by_market(market, limit=100, tenant_id=None, include_ineligible=True)
        assert len(all_rows) >= len(eligible)
        for row in eligible:
            assert row.get("eligible") is True


def main() -> int:
    tests = [
        test_weight_normalization,
        test_completeness,
        test_classification_caps,
        test_final_score_range,
        test_market_rankings,
        test_include_ineligible_flag,
    ]
    for test in tests:
        test()
        print("PASS", test.__name__)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
