from __future__ import annotations

from datetime import datetime
from typing import Any

class ContinuousFinancialCopilot:
    """Gera eventos inteligentes para acompanhamento contínuo."""

    @staticmethod
    def monitor(context: dict[str, Any]) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        health = context.get("health", {})
        summary = context.get("current_financial_situation", {})
        memory = context.get("memory", {})
        behavior = context.get("behavior", {})
        capacity = float(context.get("investment_capacity", 0) or 0)
        expense_ratio = float(summary.get("expense_ratio", 0) or 0)
        debt_ratio = float(summary.get("debt_ratio", 0) or 0)
        now = datetime.utcnow().isoformat()
        def add(t: str, sev: str, msg: str, impact: str, action: str, entity: str = "financial_plan"):
            events.append({"type": t, "severity": sev, "message": msg, "impact": impact, "suggested_action": action, "related_entity": entity, "created_at": now})
        if expense_ratio >= 0.85:
            add("expense_pressure", "critical", "Seu comprometimento de renda está alto para este mês.", "Pode reduzir sua margem de segurança e atrasar metas.", "Revisar gastos variáveis e priorizar contas essenciais.")
        elif expense_ratio >= 0.70:
            add("expense_attention", "moderate", "Suas despesas pedem atenção antes de aumentar investimentos.", "A sobra pode ficar instável.", "Manter o modelo recomendado e limitar desejos/lazer.")
        if debt_ratio >= 0.20:
            add("debt_risk", "moderate", "As dívidas ocupam uma parte relevante da renda.", "Quitar ou renegociar pode liberar capacidade futura.", "Comparar quitar dívida vs investir no Advisor.", "debt")
        if capacity > 0 and int(health.get("health_score", 0)) >= 60:
            add("investment_capacity_increased", "light", f"Você possui margem segura estimada de R$ {capacity:,.2f} para planejar aporte.", "Permite avançar metas sem pressionar o orçamento.", "Separar o aporte no começo do mês.")
        if behavior.get("risk_behavior_score", 0) >= 65:
            add("behavioral_risk", "moderate", "O comportamento recente indica risco de descontrole em algumas categorias.", "Pode comprometer o modelo financeiro recomendado.", "Acompanhar categorias críticas semanalmente.")
        if memory.get("trend") == "melhorando":
            add("financial_improvement", "light", "Sua trajetória recente mostra melhora financeira.", "Aumenta a confiança para metas e aportes graduais.", "Manter consistência por mais um mês antes de elevar risco.")
        goals = context.get("dynamic_goals", {}).get("goals", [])
        for goal in goals[:2]:
            if float(goal.get("success_probability", 50) or 50) < 45:
                add("goal_delay", "moderate", f"A meta {goal.get('goal_type','principal')} pode precisar de ajuste.", "O prazo ou aporte atual pode não ser suficiente.", "Revisar prazo, aporte ou prioridade da meta.", "goal")
        return events[:8]
