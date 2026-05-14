from app.investment.portfolio_allocator import PortfolioAllocator
from app.investment.engines.fii_engine import FIIEngine
from app.investment.engines.fixed_income_engine import FixedIncomeEngine


def test_allocator_prioritizes_reserve_when_missing():
    result = PortfolioAllocator().allocate(
        capital=1000,
        profile="agressivo",
        monthly_income=5000,
        monthly_expenses=4000,
        emergency_reserve=1000,
        monthly_debt_payment=0,
    )
    alloc = {item["asset_class"]: item["percent"] for item in result["allocation"]}
    assert alloc["caixa_reserva"] > 0.15
    assert any("reserva" in msg.lower() for msg in result["explanation"])


def test_fii_engine_uses_dividends_and_volatility():
    prices = [100, 101, 99, 102, 103, 104]
    dividends = [0.7] * 12
    result = FIIEngine().analyze("HGLG11.SA", prices, dividends)
    assert result["asset_class"] == "fii"
    assert "dividend_yield_estimated" in result["metrics"]
    assert result["portfolio_role"]


def test_fixed_income_engine_considers_liquidity_and_guarantee():
    product = {"name": "CDB Liquidez", "indexer": "CDI", "rate": 100, "liquidity_days": 0, "guarantee_type": "FGC", "minimum_investment": 0}
    result = FixedIncomeEngine().analyze_product(product)
    assert result["risk"] == "baixo"
    assert "liquidez" in " ".join(result["explanation"]).lower()
