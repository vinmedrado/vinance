from __future__ import annotations

from statistics import mean
from typing import Any


class BehavioralFinanceService:
    """Detecta padrões comportamentais sem usar linguagem de culpa."""

    @classmethod
    def analyze(cls, monthly_history: list[dict[str, Any]]) -> dict[str, Any]:
        if not monthly_history:
            return {"patterns": [], "discipline_score": 50, "stability": "sem histórico", "risk_of_slippage": "moderado", "insights": ["Cadastre alguns meses para o Vinance acompanhar sua evolução."]}
        expenses = [float(x.get("expenses", x.get("total_expenses", 0)) or 0) for x in monthly_history]
        incomes = [float(x.get("income", x.get("monthly_income", 0)) or 0) for x in monthly_history]
        reserves = [float(x.get("reserve", x.get("emergency_reserve", 0)) or 0) for x in monthly_history]
        contributions = [float(x.get("contribution", x.get("investment_capacity", 0)) or 0) for x in monthly_history]
        ratios = [(e / i if i else 1.0) for e, i in zip(expenses, incomes)]
        patterns: list[str] = []
        if len(expenses) >= 2 and expenses[-1] > expenses[0] * 1.15:
            patterns.append("aumento recorrente de gastos")
        if len(reserves) >= 2 and reserves[-1] > reserves[0]:
            patterns.append("evolução da reserva")
        if contributions and sum(1 for c in contributions if c > 0) >= max(1, len(contributions) - 1):
            patterns.append("consistência de aportes")
        if ratios and mean(ratios) > 0.85:
            patterns.append("risco de descontrole")
        if not patterns:
            patterns.append("rotina financeira estável")
        discipline = 100 - min(60, max(0, (mean(ratios) - 0.50) * 100)) if ratios else 50
        discipline += 10 if "consistência de aportes" in patterns else 0
        discipline += 8 if "evolução da reserva" in patterns else 0
        discipline_score = int(max(0, min(100, round(discipline))))
        stability = "alta" if discipline_score >= 75 else "média" if discipline_score >= 55 else "baixa"
        risk = "baixo" if discipline_score >= 75 else "moderado" if discipline_score >= 50 else "elevado"
        insights = cls._insights(patterns, stability)
        return {"patterns": patterns, "discipline_score": discipline_score, "stability": stability, "risk_of_slippage": risk, "insights": insights}

    @staticmethod
    def _insights(patterns: list[str], stability: str) -> list[str]:
        out = []
        if "aumento recorrente de gastos" in patterns:
            out.append("Seus gastos subiram de forma relevante; vale revisar as categorias variáveis antes de aumentar investimentos.")
        if "evolução da reserva" in patterns:
            out.append("Sua reserva está evoluindo, o que melhora sua estabilidade financeira.")
        if "consistência de aportes" in patterns:
            out.append("Você está mantendo consistência nos aportes, um sinal positivo para metas de médio prazo.")
        if "risco de descontrole" in patterns:
            out.append("Seu comprometimento de renda pede atenção para evitar pressão no caixa.")
        if not out:
            out.append(f"Sua rotina financeira mostra estabilidade {stability}; continue acompanhando mês a mês.")
        return out
