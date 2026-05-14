from __future__ import annotations

from typing import Any

from backend.app.intelligence.financial_safety_guardrails import FinancialSafetyGuardrails


class PremiumAdvisorMode:
    """Estrutura consultiva premium: diagnóstico, decisão, riscos e próximos passos."""

    @staticmethod
    def build(response: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        health = context.get("health", {}) or {}
        situation = context.get("current_financial_situation", {}) or {}
        phase = health.get("financial_phase", "em análise")
        score = health.get("health_score", 0)
        capacity = float(context.get("investment_capacity", 0) or 0)
        expense_ratio = float(situation.get("expense_ratio", 0) or 0)
        base_answer = response.get("answer", "")
        if expense_ratio >= 0.85:
            conservative = "Base Zero por 30 dias, revisão semanal de gastos variáveis e prioridade para contas/dívidas."
            balanced = "70/20/10 temporário, com limite rígido para desejos e foco em reserva mínima."
            aggressive = "Não recomendado agora; primeiro estabilize caixa e reserva."
        elif capacity > 0:
            conservative = "Separar uma parte maior da sobra para reserva/CDI e manter aporte baixo."
            balanced = "Manter aporte mensal dentro da margem segura e acompanhar gastos por categoria."
            aggressive = "Só aumentar risco se a reserva estiver confortável e as metas de curto prazo protegidas."
        else:
            conservative = "Reorganizar orçamento e cortar vazamentos antes de investir."
            balanced = "Negociar contas, revisar categorias críticas e buscar sobra mensal positiva."
            aggressive = "Não recomendado nesta fase."
        premium = {
            "diagnosis": f"Sua fase atual é {phase}, com score {score}/100.",
            "context_reading": "A análise considera renda, despesas, dívidas, reserva, metas, comportamento e histórico recente.",
            "recommended_decision": response.get("recommended_action", "Revisar plano financeiro do mês."),
            "main_answer": base_answer,
            "risks": ["Projeções são estimativas educacionais.", "Aumentar risco sem reserva pode pressionar seu orçamento."],
            "next_steps": [response.get("recommended_action", "Atualizar orçamento"), "Revisar alertas do copiloto", "Acompanhar evolução nos próximos 30 dias"],
            "alternatives": {"conservative": conservative, "balanced": balanced, "aggressive": aggressive},
        }
        response = dict(response)
        response["premium_advisor"] = premium
        return FinancialSafetyGuardrails.apply(response, context)
