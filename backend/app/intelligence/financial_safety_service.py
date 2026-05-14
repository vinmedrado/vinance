from __future__ import annotations

from typing import Any
from backend.app.intelligence.financial_safety_guardrails import FinancialSafetyGuardrails, DISCLAIMER


class FinancialSafetyService:
    """Camada de segurança para evitar promessa financeira ou risco incompatível."""

    BLOCKED_PHRASES = ("compre ", "venda ", "retorno garantido", "sem risco", "garantido")

    @classmethod
    def evaluate(cls, response: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        text = " ".join(str(response.get(k, "")) for k in ("answer", "main_message", "recommendation")).lower()
        health = context.get("health", {}) or {}
        risk_level = str(health.get("risk_level", "")).lower()
        phase = str(health.get("financial_phase", "")).lower()
        capacity_raw = context.get("investment_capacity", None)
        if capacity_raw is None:
            capacity_raw = context.get("budget_advisor", {}).get("investment_capacity", 0)
        capacity = float(capacity_raw or 0)
        warnings: list[str] = []
        blocked = False
        for phrase in cls.BLOCKED_PHRASES:
            if phrase in text:
                warnings.append("A resposta foi suavizada para não parecer ordem de compra/venda ou promessa de resultado.")
                blocked = True
        if risk_level in {"alto", "crítico", "critico", "elevado"} or phase in {"sobrevivência", "recuperação"}:
            if ("invest" in text or "aporte" in text or "carteira" in text) and capacity <= 0:
                blocked = True
                warnings.append("Investimento agressivo bloqueado porque a saúde financeira exige foco em caixa, dívidas ou reserva.")
        response = dict(response)
        if blocked and capacity <= 0:
            response["answer"] = "Pelo seu contexto atual, o próximo passo mais seguro é organizar caixa, contas e reserva antes de aumentar investimentos."
            response["recommended_action"] = "Revisar orçamento e priorizar reserva/dívidas."
        response["safety_warnings"] = warnings
        response["disclaimer"] = DISCLAIMER
        return FinancialSafetyGuardrails.apply(response, context)

    @staticmethod
    def disclaimer() -> str:
        return DISCLAIMER
