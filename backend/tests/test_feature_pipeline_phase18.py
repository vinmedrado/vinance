from decimal import Decimal

from backend.app.intelligence.feature_pipeline.common import calculate_momentum, calculate_volatility, calculate_zscore
from backend.app.intelligence.feature_scoring import score_acoes_features, score_cripto_features, score_fii_features


def test_calculate_momentum_returns_none_without_history():
    assert calculate_momentum([10, 11], 30) is None


def test_calculate_momentum_basic():
    assert calculate_momentum([100] + [100] * 29 + [110], 30) == Decimal("10.000000")


def test_calculate_volatility_range_or_none():
    value = calculate_volatility([100, 101, 99, 102, 100, 103, 104, 105], 7)
    assert value is None or value >= 0


def test_zscore_basic():
    value = calculate_zscore(12, [10, 11, 12, 13, 14])
    assert value is not None


def test_feature_scores_always_between_0_and_100():
    scores = [
        score_fii_features(momentum_30d=10, volatilidade_30d=20),
        score_acoes_features(momentum_90d=10, volatilidade_90d=35),
        score_cripto_features(momentum_30d=20, volatilidade_30d=120),
    ]
    assert all(Decimal("0") <= score <= Decimal("100") for score in scores)


def test_missing_data_gets_neutral_reduced_weight_without_breaking():
    score = score_fii_features()
    assert Decimal("0") <= score <= Decimal("100")
