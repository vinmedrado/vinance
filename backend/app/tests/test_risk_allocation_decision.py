from backend.app.core.risk_profile import RiskProfile, normalize_risk_profile
from backend.app.investment.portfolio_allocator import PortfolioAllocator
from backend.app.decision.decision_engine import decide_financial_path


def test_risk_profile_normalizer_accepts_aliases():
    assert normalize_risk_profile("Conservador") == RiskProfile.CONSERVADOR
    assert normalize_risk_profile("agressivo") == RiskProfile.ARROJADO
    assert normalize_risk_profile("arrojado") == RiskProfile.ARROJADO


def test_allocation_reduces_risk_when_reserve_is_low():
    result = PortfolioAllocator().allocate(capital=1000, profile="agressivo", monthly_income=5000, monthly_expenses=4500, emergency_reserve=1000)
    by_class = result["allocation_by_class"]
    assert by_class["caixa_reserva"] > 0.15
    assert by_class["cripto"] < 0.05


def test_decision_blocks_high_debt():
    allocation = PortfolioAllocator().allocate(capital=1000, profile="moderado", monthly_income=5000, monthly_expenses=3500, emergency_reserve=1000, monthly_debt_payment=1200)
    decision = decide_financial_path(renda=5000, despesas=3500, divida_mensal=1200, reserva=1000, perfil="moderado", allocation=allocation)
    assert decision["decisao"] == "Não recomendado"
