from __future__ import annotations

from typing import Any

DISCLAIMER = "O Vinance fornece análises e simulações educacionais baseadas em dados históricos e modelos quantitativos. Isso não constitui recomendação financeira."


class FinancialDecisionAdvisor:
    """Ajuda em decisões financeiras sem tom técnico ou promessa de retorno."""

    @classmethod
    def advise(cls, decision_type: str, *, health: dict[str, Any], memory: dict[str, Any], behavior: dict[str, Any], context: dict[str, Any] | None = None) -> dict[str, Any]:
        context = context or {}
        score = int(health.get("health_score", 50))
        risk = health.get("risk_level", "moderado")
        capacity = float(context.get("investment_capacity", health.get("metrics", {}).get("investment_capacity", 0)) or 0)
        debt_ratio = float(context.get("debt_ratio", health.get("metrics", {}).get("debt_ratio", 0)) or 0)
        reserve_months = float(context.get("reserve_months", health.get("metrics", {}).get("reserve_months", 0)) or 0)
        title = cls._title(decision_type)
        recommendation = ""
        reasons: list[str] = []
        next_steps: list[str] = []
        if decision_type == "debt_vs_invest":
            if debt_ratio >= 0.20 or risk == "alto":
                recommendation = "Priorize reduzir dívidas antes de aumentar investimentos."
                reasons.append("Suas dívidas ou compromissos pressionam a renda mensal.")
                next_steps.extend(["Liste as dívidas por custo e atraso.", "Direcione a maior parte da sobra para quitar compromissos críticos."])
            elif reserve_months < 3:
                recommendation = "Divida a sobra entre reserva de emergência e dívidas leves."
                reasons.append("Sua reserva ainda não cobre uma margem confortável.")
                next_steps.append("Monte pelo menos 3 meses de despesas antes de elevar risco.")
            else:
                recommendation = "Você pode equilibrar quitação e investimento conservador/moderado."
                reasons.append("Sua reserva e margem permitem avançar com mais equilíbrio.")
                next_steps.append("Mantenha aportes simples e evite concentrar tudo em ativos voláteis.")
        elif decision_type == "increase_contribution":
            if capacity <= 0 or score < 55:
                recommendation = "Ainda não é o melhor momento para aumentar aporte."
                reasons.append("A margem segura está baixa para assumir um compromisso maior.")
                next_steps.append("Recupere margem mensal antes de aumentar aportes automáticos.")
            else:
                recommendation = "Aumentar o aporte de forma gradual parece coerente com sua situação."
                reasons.append("Existe capacidade financeira positiva e o plano não depende de uma decisão agressiva.")
                next_steps.append("Teste um aumento pequeno por 30 dias e acompanhe o impacto no caixa.")
        elif decision_type == "change_budget_model":
            recommendation = "Mude o modelo apenas se a melhora se repetir por mais de um mês."
            reasons.append("Modelos financeiros funcionam melhor quando acompanham tendência, não apenas um mês isolado.")
            next_steps.append("Compare o mês atual com os dois meses anteriores antes de migrar.")
        elif decision_type == "increase_reserve":
            recommendation = "Fortalecer a reserva deve ser prioridade enquanto ela estiver abaixo de 3 a 6 meses."
            reasons.append("Reserva reduz a chance de vender investimentos ou contrair dívida em imprevistos.")
            next_steps.append("Defina uma meta de reserva mensal automática.")
        else:
            recommendation = "A decisão mais segura agora é proteger sua margem mensal e avançar de forma gradual."
            reasons.append("O Vinance prioriza estabilidade financeira antes de aumentar risco.")
            next_steps.append("Revise renda, despesas e metas para uma orientação mais precisa.")
        return {
            "decision_type": decision_type,
            "title": title,
            "recommendation": recommendation,
            "reasons": reasons,
            "next_steps": next_steps,
            "confidence": cls._confidence(score, memory, behavior),
            "disclaimer": DISCLAIMER,
        }

    @staticmethod
    def _title(decision_type: str) -> str:
        return {
            "debt_vs_invest": "Quitar dívida ou investir?",
            "increase_contribution": "Aumentar aporte mensal",
            "reduce_expenses": "Reduzir gastos",
            "change_budget_model": "Mudar modelo financeiro",
            "increase_reserve": "Aumentar reserva",
            "accelerate_goal": "Acelerar meta",
        }.get(decision_type, "Decisão financeira")

    @staticmethod
    def _confidence(score: int, memory: dict[str, Any], behavior: dict[str, Any]) -> float:
        memory_bonus = 0.08 if memory.get("memory_strength") == "boa" else 0.0
        behavior_bonus = 0.05 if int(behavior.get("behavioral_score", 50)) >= 60 else 0.0
        return round(max(0.55, min(0.92, 0.60 + score / 500 + memory_bonus + behavior_bonus)), 2)
