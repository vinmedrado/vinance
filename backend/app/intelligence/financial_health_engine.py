from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


@dataclass(frozen=True)
class FinancialHealthInput:
    monthly_income: float = 0.0
    total_expenses: float = 0.0
    debt_payments: float = 0.0
    overdue_bills: float = 0.0
    emergency_reserve: float = 0.0
    net_worth: float = 0.0
    previous_health_score: int | None = None
    previous_net_worth: float | None = None
    previous_debt_payments: float | None = None
    investment_capacity: float = 0.0


class FinancialHealthEngine:
    """Calcula saúde financeira de forma contínua e traduz para fases humanas."""

    @staticmethod
    def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
        return max(low, min(high, value))

    @classmethod
    def calculate(cls, payload: FinancialHealthInput | dict[str, Any]) -> dict[str, Any]:
        if isinstance(payload, dict):
            allowed = FinancialHealthInput.__dataclass_fields__.keys()
            payload = FinancialHealthInput(**{k: v for k, v in payload.items() if k in allowed})
        income = max(float(payload.monthly_income or 0), 0)
        expenses = max(float(payload.total_expenses or 0), 0)
        debts = max(float(payload.debt_payments or 0), 0)
        overdue = max(float(payload.overdue_bills or 0), 0)
        reserve = max(float(payload.emergency_reserve or 0), 0)
        invest_capacity = max(float(payload.investment_capacity or 0), 0)

        expense_ratio = (expenses / income) if income else 1.0
        debt_ratio = (debts / income) if income else 0.0
        reserve_months = (reserve / max(expenses, 1)) if expenses else (6.0 if reserve > 0 else 0.0)
        savings_rate = max((income - expenses) / income, 0) if income else 0.0

        score = 100.0
        score -= cls._clamp((expense_ratio - 0.45) * 100, 0, 45)
        score -= cls._clamp(debt_ratio * 90, 0, 25)
        score -= 25 if overdue > 0 else 0
        score += cls._clamp(reserve_months * 5, 0, 18)
        score += cls._clamp(savings_rate * 45, 0, 18)
        score += cls._clamp(invest_capacity / max(income, 1) * 30, 0, 8)
        health_score = int(round(cls._clamp(score)))

        if health_score < 30:
            phase, risk = "sobrevivência", "crítico"
        elif health_score < 45:
            phase, risk = "recuperação", "elevado"
        elif health_score < 60:
            phase, risk = "estabilização", "moderado"
        elif health_score < 75:
            phase, risk = "crescimento", "moderado"
        elif health_score < 88:
            phase, risk = "construção patrimonial", "baixo"
        else:
            phase, risk = "expansão financeira", "baixo"

        trend = "estável"
        if payload.previous_health_score is not None:
            delta = health_score - int(payload.previous_health_score)
            if delta >= 5:
                trend = "melhorando"
            elif delta <= -5:
                trend = "piorando"
        elif payload.previous_net_worth is not None and payload.net_worth:
            diff = float(payload.net_worth) - float(payload.previous_net_worth or 0)
            trend = "melhorando" if diff > 0 else "piorando" if diff < 0 else "estável"

        return {
            "health_score": health_score,
            "risk_level": risk,
            "financial_phase": phase,
            "evolution_trend": trend,
            "metrics": {
                "expense_ratio_pct": round(expense_ratio * 100, 2),
                "debt_ratio_pct": round(debt_ratio * 100, 2),
                "reserve_months": round(reserve_months, 2),
                "savings_rate_pct": round(savings_rate * 100, 2),
            },
            "plain_language_summary": cls._summary(phase, risk, trend, health_score),
            "input_summary": asdict(payload),
        }

    @staticmethod
    def _summary(phase: str, risk: str, trend: str, score: int) -> str:
        return f"Sua saúde financeira está em {score}/100, fase de {phase}, com risco {risk} e tendência {trend}."
