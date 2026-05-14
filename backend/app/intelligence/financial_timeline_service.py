from __future__ import annotations

from typing import Any


class FinancialTimelineService:
    """Monta uma jornada financeira mensal a partir de snapshots e eventos simples."""

    @classmethod
    def build(cls, snapshots: list[dict[str, Any]]) -> dict[str, Any]:
        events = []
        last_model = None
        last_score = None
        for item in sorted(snapshots, key=lambda x: (x.get("year", 0), x.get("month", 0))):
            label = f"{item.get('month', '--'):02d}/{item.get('year', '----')}" if isinstance(item.get('month'), int) else str(item.get("period", "mês"))
            model = item.get("recommended_model") or item.get("model_label")
            score = item.get("health_score")
            if model and model != last_model:
                events.append({"period": label, "type": "model_change", "title": "Modelo financeiro ajustado", "description": f"O plano passou para {model} para acompanhar sua realidade."})
            if score is not None and last_score is not None:
                diff = int(score) - int(last_score)
                if abs(diff) >= 5:
                    direction = "melhorou" if diff > 0 else "piorou"
                    events.append({"period": label, "type": "health_change", "title": "Saúde financeira mudou", "description": f"Seu score {direction} {abs(diff)} pontos."})
            if item.get("investment_capacity", 0) and float(item.get("investment_capacity", 0)) > 0:
                events.append({"period": label, "type": "investment_capacity", "title": "Margem para investir", "description": "Foi identificada uma sobra segura para aporte mensal."})
            last_model = model or last_model
            last_score = score if score is not None else last_score
        if not events:
            events.append({"period": "agora", "type": "start", "title": "Jornada iniciada", "description": "Cadastre renda e despesas para o Vinance acompanhar sua evolução."})
        return {"events": events, "summary": "Linha do tempo da sua jornada financeira pessoal."}
