from __future__ import annotations

from typing import Any


class HumanizationEngine:
    """Normaliza mensagens para tom premium, simples, empático e não agressivo."""

    @staticmethod
    def refine(message: str, *, phase: str | None = None, tone: str = "consultive", detail_level: str = "short") -> str:
        text = (message or "").strip()
        replacements = {
            "você falhou": "o plano precisa de ajuste",
            "erro": "ponto de atenção",
            "risco alto": "momento de maior cuidado",
            "agressivo": "mais avançado",
            "deve comprar": "pode avaliar com cautela",
            "deve vender": "pode revisar com cautela",
            "garantido": "estimado",
        }
        lower = text.lower()
        for bad, good in replacements.items():
            lower = lower.replace(bad, good)
        if not lower:
            lower = "O Vinance vai acompanhar seus dados e sugerir o próximo passo com segurança."
        if detail_level == "short" and len(lower) > 420:
            lower = lower[:417].rsplit(" ", 1)[0] + "..."
        prefix = ""
        if tone == "encouraging":
            prefix = "Boa evolução: "
        elif tone == "direct":
            prefix = "Próximo passo: "
        result = lower[0].upper() + lower[1:]
        if phase and phase not in result.lower():
            result = f"Na sua fase de {phase}, {result[0].lower() + result[1:] if len(result) > 1 else result}"
        return prefix + result

    @classmethod
    def refine_list(cls, messages: list[str], *, phase: str | None = None, tone: str = "consultive") -> list[str]:
        return [cls.refine(m, phase=phase, tone=tone) for m in messages if m]

    @staticmethod
    def next_best_action(options: dict[str, Any]) -> str:
        health_score = int(options.get("health_score", 50))
        capacity = float(options.get("investment_capacity", 0) or 0)
        reserve_months = float(options.get("reserve_months", 0) or 0)
        if health_score < 45:
            return "Organize o mês atual e reduza pressão no caixa antes de pensar em novos investimentos."
        if reserve_months < 3:
            return "Direcione a sobra principal para construir uma reserva mínima."
        if capacity > 0:
            return "Separe o aporte seguro no início do mês e acompanhe sua meta pelo Vinance."
        return "Atualize renda e despesas para o Vinance indicar o próximo passo com mais precisão."
