from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any

MONEY = Decimal("0.01")
RATIO = Decimal("0.0001")


def _decimal(value: Decimal | int | float | str) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _money(value: Decimal) -> Decimal:
    return value.quantize(MONEY, rounding=ROUND_HALF_UP)


def calculate_budget_strategy(
    *,
    monthly_salary: Decimal,
    total_expenses_30d: Decimal,
    emergency_reserve: Decimal,
    has_debt_default: bool,
    financial_score: int,
) -> dict[str, Any]:
    salary = _decimal(monthly_salary)
    expenses = _decimal(total_expenses_30d)
    reserve = _decimal(emergency_reserve)

    if salary <= 0:
        raise ValueError("monthly_salary must be greater than zero")
    if expenses < 0 or reserve < 0:
        raise ValueError("expenses and emergency reserve cannot be negative")

    committed_ratio = (expenses / salary).quantize(RATIO, rounding=ROUND_HALF_UP)

    if has_debt_default or committed_ratio > Decimal("0.60"):
        method = "80/15/5"
        investment_percentage = Decimal("0.05")
    elif committed_ratio > Decimal("0.40"):
        method = "70/20/10"
        investment_percentage = Decimal("0.10")
    else:
        method = "50/30/20"
        investment_percentage = Decimal("0.20")

    emergency_target = expenses * Decimal("3")
    emergency_reserve_priority = reserve < emergency_target
    if emergency_reserve_priority:
        investment_percentage = max(Decimal("0.05"), (investment_percentage / Decimal("2")).quantize(RATIO))

    high_risk_allowed = financial_score >= 40 and not has_debt_default
    investment_capacity = _money(salary * investment_percentage)

    explanation_parts = [
        f"Método {method} definido pela proporção de despesas de {committed_ratio} da renda mensal.",
    ]
    if has_debt_default:
        explanation_parts.append("Inadimplência ativa força método conservador 80/15/5.")
    if emergency_reserve_priority:
        explanation_parts.append("Reserva de emergência abaixo de 3 meses de despesas; prioridade ajustada para formação de reserva.")
    if not high_risk_allowed:
        explanation_parts.append("Risco alto bloqueado pelo score financeiro ou por inadimplência.")

    return {
        "method": method,
        "committed_ratio": committed_ratio,
        "total_expenses_30d": _money(expenses),
        "investment_percentage": investment_percentage,
        "investment_capacity": investment_capacity,
        "emergency_reserve_priority": emergency_reserve_priority,
        "high_risk_allowed": high_risk_allowed,
        "explanation": " ".join(explanation_parts),
    }
