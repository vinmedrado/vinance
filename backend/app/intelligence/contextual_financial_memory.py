from __future__ import annotations

from typing import Any


class ContextualFinancialMemory:
    """Resume memória financeira em um formato útil para IA consultiva.

    A entrada pode vir do FinancialMemoryService, snapshots mensais ou contexto consolidado.
    O resultado não é uma resposta pronta; é um bloco de contexto que influencia tom,
    prioridades, profundidade e próximos passos.
    """

    @staticmethod
    def summarize(context: dict[str, Any]) -> dict[str, Any]:
        memory = context.get("memory", {}) or {}
        behavior = context.get("behavior", {}) or {}
        health = context.get("health", {}) or {}
        situation = context.get("current_financial_situation", {}) or {}
        budget = context.get("budget_advisor", {}) or {}

        critical_categories = memory.get("critical_categories", []) or []
        patterns = list(memory.get("patterns", []) or [])
        if situation.get("expense_ratio", 0) >= 0.85:
            patterns.append("comprometimento de renda elevado")
        if situation.get("debt_ratio", 0) >= 0.20:
            patterns.append("dívidas pressionando orçamento")
        if behavior.get("discipline_score", 60) >= 70:
            patterns.append("disciplina financeira em evolução")
        if memory.get("trend") == "melhorando":
            patterns.append("trajetória recente de melhora")

        priority = "organização financeira"
        phase = str(health.get("financial_phase", "")).lower()
        if phase in {"sobrevivência", "recuperação"}:
            priority = "caixa, dívidas e reserva"
        elif phase in {"estabilização", "crescimento"}:
            priority = "consistência de aporte e reserva"
        elif phase in {"construção patrimonial", "expansão financeira"}:
            priority = "diversificação e metas de longo prazo"

        return {
            "memory_strength": memory.get("memory_strength", "inicial"),
            "trend": memory.get("trend", health.get("evolution_trend", "estável")),
            "recurring_patterns": sorted(set(patterns))[:8],
            "critical_categories": critical_categories[:5],
            "recent_changes": memory.get("insights", [])[:5],
            "model_history_hint": budget.get("recommended_model"),
            "priority_now": priority,
            "behavioral_context": {
                "behavioral_score": behavior.get("behavioral_score"),
                "discipline_score": behavior.get("discipline_score"),
                "stability_score": behavior.get("stability_score"),
                "risk_behavior_score": behavior.get("risk_behavior_score"),
                "signals": behavior.get("signals", [])[:5],
            },
        }
