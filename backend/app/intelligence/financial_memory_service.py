from __future__ import annotations

from collections import defaultdict
from statistics import mean, pstdev
from typing import Any

DISCLAIMER = "O Vinance fornece análises e simulações educacionais baseadas em dados históricos e modelos quantitativos. Isso não constitui recomendação financeira."


class FinancialMemoryService:
    """Memória financeira leve, persistível via snapshots e segura por organization_id/user_id no chamador."""

    @classmethod
    def analyze(cls, history: list[dict[str, Any]], *, organization_id: str | None = None, user_id: str | None = None) -> dict[str, Any]:
        ordered = sorted(history or [], key=lambda x: (int(x.get("year", 0) or 0), int(x.get("month", 0) or 0)))
        if not ordered:
            return {
                "organization_id": organization_id,
                "user_id": user_id,
                "memory_strength": "inicial",
                "patterns": ["histórico insuficiente"],
                "critical_months": [],
                "seasonality": {},
                "critical_categories": [],
                "trend": "sem histórico",
                "insights": ["Cadastre renda, despesas e metas por alguns meses para o Vinance aprender seu padrão financeiro."],
                "disclaimer": DISCLAIMER,
            }
        incomes = [float(x.get("income", x.get("monthly_income", 0)) or 0) for x in ordered]
        expenses = [float(x.get("expenses", x.get("total_expenses", 0)) or 0) for x in ordered]
        reserves = [float(x.get("reserve", x.get("emergency_reserve", 0)) or 0) for x in ordered]
        contributions = [float(x.get("contribution", x.get("investment_capacity", 0)) or 0) for x in ordered]
        ratios = [(e / i) if i else 1.0 for e, i in zip(expenses, incomes)]
        avg_ratio = mean(ratios)
        ratio_std = pstdev(ratios) if len(ratios) > 1 else 0.0
        critical = []
        seasonality: dict[str, dict[str, float]] = {}
        by_month: dict[int, list[float]] = defaultdict(list)
        for item, ratio in zip(ordered, ratios):
            month = int(item.get("month", 0) or 0)
            if month:
                by_month[month].append(ratio)
            if ratio >= 0.9 or float(item.get("overdue_bills", 0) or 0) > 0:
                critical.append({"year": item.get("year"), "month": item.get("month"), "reason": "comprometimento elevado ou contas atrasadas"})
        for month, values in by_month.items():
            seasonality[f"{month:02d}"] = {"avg_expense_ratio": round(mean(values), 3)}
        patterns: list[str] = []
        if avg_ratio >= 0.85:
            patterns.append("pressão recorrente no orçamento")
        if ratio_std >= 0.12:
            patterns.append("instabilidade mensal")
        if len(expenses) >= 3 and expenses[-1] > mean(expenses[:-1]) * 1.15:
            patterns.append("gastos acima do padrão recente")
        if len(reserves) >= 2 and reserves[-1] > reserves[0]:
            patterns.append("reserva em evolução")
        if contributions and sum(1 for c in contributions if c > 0) >= max(1, len(contributions) - 1):
            patterns.append("consistência de aportes")
        if not patterns:
            patterns.append("rotina financeira estável")
        trend = "melhorando" if len(ratios) >= 2 and ratios[-1] < ratios[0] - 0.05 else "piorando" if len(ratios) >= 2 and ratios[-1] > ratios[0] + 0.05 else "estável"
        critical_categories = cls._critical_categories(ordered)
        insights = cls._insights(patterns, trend, critical, critical_categories)
        return {
            "organization_id": organization_id,
            "user_id": user_id,
            "memory_strength": "boa" if len(ordered) >= 6 else "em formação",
            "patterns": patterns,
            "critical_months": critical,
            "seasonality": seasonality,
            "critical_categories": critical_categories,
            "trend": trend,
            "average_expense_ratio": round(avg_ratio, 3),
            "stability_index": int(max(0, min(100, 100 - ratio_std * 250))),
            "insights": insights,
            "disclaimer": DISCLAIMER,
        }

    @staticmethod
    def _critical_categories(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
        totals: dict[str, float] = defaultdict(float)
        for item in history:
            categories = item.get("categories") or item.get("by_category") or {}
            if isinstance(categories, dict):
                for name, value in categories.items():
                    totals[str(name)] += float(value or 0)
        return [{"category": k, "total": round(v, 2)} for k, v in sorted(totals.items(), key=lambda x: x[1], reverse=True)[:5]]

    @staticmethod
    def _insights(patterns: list[str], trend: str, critical: list[dict[str, Any]], categories: list[dict[str, Any]]) -> list[str]:
        insights = []
        if trend == "melhorando":
            insights.append("Sua trajetória recente mostra melhora; mantenha o plano antes de aumentar o risco dos investimentos.")
        elif trend == "piorando":
            insights.append("O Vinance identificou perda de margem; revise gastos variáveis antes de assumir novos compromissos.")
        else:
            insights.append("Sua rotina está relativamente estável; o próximo ganho vem de consistência e pequenos ajustes.")
        if critical:
            insights.append("Existem meses críticos no histórico; deixe uma margem extra nesses períodos.")
        if categories:
            insights.append(f"A categoria mais sensível hoje é {categories[0]['category']}; ela merece acompanhamento semanal.")
        if "consistência de aportes" in patterns:
            insights.append("Seus aportes mostram consistência, o que fortalece metas de médio e longo prazo.")
        return insights
