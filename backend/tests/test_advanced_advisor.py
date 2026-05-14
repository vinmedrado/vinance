from app.financial.services.advanced_advisor import build_advanced_advisor, build_future_projection, build_priority_engine


def test_priority_engine_detects_critical_reserve():
    result = build_priority_engine(
        income=5000,
        expenses=4200,
        emergency_reserve=500,
        reserve_months_target=6,
        monthly_payment=0,
        investment_target=0,
        risk_profile="conservador",
    )
    assert result["problema_mais_critico"]["problema"] in {"reserva_critica", "renda_pressionada"}
    assert result["acao_principal_recomendada"]


def test_projection_returns_6_12_24_months():
    projection = build_future_projection(
        income=8000,
        expenses=5000,
        emergency_reserve=10000,
        planned_monthly_investment=1000,
    )
    assert [row["meses"] for row in projection] == [6, 12, 24]
    assert projection[-1]["reserva_estimada"] > projection[0]["reserva_estimada"]


def test_advanced_advisor_integrates_financing_and_investment():
    advisor = build_advanced_advisor(
        profile={"perfil_risco": "moderado", "reserva_meses_alvo": 6},
        income=7000,
        expenses=4000,
        emergency_reserve=6000,
        investment_target=500,
        financing_analysis={"classificacao": "moderado", "parcela_simulada": 1800},
        investment_advice={"recomendacao": "construir_reserva", "mensagem": "Priorize reserva."},
        history=[],
    )
    assert advisor["decisao"] in {"Não recomendado", "Recomendado com ajustes", "Seguro"}
    assert advisor["integracao_total"]["financiamento_impacta_investimento"] is True
    assert advisor["projecao_futura"][0]["meses"] == 6
