from __future__ import annotations

from typing import Any


class FinancialCoachingService:
    """Gera coaching financeiro humano, contextual e acionável."""

    @classmethod
    def generate(cls, health: dict[str, Any], advisor: dict[str, Any], behavior: dict[str, Any] | None = None) -> dict[str, Any]:
        behavior = behavior or {}
        messages: list[str] = []
        alerts: list[dict[str, str]] = []
        next_steps: list[str] = []
        score = int(health.get("health_score", 0))
        phase = health.get("financial_phase", "organização")
        trend = health.get("evolution_trend", "estável")
        capacity = float(advisor.get("investment_capacity", 0) or 0)

        if trend == "melhorando":
            messages.append("Sua evolução financeira está melhorando. Continue protegendo sua reserva antes de aumentar risco.")
        elif trend == "piorando":
            messages.append("Seu mês exige atenção. O ideal agora é reduzir pressão no caixa e evitar novos compromissos.")
        else:
            messages.append(f"Você está na fase de {phase}. O próximo passo é seguir o plano mensal recomendado.")

        if capacity > 0:
            messages.append(f"Você possui margem segura estimada para investir R$ {capacity:,.2f} neste mês.".replace(',', 'X').replace('.', ',').replace('X', '.'))
            next_steps.append("Separe o aporte logo após receber a renda para evitar perda de disciplina.")
        else:
            messages.append("Antes de investir mais, o foco deve ser organizar contas, reserva e compromissos essenciais.")
            next_steps.append("Revise gastos variáveis e contas atrasadas antes de assumir novos investimentos.")

        for warning in advisor.get("warnings", []):
            alerts.append({"severity": "moderado", "message": warning})
        if score < 40:
            alerts.append({"severity": "crítico", "message": "Sua saúde financeira está baixa; priorize caixa e contas essenciais."})
        if "aumento recorrente de gastos" in behavior.get("patterns", []):
            alerts.append({"severity": "moderado", "message": "Seus gastos vêm crescendo; defina um teto semanal para despesas variáveis."})
        if "evolução da reserva" in behavior.get("patterns", []):
            messages.append("Sua reserva está evoluindo, isso aumenta sua segurança para decisões futuras.")

        next_steps.extend(advisor.get("action_plan", [])[:3])
        return {"messages": messages, "alerts": alerts, "next_steps": list(dict.fromkeys(next_steps)), "tone": "consultor financeiro premium"}
