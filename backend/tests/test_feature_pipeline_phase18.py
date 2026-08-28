from decimal import Decimal

from fastapi import FastAPI

from backend.app.core.celery import celery_app
from backend.app.intelligence.router import router as intelligence_router
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


def test_feature_status_and_daily_pipeline_are_registered():
    app = FastAPI()
    app.include_router(intelligence_router)
    assert "/intelligence/features/status" in app.openapi()["paths"]
    assert "backend.app.intelligence.scheduler.tasks" in celery_app.conf.include
    item = celery_app.conf.beat_schedule["intelligence-compute-all-market-features-daily"]
    assert item["task"] == "intelligence.compute_all_market_features"
    assert item["schedule"]._orig_hour == 23
    assert item["schedule"]._orig_minute == 30
