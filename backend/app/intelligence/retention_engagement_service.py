from __future__ import annotations

from typing import Any


class RetentionEngagementService:
    """Marcos financeiros premium, sem gamificação infantil."""

    @classmethod
    def build(cls, history: list[dict[str, Any]], health: dict[str, Any], memory: dict[str, Any]) -> dict[str, Any]:
        milestones = []
        if memory.get("trend") == "melhorando":
            milestones.append({"type": "progress", "title": "Evolução positiva", "description": "Sua trajetória financeira melhorou em relação ao início do histórico."})
        if any("reserva" in p for p in memory.get("patterns", [])):
            milestones.append({"type": "reserve", "title": "Reserva em evolução", "description": "Sua reserva vem crescendo, o que aumenta sua segurança."})
        if any("aportes" in p for p in memory.get("patterns", [])):
            milestones.append({"type": "consistency", "title": "Consistência de aportes", "description": "Você manteve aportes em boa parte do período analisado."})
        if int(health.get("health_score", 0)) >= 70:
            milestones.append({"type": "phase", "title": "Nova fase financeira", "description": "Sua saúde financeira já permite decisões mais estruturadas."})
        if not milestones:
            milestones.append({"type": "start", "title": "Jornada em acompanhamento", "description": "Continue registrando dados para construir histórico e receber recomendações melhores."})
        return {"milestones": milestones, "progress_summary": cls._summary(milestones), "recurring_insights": memory.get("insights", [])[:3]}

    @staticmethod
    def _summary(milestones: list[dict[str, str]]) -> str:
        if len(milestones) >= 3:
            return "Você já possui sinais consistentes de evolução financeira."
        if milestones and milestones[0].get("type") != "start":
            return "Sua evolução começou a aparecer; mantenha o plano por mais alguns ciclos."
        return "O primeiro objetivo é criar histórico e previsibilidade mensal."
