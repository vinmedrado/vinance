
from __future__ import annotations
from typing import Any
from services.agents.base_agent import BaseAgent


class ExplainerAgent(BaseAgent):
    name = "explainer"
    description = "Explica o resultado completo em linguagem simples."

    def run_fallback(self, context: dict[str, Any]) -> dict[str, Any]:
        outputs = context.get("agent_outputs") or {}
        global_score = context.get("global_intelligence_score") or {}
        top_insights = context.get("top_insights") or []
        warnings = context.get("warnings") or []
        opportunities = context.get("opportunities") or []

        label = global_score.get("label") or "Atenção"
        score = global_score.get("score")

        risks = [i.get("message") for i in top_insights + warnings if i.get("priority") in {"high", "medium"}][:3]
        opps = [i.get("message") for i in opportunities][:3]

        if label in {"Excelente", "Bom"}:
            summary = f"O FinanceOS está em condição {label.lower()} para análise. Score global: {score}."
        elif label == "Atenção":
            summary = f"O FinanceOS está utilizável, mas com pontos de atenção. Score global: {score}."
        else:
            summary = f"O FinanceOS exige revisão antes de decisões importantes. Score global: {score}."

        if risks:
            summary += " Principais riscos: " + " ".join(risks[:2])
        if opps:
            summary += " Principais oportunidades: " + " ".join(opps[:2])

        insights = []
        if risks:
            insights.append(self.make_insight("high", "Principais riscos", " | ".join(risks), "Resolva riscos de alta prioridade antes de tomar decisões."))
        if opps:
            insights.append(self.make_insight("low", "Principais oportunidades", " | ".join(opps), "Use oportunidades como lista de melhoria incremental."))

        return {
            "agent": self.name,
            "status": "ok" if label in {"Excelente", "Bom"} else "warning" if label == "Atenção" else "critical",
            "summary": summary,
            "insights": insights,
            "recommendations": [
                "Revise primeiro os insights high.",
                "Não altere estratégia automaticamente com base nos agentes.",
                "Rode novamente o orquestrador após corrigir dados e cobertura.",
            ],
            "metrics_used": {
                "global_score": score,
                "label": label,
                "top_insights_count": len(top_insights),
                "warnings_count": len(warnings),
                "opportunities_count": len(opportunities),
            },
            "final_explanation": summary,
        }
