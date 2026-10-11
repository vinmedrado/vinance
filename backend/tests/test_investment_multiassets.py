from backend.app.investment.engines.fii_engine import FIIEngine


def test_fii_engine_uses_dividends_and_volatility():
    prices = [100, 101, 99, 102, 103, 104]
    dividends = [0.7] * 12
    result = FIIEngine().analyze("HGLG11.SA", prices, dividends)
    assert result["asset_class"] == "fii"
    assert "dividend_yield_estimated" in result["metrics"]
    assert result["portfolio_role"]
