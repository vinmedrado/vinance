from __future__ import annotations

from typing import Any

DISCLAIMER = "O Vinance fornece análises e simulações educacionais baseadas em dados históricos e modelos quantitativos. Isso não constitui recomendação financeira."


class FinancialForecastService:
    """Projeção explicável para patrimônio, reserva, independência e risco futuro."""

    RATES = {
        "pessimista": {"growth": 0.002, "income_factor": 0.98, "expense_factor": 1.05},
        "base": {"growth": 0.006, "income_factor": 1.00, "expense_factor": 1.00},
        "otimista": {"growth": 0.009, "income_factor": 1.04, "expense_factor": 0.98},
        "conservador": {"growth": 0.0045, "income_factor": 1.00, "expense_factor": 1.01},
        "moderado": {"growth": 0.0065, "income_factor": 1.02, "expense_factor": 1.00},
        "agressivo": {"growth": 0.0095, "income_factor": 1.03, "expense_factor": 1.00},
        "crise": {"growth": -0.001, "income_factor": 0.93, "expense_factor": 1.08},
        "inflação alta": {"growth": 0.003, "income_factor": 0.99, "expense_factor": 1.10},
        "juros altos": {"growth": 0.0055, "income_factor": 1.00, "expense_factor": 1.04},
    }

    @classmethod
    def project(cls, monthly_income: float, total_expenses: float, current_net_worth: float = 0.0, emergency_reserve: float = 0.0, months: int = 12, inflation_rate_monthly: float = 0.003, debt_payment: float = 0.0, contribution_change: float = 0.0, salary_growth_monthly: float = 0.0, include_advanced: bool = False) -> dict[str, Any]:
        income = max(float(monthly_income or 0), 0)
        expenses = max(float(total_expenses or 0), 0)
        debt = max(float(debt_payment or 0), 0)
        net = max(float(current_net_worth or 0), 0)
        reserve = max(float(emergency_reserve or 0), 0)
        scenarios = []
        scenario_items = cls.RATES.items() if include_advanced else [(k, cls.RATES[k]) for k in ("pessimista", "base", "otimista")]
        for name, cfg in scenario_items:
            patrimonio = net
            reserva = reserve
            future_income = income * cfg["income_factor"]
            future_expenses = expenses * cfg["expense_factor"] + debt
            for _ in range(max(1, months)):
                future_income *= (1 + salary_growth_monthly)
                future_expenses *= (1 + inflation_rate_monthly)
                capacidade = max(future_income - future_expenses + contribution_change, 0)
                aporte = capacidade * (0.55 if name in {"pessimista", "crise", "inflação alta"} else 0.70 if name in {"base", "conservador", "moderado", "juros altos"} else 0.80)
                patrimonio = patrimonio * (1 + cfg["growth"]) + aporte
                reserva = min(reserva + capacidade * 0.20, max(expenses, 1) * 6)
            future_capacity = max(future_income - future_expenses + contribution_change, 0)
            months_to_independence = cls._months_to_independence(patrimonio, expenses)
            future_risk = "baixo" if reserva >= expenses * 6 and future_capacity > 0 else "moderado" if reserva >= expenses * 3 else "elevado"
            scenarios.append({
                "name": name,
                "projected_net_worth": round(patrimonio, 2),
                "projected_reserve": round(reserva, 2),
                "future_monthly_capacity": round(future_capacity, 2),
                "future_financial_risk": future_risk,
                "financial_independence_hint_months": months_to_independence,
                "retirement_projection_hint": "mais confortável" if patrimonio > expenses * 120 else "em construção",
                "goal_probability_hint": "maior" if name in {"otimista", "agressivo"} else "moderada" if name in {"base", "moderado"} else "menor",
            })
        return {
            "months": months,
            "scenarios": scenarios,
            "plain_language_summary": "A projeção mostra como renda, gastos, inflação e constância de aporte podem afetar sua evolução financeira.",
            "disclaimer": DISCLAIMER,
        }

    @staticmethod
    def _months_to_independence(net_worth: float, monthly_expenses: float) -> int | None:
        if monthly_expenses <= 0:
            return None
        target = monthly_expenses * 300
        if net_worth >= target:
            return 0
        return None
