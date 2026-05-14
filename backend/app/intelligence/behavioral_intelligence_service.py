from __future__ import annotations

from statistics import mean
from typing import Any


class BehavioralIntelligenceService:
    """Transforma histórico financeiro em sinais comportamentais simples e não punitivos."""

    @classmethod
    def analyze(cls, history: list[dict[str, Any]], memory: dict[str, Any] | None = None) -> dict[str, Any]:
        memory = memory or {}
        if not history:
            return {
                "behavioral_score": 50,
                "stability_score": 50,
                "discipline_score": 50,
                "risk_behavior_score": 50,
                "signals": ["histórico insuficiente"],
                "plain_language_summary": "O Vinance ainda está aprendendo seu comportamento financeiro.",
            }
        ratios = []
        contributions = []
        overdue_count = 0
        for item in history:
            income = float(item.get("income", item.get("monthly_income", 0)) or 0)
            expenses = float(item.get("expenses", item.get("total_expenses", 0)) or 0)
            ratios.append((expenses / income) if income else 1.0)
            contributions.append(float(item.get("contribution", item.get("investment_capacity", 0)) or 0))
            overdue_count += 1 if float(item.get("overdue_bills", 0) or 0) > 0 else 0
        avg_ratio = mean(ratios)
        positive_contribution_rate = sum(1 for c in contributions if c > 0) / max(len(contributions), 1)
        stability = int(max(0, min(100, 100 - (max(ratios) - min(ratios)) * 180))) if ratios else 50
        discipline = int(max(0, min(100, 95 - max(0, avg_ratio - 0.55) * 130 + positive_contribution_rate * 12 - overdue_count * 8)))
        risk_behavior = int(max(0, min(100, 100 - discipline + overdue_count * 10)))
        behavioral = int(max(0, min(100, discipline * 0.55 + stability * 0.30 + (100 - risk_behavior) * 0.15)))
        signals = []
        if avg_ratio > 0.85:
            signals.append("risco de endividamento")
        if positive_contribution_rate >= 0.7:
            signals.append("consistência de investimentos")
        if "gastos acima do padrão recente" in memory.get("patterns", []):
            signals.append("impulsividade financeira possível")
        if "reserva em evolução" in memory.get("patterns", []):
            signals.append("melhora comportamental")
        if overdue_count:
            signals.append("inadimplência recorrente")
        if not signals:
            signals.append("comportamento estável")
        if behavioral >= 75:
            summary = "Seu comportamento financeiro demonstra boa disciplina e estabilidade."
        elif behavioral >= 55:
            summary = "Seu comportamento financeiro está em construção; pequenos ajustes já podem gerar melhora."
        else:
            summary = "Seu comportamento financeiro pede proteção de caixa e revisão de compromissos."
        return {
            "behavioral_score": behavioral,
            "stability_score": stability,
            "discipline_score": discipline,
            "risk_behavior_score": risk_behavior,
            "signals": signals,
            "plain_language_summary": summary,
        }
