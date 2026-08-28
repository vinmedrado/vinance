from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any


def _decimal(value: Decimal | int | float | str) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


def calculate_financial_score(
    *,
    monthly_salary: Decimal,
    total_expenses_30d: Decimal,
    emergency_reserve: Decimal,
    has_debt_default: bool,
) -> dict[str, Any]:
    salary = _decimal(monthly_salary)
    expenses = _decimal(total_expenses_30d)
    reserve = _decimal(emergency_reserve)
    if salary <= 0:
        raise ValueError("monthly_salary must be greater than zero")
    if expenses < 0 or reserve < 0:
        raise ValueError("expenses and emergency reserve cannot be negative")

    score = 100
    penalties: list[str] = []
    recommendations: list[str] = []
    committed_ratio = (expenses / salary).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

    if has_debt_default:
        score -= 35
        penalties.append("inadimplencia_ativa")
        recommendations.append("Regularizar dívidas vencidas antes de assumir risco financeiro elevado.")

    if committed_ratio > Decimal("0.60"):
        score -= 25
        penalties.append("despesas_acima_60_porcento_renda")
        recommendations.append("Reduzir despesas comprometidas para abaixo de 60% da renda mensal.")
    elif committed_ratio > Decimal("0.40"):
        score -= 12
        penalties.append("despesas_entre_40_e_60_porcento_renda")
        recommendations.append("Monitorar despesas para preservar capacidade de poupança e investimento.")

    emergency_target = expenses * Decimal("3")
    if reserve < emergency_target:
        score -= 18
        penalties.append("reserva_emergencia_menor_3_meses")
        recommendations.append("Priorizar reserva de emergência até pelo menos 3 meses de despesas.")

    investment_capacity_ratio = max(Decimal("0"), (salary - expenses) / salary)
    if investment_capacity_ratio < Decimal("0.10"):
        score -= 10
        penalties.append("capacidade_investimento_muito_baixa")
        recommendations.append("Aumentar margem mensal disponível antes de buscar investimentos de maior risco.")

    score = max(0, min(100, score))
    if score < 40:
        level = "critical"
    elif score < 70:
        level = "attention"
    elif score < 90:
        level = "healthy"
    else:
        level = "excellent"

    if not recommendations:
        recommendations.append("Manter disciplina orçamentária e revisar o diagnóstico mensalmente.")

    return {
        "score": score,
        "level": level,
        "penalties": penalties,
        "recommendations": recommendations,
    }
