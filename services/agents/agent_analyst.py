
from __future__ import annotations
from typing import Any
from services.agents.base_agent import BaseAgent


class AnalystAgent(BaseAgent):
    name = "analyst"
    description = "Analisa visão geral usando outputs de catálogo, estratégia e risco."

    def run_fallback(self, context: dict[str, Any]) -> dict[str, Any]:
        orchestrator = context.get("orchestrator") or {}
        coverage = context.get("coverage") or {}
        catalog_out = (context.get("agent_outputs") or {}).get("catalog") or {}
        strategy_out = (context.get("agent_outputs") or {}).get("strategy") or {}
        risk_out = (context.get("agent_outputs") or {}).get("risk") or {}
        catalog = context.get("catalog") or {}

        total_assets = int(catalog.get("total_assets") or coverage.get("total_assets") or 0)
        assets_with_price = int(coverage.get("assets_with_price") or 0)
        coverage_rate = (assets_with_price / total_assets) if total_assets else 0

        status = "ok"
        insights = []
        recommendations = ["Use o Orquestrador Geral para manter o ciclo operacional consistente."]

        orch_status = orchestrator.get("status") or orchestrator.get("status_final")
        if orch_status == "failed":
            status = "critical"
            insights.append(self.make_insight("high", "Orquestrador falhou", "A última execução do orquestrador falhou.", "Revise logs antes de confiar nos dados."))
        elif orch_status == "partial_success":
            status = "warning"
            insights.append(self.make_insight("medium", "Execução parcial", "A última execução concluiu com alertas.", "Confira etapas com falhas não críticas."))

        if coverage_rate < 0.5:
            status = "critical"
            insights.append(self.make_insight("high", "Cobertura baixa", f"Cobertura de preços aproximada: {coverage_rate:.1%}.", "Atualize dados de mercado antes de usar rankings."))
        elif coverage_rate < 0.8:
            if status == "ok":
                status = "warning"
            insights.append(self.make_insight("medium", "Cobertura intermediária", f"Cobertura de preços aproximada: {coverage_rate:.1%}.", "Priorize ativos sem preço."))
        else:
            insights.append(self.make_insight("low", "Boa cobertura", f"Cobertura de preços aproximada: {coverage_rate:.1%}.", "Mantenha atualização incremental."))

        for label, output in [("catálogo", catalog_out), ("estratégia", strategy_out), ("risco", risk_out)]:
            if output.get("status") in {"warning", "critical"}:
                priority = "high" if output.get("status") == "critical" else "medium"
                if status != "critical":
                    status = "warning"
                insights.append(self.make_insight(priority, f"Atenção em {label}", output.get("summary") or f"{label} requer atenção.", "Abra a seção do agente para detalhes."))

        score = 100
        if coverage_rate < 0.8:
            score -= 20
        if catalog_out.get("status") in {"warning", "critical"}:
            score -= 15
        if strategy_out.get("status") in {"warning", "critical"}:
            score -= 15
        if risk_out.get("status") == "critical":
            score -= 30
        elif risk_out.get("status") == "warning":
            score -= 15

        return {
            "agent": self.name,
            "status": status,
            "summary": "Análise coordenada do estado operacional do FinanceOS.",
            "insights": insights,
            "recommendations": recommendations,
            "metrics_used": {
                "orchestrator_status": orch_status,
                "coverage_rate": coverage_rate,
                "total_assets": total_assets,
                "assets_with_price": assets_with_price,
                "catalog_status": catalog_out.get("status"),
                "strategy_status": strategy_out.get("status"),
                "risk_status": risk_out.get("status"),
            },
            "score": max(0, min(100, score)),
        }
