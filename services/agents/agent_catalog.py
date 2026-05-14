
from __future__ import annotations
from typing import Any
from services.agents.base_agent import BaseAgent


class CatalogAgent(BaseAgent):
    name = "catalog"
    description = "Analisa qualidade do catálogo de ativos e scores de qualidade."

    def run_fallback(self, context: dict[str, Any]) -> dict[str, Any]:
        catalog = context.get("catalog") or {}
        avg_quality = catalog.get("avg_quality_score")
        total_assets = int(catalog.get("total_assets") or 0)
        low_quality = int(catalog.get("low_quality_assets") or 0)
        coverage = context.get("coverage") or {}

        try:
            avg = float(avg_quality) if avg_quality is not None else None
        except Exception:
            avg = None

        insights = []
        recommendations = ["Mantenha validação periódica do catálogo antes de rodar rankings e análises."]
        status = "ok"
        score = 60 if avg is None else max(0, min(100, avg))

        if total_assets <= 0:
            status = "critical"
            insights.append(self.make_insight("high", "Catálogo vazio", "Nenhum ativo foi encontrado no catálogo.", "Importe ou sincronize ativos antes de rodar análises."))
        else:
            insights.append(self.make_insight("low", "Base catalogada", f"O catálogo possui {total_assets} ativo(s).", "Mantenha a base limpa e validada."))

        if avg is None:
            status = "warning"
            insights.append(self.make_insight("medium", "Score de qualidade ausente", "Não foi possível calcular qualidade média do catálogo.", "Rode atualização de quality scores."))
        elif avg < 50:
            status = "critical"
            insights.append(self.make_insight("high", "Qualidade baixa", f"Score médio do catálogo está em {avg:.1f}.", "Corrija metadados, classe, ticker e identificadores."))
        elif avg < 75:
            status = "warning"
            insights.append(self.make_insight("medium", "Qualidade intermediária", f"Score médio do catálogo está em {avg:.1f}.", "Priorize ativos com menor score."))
        else:
            insights.append(self.make_insight("low", "Boa qualidade de catálogo", f"Score médio do catálogo está em {avg:.1f}.", "Continue monitorando ativos novos."))

        if low_quality > 0:
            if status == "ok":
                status = "warning"
            insights.append(self.make_insight("medium", "Ativos de baixa qualidade", f"{low_quality} ativo(s) aparecem com qualidade baixa.", "Revise os ativos listados como baixa qualidade."))

        return {
            "agent": self.name,
            "status": status,
            "summary": "Avaliação coordenada da qualidade do catálogo.",
            "insights": insights,
            "recommendations": recommendations,
            "metrics_used": {
                "total_assets": total_assets,
                "avg_quality_score": avg,
                "low_quality_assets": low_quality,
                "assets_with_price": coverage.get("assets_with_price"),
            },
            "score": score,
            "recommended_assets": catalog.get("top_quality_assets") or [],
            "avoid_assets": catalog.get("low_quality_asset_list") or [],
        }
