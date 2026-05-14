from __future__ import annotations

from typing import Any

from backend.app.core.risk_profile import normalize_risk_profile, RiskProfile


def decide_financial_path(
    *,
    renda: float,
    despesas: float,
    divida_mensal: float,
    reserva: float,
    perfil: str | None,
    allocation: dict[str, Any] | None = None,
    market_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    income = max(float(renda or 0), 0.0)
    expenses = max(float(despesas or 0), 0.0)
    debt = max(float(divida_mensal or 0), 0.0)
    reserve = max(float(reserva or 0), 0.0)
    profile = normalize_risk_profile(perfil)
    reserve_months = reserve / expenses if expenses > 0 else 0.0
    commitment = (expenses + debt) / income if income > 0 else 1.0
    alerts: list[str] = []
    reasons: list[str] = []

    if income <= 0:
        return {
            "decisao": "Não recomendado",
            "classificacao": "arriscado",
            "diagnostico": "Cadastre renda mensal para o FinanceOS calcular decisões com segurança.",
            "acao_principal": "Cadastrar renda, despesas e reserva antes de simular financiamento ou investimento.",
            "motivos": ["Sem renda informada, qualquer decisão financeira fica sem base."],
            "alertas": ["Dados financeiros incompletos."],
        }

    if commitment >= 0.80:
        reasons.append("A renda está muito comprometida por despesas e dívidas.")
        alerts.append("Excesso de risco financeiro: reduza compromissos antes de assumir novas parcelas.")
    if reserve_months < 3:
        reasons.append("A reserva de emergência está abaixo de 3 meses de despesas.")
        alerts.append("Reserva baixa: priorize liquidez antes de renda variável.")
    elif reserve_months < 6:
        reasons.append("A reserva ainda não chegou ao alvo recomendado de 6 meses.")

    macro_stress = float((market_context or {}).get("macro_stress") or 0)
    if macro_stress >= 0.7:
        reasons.append("O contexto macro está pressionado, então a decisão precisa ser mais defensiva.")
        alerts.append("Mercado em estresse: evite aumentar risco sem reserva completa.")

    if profile == RiskProfile.CONSERVADOR and allocation:
        risky = sum((allocation.get("allocation_by_class") or {}).get(k, 0) for k in ("acoes", "bdrs", "cripto"))
        if risky > 0.20:
            reasons.append("A alocação está agressiva demais para um perfil conservador.")
            alerts.append("Perfil conservador com alta exposição a volatilidade.")

    if commitment >= 0.80 or reserve_months < 1:
        decision = "Não recomendado"
        classification = "arriscado"
        action = "Fortalecer caixa e reduzir dívidas antes de investir pesado ou financiar."
    elif commitment >= 0.65 or reserve_months < 6:
        decision = "Recomendado com ajustes"
        classification = "moderado"
        action = "Manter aportes menores, priorizar reserva e evitar aumentar parcela mensal."
    else:
        decision = "Seguro"
        classification = "seguro"
        action = "Executar plano de investimento respeitando a alocação por perfil."

    if not reasons:
        reasons.append("Renda, despesas, reserva e perfil estão coerentes para seguir com planejamento.")
    return {
        "decisao": decision,
        "classificacao": classification,
        "diagnostico": " ".join(reasons),
        "acao_principal": action,
        "motivos": reasons,
        "alertas": alerts,
        "indicadores": {"comprometimento_renda": round(commitment, 4), "meses_reserva": round(reserve_months, 2), "perfil": profile.value},
    }
