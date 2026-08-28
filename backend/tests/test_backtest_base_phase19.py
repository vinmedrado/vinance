from __future__ import annotations

from datetime import date

from fastapi import FastAPI

from backend.app.intelligence.backtest.engine import FeaturePoint, PricePoint, run_ranking_backtest
from backend.app.intelligence.backtest.metrics import max_drawdown, sharpe_ratio, total_return, volatility, win_rate
from backend.app.intelligence.router import router as intelligence_router


def test_metrics_with_valid_series():
    prices = [100, 110, 121]
    assert round(total_return(prices), 4) == 0.21
    returns = [0.10, 0.10]
    assert win_rate(returns) == 1.0
    assert volatility(returns) == 0.0


def test_metrics_with_empty_series_return_none():
    assert total_return([]) is None
    assert volatility([]) is None
    assert sharpe_ratio([]) is None
    assert max_drawdown([]) is None
    assert win_rate([]) is None


def test_max_drawdown():
    assert round(max_drawdown([100, 120, 90, 95]), 4) == -0.25


def test_sharpe_ratio_returns_none_for_zero_volatility():
    assert sharpe_ratio([0.01, 0.01, 0.01]) is None


def test_engine_selects_top_n_by_score_and_uses_future_prices_only():
    features = [
        FeaturePoint("AAA", date(2024, 1, 1), 90),
        FeaturePoint("BBB", date(2024, 1, 1), 50),
    ]
    prices = [
        PricePoint("AAA", date(2024, 1, 1), 100),
        PricePoint("AAA", date(2024, 1, 2), 110),
        PricePoint("AAA", date(2024, 2, 1), 121),
        PricePoint("BBB", date(2024, 1, 2), 100),
        PricePoint("BBB", date(2024, 2, 1), 80),
    ]
    result = run_ranking_backtest(
        market="acoes",
        features=features,
        prices=prices,
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 1),
        holding_period_days=30,
        top_n=1,
        rebalance_frequency="monthly",
    )
    assert result["sample_size"] == 1
    trade = result["trades"][0]
    assert trade.ticker == "AAA"
    assert trade.entry_date == date(2024, 1, 2)
    assert trade.signal_date < trade.entry_date


def test_engine_ignores_asset_without_price_with_warning():
    features = [FeaturePoint("AAA", date(2024, 1, 1), 90)]
    result = run_ranking_backtest(
        market="acoes",
        features=features,
        prices=[],
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 1),
        holding_period_days=30,
        top_n=1,
        rebalance_frequency="monthly",
    )
    assert result["sample_size"] == 0
    assert any("preço insuficiente" in warning or "Nenhum preço" in warning for warning in result["warnings"])


def test_no_trained_ml_terms_in_methodology():
    result = run_ranking_backtest(
        market="acoes",
        features=[],
        prices=[],
        start_date=date(2024, 1, 1),
        end_date=date(2024, 2, 1),
    )
    methodology = " ".join(result["methodology"]).lower()
    assert "não há ml treinado" in methodology


def test_authenticated_backtest_routes_are_registered():
    app = FastAPI()
    app.include_router(intelligence_router)
    paths = set(app.openapi()["paths"])
    assert "/intelligence/backtest/run" in paths
    assert "/intelligence/backtest/summary" in paths
