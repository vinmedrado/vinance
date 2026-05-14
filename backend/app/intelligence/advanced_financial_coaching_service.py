from __future__ import annotations

from typing import Any


class AdvancedFinancialCoachingService:
    """Coaching premium baseado em memória, saúde, comportamento e metas."""

    @classmethod
    def generate(cls, *, health: dict[str, Any], memory: dict[str, Any], behavior: dict[str, Any], forecast: dict[str, Any] | None = None) -> dict[str, Any]:
        phase = health.get("financial_phase", "organização")
        trend = memory.get("trend", health.get("evolution_trend", "estável"))
        behavioral_score = int(behavior.get("behavioral_score", 50))
        messages: list[str] = []
        tips: list[str] = []
        alerts: list[dict[str, str]] = []
        if trend == "melhorando":
            messages.append("Sua evolução financeira está positiva. O melhor próximo passo é manter consistência antes de aumentar compromissos.")
        elif trend == "piorando":
            messages.append("Seu histórico recente mostra perda de margem. O foco agora é recuperar controle com ajustes simples no mês atual.")
        else:
            messages.append(f"Você está na fase de {phase}. O Vinance vai acompanhar sua evolução e ajustar o plano conforme seus dados melhorarem.")
        if behavioral_score >= 75:
            messages.append("Seu comportamento financeiro mostra disciplina; isso permite planejar metas com mais segurança.")
            tips.append("Automatize o aporte no início do mês para proteger sua consistência.")
        elif behavioral_score >= 55:
            messages.append("Você está em uma fase de construção de hábito. O ideal é escolher poucos ajustes e repetir por 30 dias.")
            tips.append("Defina um teto semanal para gastos variáveis e acompanhe pelo Vinance.")
        else:
            messages.append("Antes de buscar investimentos mais avançados, fortaleça caixa, reserva e previsibilidade mensal.")
            tips.append("Priorize contas essenciais e reduza gastos flexíveis até recuperar margem.")
        for pattern in memory.get("patterns", []):
            if "pressão" in pattern or "instabilidade" in pattern:
                alerts.append({"severity": "moderado", "message": "Seu histórico indica pressão no orçamento. Evite novas parcelas neste momento."})
            if "gastos acima" in pattern:
                alerts.append({"severity": "leve", "message": "Houve gasto acima do padrão recente. Vale revisar as categorias mais sensíveis."})
        critical_categories = memory.get("critical_categories", [])
        if critical_categories:
            tips.append(f"Acompanhe {critical_categories[0]['category']} de perto, pois ela é a categoria que mais pesa no histórico.")
        if forecast:
            base = next((s for s in forecast.get("scenarios", []) if s.get("name") in {"base", "moderado"}), None)
            if base:
                messages.append("No cenário base, sua evolução depende mais da consistência mensal do que de grandes decisões isoladas.")
        return {"messages": messages, "tips": tips, "alerts": alerts, "tone": "consultivo, positivo e direto"}
