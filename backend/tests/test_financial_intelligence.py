from app.financial.services.investment_advisor import build_investment_advice
from app.financial.services.decision_engine import build_central_decision
from app.financing.schemas import FinancingSimulationRequest
from app.financial.services.financial_analysis import analyze_financing_decision


def test_investment_advice_prioritizes_emergency_reserve_when_missing():
    advice = build_investment_advice(
        income=6000,
        expenses=4200,
        emergency_reserve=2000,
        available_capital=1000,
        risk_profile="moderado",
    )
    assert advice["recomendacao"] == "construir_reserva"
    assert advice["reserva_emergencia_gap"] > 0
    assert advice["alocacao_sugerida"][0]["classe"] == "Reserva/Liquidez"


def test_investment_advice_blocks_risk_when_budget_is_negative():
    advice = build_investment_advice(
        income=5000,
        expenses=5200,
        emergency_reserve=0,
        available_capital=500,
        risk_profile="agressivo",
    )
    assert advice["situacao"] == "endividado"
    assert advice["recomendacao"] == "priorizar_caixa_e_dividas"


def test_central_decision_becomes_defensive_with_investment_blocker():
    advice = build_investment_advice(5000, 5200, 0, 500, risk_profile="agressivo")
    decision = build_central_decision(None, advice)
    assert decision["classificacao_geral"] == "arriscado"
    assert decision["decisao"] == "reorganizar_orcamento"


def test_financing_decision_returns_explainability_and_scenarios():
    financing = FinancingSimulationRequest(
        asset_type="car",
        system="PRICE",
        asset_value=80000,
        down_payment=16000,
        months=60,
        monthly_rate=0.015,
        iof_scenario="pf_auto",
    )
    analysis = analyze_financing_decision(
        financing=financing,
        renda_mensal=6000,
        despesas_mensais=3000,
        saldo_disponivel=3000,
        usar_dados_core=False,
    )
    assert analysis["classificacao"] in {"seguro", "moderado", "arriscado"}
    assert analysis["motivos"]
    assert analysis["como_melhorar"]
    assert len(analysis["cenarios"]) >= 2
