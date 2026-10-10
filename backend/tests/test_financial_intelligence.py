from backend.app.financial.services.financial_analysis import (
    analyze_financing_decision,
)
from backend.app.financing.schemas import FinancingSimulationRequest


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
