from __future__ import annotations

import re
from typing import Any

DISCLAIMER = "O Vinance fornece análises educacionais baseadas nos seus dados e em simulações. Isso não constitui recomendação financeira individualizada."


class FinancialSafetyGuardrails:
    """Guardrails para advisor financeiro conversacional.

    A camada evita promessa de retorno, ordem de compra/venda e recomendação de risco
    incompatível com a saúde financeira do usuário.
    """

    PROMISE_PATTERNS = [
        r"retorno\s+garantido",
        r"sem\s+risco",
        r"certeza\s+de\s+ganho",
        r"vai\s+render\s+com\s+certeza",
        r"lucro\s+garantido",
    ]
    ORDER_PATTERNS = [r"\bcompre\b", r"\bvenda\b", r"\ball[- ]?in\b", r"aposte tudo"]

    @classmethod
    def inspect_request(cls, question: str, context: dict[str, Any]) -> dict[str, Any]:
        q = (question or "").lower()
        health = context.get("health", {}) or {}
        phase = str(health.get("financial_phase", "")).lower()
        capacity = float(context.get("investment_capacity", 0) or 0)
        asks_for_risky_investment = any(w in q for w in ["cripto", "ação", "acoes", "ações", "carteira agressiva", "alavanc", "trade"])
        financially_critical = phase in {"sobrevivência", "recuperação"} or int(health.get("health_score", 50) or 50) < 40
        return {
            "financially_critical": financially_critical,
            "asks_for_risky_investment": asks_for_risky_investment,
            "must_prioritize_cash": financially_critical and (capacity <= 0 or asks_for_risky_investment),
        }

    @classmethod
    def sanitize_answer(cls, answer: str, context: dict[str, Any]) -> tuple[str, list[str]]:
        text = answer or ""
        warnings: list[str] = []
        for pattern in cls.PROMISE_PATTERNS:
            if re.search(pattern, text, flags=re.I):
                text = re.sub(pattern, "resultado estimado", text, flags=re.I)
                warnings.append("Promessa de retorno removida.")
        for pattern in cls.ORDER_PATTERNS:
            if re.search(pattern, text, flags=re.I):
                text = re.sub(pattern, "avalie com cautela", text, flags=re.I)
                warnings.append("Ordem direta de compra/venda suavizada.")

        phase = str((context.get("health") or {}).get("financial_phase", "")).lower()
        capacity = float(context.get("investment_capacity", 0) or 0)
        lower = text.lower()
        if phase in {"sobrevivência", "recuperação"} and capacity <= 0 and any(w in lower for w in ["invest", "carteira", "cripto", "ação", "acoes", "ações"]):
            text = "Pelo seu contexto atual, o caminho mais prudente é proteger o caixa, organizar contas e fortalecer a reserva antes de aumentar risco em investimentos."
            warnings.append("Investimento inadequado bloqueado pela saúde financeira atual.")
        return text.strip(), warnings

    @classmethod
    def apply(cls, response: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        response = dict(response)
        answer, warnings = cls.sanitize_answer(str(response.get("answer", "")), context)
        response["answer"] = answer
        response["safety_warnings"] = sorted(set(list(response.get("safety_warnings", [])) + warnings))
        response["disclaimer"] = DISCLAIMER
        return response

    @staticmethod
    def disclaimer() -> str:
        return DISCLAIMER
