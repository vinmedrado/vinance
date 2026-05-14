from __future__ import annotations

from typing import Any, Literal

RiskProfile = Literal["conservador", "moderado", "agressivo"]
Situation = Literal["endividado", "equilibrado", "capital_disponivel"]

PROFILE_ALLOCATION = {
    "conservador": {"Reserva/Liquidez": 0.55, "Renda fixa": 0.35, "Fundos imobiliários/ETFs": 0.10, "Renda variável": 0.00},
    "moderado": {"Reserva/Liquidez": 0.35, "Renda fixa": 0.35, "Fundos imobiliários/ETFs": 0.20, "Renda variável": 0.10},
    "agressivo": {"Reserva/Liquidez": 0.20, "Renda fixa": 0.25, "Fundos imobiliários/ETFs": 0.25, "Renda variável": 0.30},
}


def _round(value: float | int | None, digits: int = 2) -> float:
    return round(float(value or 0), digits)


def _money(value: float | int | None) -> str:
    return f"R$ {_round(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def infer_situation(income: float, expenses: float, emergency_reserve: float, monthly_debt_payment: float = 0) -> Situation:
    if income <= 0:
        return "endividado"
    balance = income - expenses - monthly_debt_payment
    commitment = (expenses + monthly_debt_payment) / income
    if balance <= 0 or commitment >= 0.85:
        return "endividado"
    reserve_months = emergency_reserve / max(expenses, 1)
    if reserve_months >= 6 and balance > income * 0.15:
        return "capital_disponivel"
    return "equilibrado"


def build_investment_advice(
    income: float,
    expenses: float,
    emergency_reserve: float = 0,
    available_capital: float = 0,
    monthly_investment_capacity: float | None = None,
    risk_profile: RiskProfile = "conservador",
    monthly_debt_payment: float = 0,
) -> dict[str, Any]:
    income = _round(income)
    expenses = _round(expenses)
    emergency_reserve = _round(emergency_reserve)
    available_capital = _round(available_capital)
    monthly_debt_payment = _round(monthly_debt_payment)
    balance = _round(income - expenses - monthly_debt_payment)
    monthly_capacity = _round(monthly_investment_capacity if monthly_investment_capacity is not None else max(0.0, balance * 0.50))
    reserve_target = _round(expenses * 6)
    reserve_gap = _round(max(0.0, reserve_target - emergency_reserve))
    reserve_months = _round(emergency_reserve / expenses, 2) if expenses > 0 else 0.0
    situation = infer_situation(income, expenses, emergency_reserve, monthly_debt_payment)

    reasons: list[str] = []
    next_steps: list[str] = []

    if situation == "endividado":
        recommendation = "priorizar_caixa_e_dividas"
        title = "Ainda não é o melhor momento para investir com risco."
        reasons.append("A renda está muito comprometida ou o saldo mensal está negativo/baixo.")
        next_steps.append("Primeiro recupere saldo mensal positivo e reduza dívidas caras.")
        next_steps.append("Direcione aportes para reserva de emergência e liquidez imediata.")
        base_allocation = {"Reserva/Liquidez": 1.0, "Renda fixa": 0.0, "Fundos imobiliários/ETFs": 0.0, "Renda variável": 0.0}
    elif reserve_gap > 0:
        recommendation = "construir_reserva"
        title = "Priorize reserva de emergência antes de aumentar risco."
        reasons.append(f"Sua reserva cobre cerca de {reserve_months:.1f} meses de despesas; a meta sugerida é 6 meses.")
        next_steps.append(f"Construa uma reserva de pelo menos {_money(reserve_target)} antes de elevar exposição em renda variável.")
        next_steps.append("Use aportes mensais recorrentes e produtos de alta liquidez para a reserva.")
        base_allocation = {"Reserva/Liquidez": 0.80, "Renda fixa": 0.20, "Fundos imobiliários/ETFs": 0.0, "Renda variável": 0.0}
    else:
        recommendation = "investir_com_alocacao"
        title = "Você já pode investir seguindo uma alocação compatível com seu perfil."
        reasons.append("A reserva de emergência está próxima/acima do alvo de 6 meses de despesas.")
        reasons.append("Há margem para alocar parte do capital sem comprometer obrigações mensais.")
        next_steps.append("Mantenha a reserva intacta e invista apenas o excedente planejado.")
        next_steps.append("Rebalanceie a carteira periodicamente para não concentrar risco.")
        base_allocation = PROFILE_ALLOCATION.get(risk_profile, PROFILE_ALLOCATION["conservador"])

    amount_to_allocate = available_capital if available_capital > 0 else monthly_capacity
    allocation = [
        {"classe": name, "percentual": pct, "valor": _round(amount_to_allocate * pct)}
        for name, pct in base_allocation.items()
    ]

    return {
        "perfil_risco": risk_profile,
        "situacao": situation,
        "recomendacao": recommendation,
        "titulo": title,
        "renda_mensal": income,
        "despesas_mensais": expenses,
        "saldo_mensal": balance,
        "capacidade_investimento_mensal": monthly_capacity,
        "reserva_emergencia_atual": emergency_reserve,
        "reserva_emergencia_meta": reserve_target,
        "reserva_emergencia_gap": reserve_gap,
        "meses_reserva": reserve_months,
        "alocacao_sugerida": allocation,
        "fatores": reasons,
        "proximos_passos": next_steps,
        "mensagem": f"{title} Reserva atual: {_money(emergency_reserve)}; meta: {_money(reserve_target)}.",
        "disclaimer": "Sugestão educacional para organização financeira. Não é recomendação individualizada de investimento.",
    }
