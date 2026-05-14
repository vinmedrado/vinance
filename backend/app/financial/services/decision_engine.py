from __future__ import annotations

from typing import Any


def _class_rank(name: str) -> int:
    return {"seguro": 0, "moderado": 1, "arriscado": 2}.get(name, 2)


def build_central_decision(financing_analysis: dict[str, Any] | None, investment_advice: dict[str, Any] | None) -> dict[str, Any]:
    """Motor central: transforma análises técnicas em decisão humana."""
    actions: list[str] = []
    blockers: list[str] = []
    decision = "acompanhar"
    classification = "moderado"

    if financing_analysis:
        classification = financing_analysis.get("classificacao", "arriscado")
        if classification == "seguro":
            actions.append("Financiamento possível, desde que mantenha reserva e compare CET.")
            decision = "pode_financiar_com_cautela"
        elif classification == "moderado":
            actions.append("Financiamento possível, mas melhorar entrada/prazo reduz risco.")
            decision = "melhorar_condicoes_antes"
        else:
            blockers.append("O financiamento pressiona demais a renda ou a margem mensal.")
            decision = "esperar"
    if investment_advice:
        rec = investment_advice.get("recomendacao")
        if rec == "priorizar_caixa_e_dividas":
            blockers.append("Investimento com risco deve esperar até o caixa mensal ficar saudável.")
            decision = "reorganizar_orcamento"
            classification = "arriscado"
        elif rec == "construir_reserva":
            actions.append("Priorize reserva de emergência antes de aumentar investimentos de risco.")
            if _class_rank(classification) < _class_rank("moderado"):
                classification = "moderado"
        elif rec == "investir_com_alocacao":
            actions.append("Investimento pode avançar com alocação compatível ao perfil de risco.")

    if blockers:
        headline = "A melhor decisão agora é proteger o caixa antes de assumir mais risco."
    elif decision == "pode_financiar_com_cautela":
        headline = "A decisão é viável, mas deve ser feita com controle de CET, prazo e reserva."
    else:
        headline = "A decisão melhora se você reforçar entrada, reserva e margem mensal."

    return {
        "classificacao_geral": classification,
        "decisao": decision,
        "diagnostico": headline,
        "bloqueios": blockers,
        "proximas_acoes": actions[:5],
    }
