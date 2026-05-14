from __future__ import annotations

from datetime import date, timedelta
from math import pow
from typing import Any


class DynamicGoalsService:
    """Recalcula metas quando renda, despesas, reserva ou comportamento mudam."""

    @classmethod
    def recalculate(cls, goals: list[dict[str, Any]], *, monthly_capacity: float, behavior: dict[str, Any] | None = None, inflation_annual: float = 0.045) -> dict[str, Any]:
        behavior = behavior or {}
        capacity = max(float(monthly_capacity or 0), 0.0)
        discipline = int(behavior.get("discipline_score", 60))
        capacity_factor = 0.80 if discipline >= 75 else 0.65 if discipline >= 55 else 0.45
        suggested_pool = capacity * capacity_factor
        results = []
        for goal in goals or []:
            target = float(goal.get("target_amount", 0) or 0)
            current = float(goal.get("current_amount", 0) or 0)
            target_date = goal.get("target_date")
            months = cls._months_until(target_date)
            adjusted = target * pow(1 + inflation_annual, months / 12)
            remaining = max(adjusted - current, 0)
            required = remaining / max(months, 1)
            suggested = min(max(required, 0), suggested_pool) if suggested_pool else 0
            estimated_months = int(remaining / suggested) if suggested > 0 else None
            probability = cls._probability(suggested, required, discipline)
            results.append({
                "goal_type": goal.get("goal_type", "personalizado"),
                "target_amount": round(target, 2),
                "inflation_adjusted_target": round(adjusted, 2),
                "remaining_amount": round(remaining, 2),
                "required_monthly_contribution": round(required, 2),
                "suggested_monthly_contribution": round(suggested, 2),
                "success_probability": probability,
                "estimated_completion_months": estimated_months,
                "plain_language_summary": cls._summary(probability, required, suggested),
            })
        return {"goals": results, "available_goal_capacity": round(suggested_pool, 2), "behavior_adjustment": capacity_factor}

    @staticmethod
    def _months_until(value: Any) -> int:
        if isinstance(value, date):
            today = date.today()
            return max((value.year - today.year) * 12 + value.month - today.month, 1)
        return 24

    @staticmethod
    def _probability(suggested: float, required: float, discipline: int) -> int:
        if required <= 0:
            return 100
        base = min(suggested / required, 1.2) / 1.2 * 85
        return int(max(5, min(95, base + (discipline - 60) * 0.25)))

    @staticmethod
    def _summary(probability: int, required: float, suggested: float) -> str:
        if probability >= 75:
            return "Meta bem encaminhada com o aporte sugerido atual."
        if probability >= 45:
            return "Meta possível, mas depende de consistência e acompanhamento mensal."
        if suggested <= 0:
            return "Antes de acelerar esta meta, o ideal é recuperar margem financeira."
        return "Meta apertada no prazo atual; considere aumentar prazo, reduzir valor ou elevar aporte."
