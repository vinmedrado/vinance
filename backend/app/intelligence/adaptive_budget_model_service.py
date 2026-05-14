from __future__ import annotations

from typing import Any
from backend.app.intelligence.budget_model_advisor_service import BudgetModelAdvisorService
from backend.app.intelligence.financial_health_engine import FinancialHealthEngine


class AdaptiveBudgetModelService:
    """Decide quando o usuário deve migrar de modelo financeiro sem precisar escolher sozinho."""

    @classmethod
    def evaluate(cls, current_input: dict[str, Any], previous_snapshot: dict[str, Any] | None = None) -> dict[str, Any]:
        advisor = BudgetModelAdvisorService.recommend(current_input)
        health = FinancialHealthEngine.calculate({
            "monthly_income": current_input.get("monthly_income", 0),
            "total_expenses": current_input.get("total_expenses", 0),
            "debt_payments": current_input.get("debt_payments", 0),
            "overdue_bills": current_input.get("overdue_bills", 0),
            "emergency_reserve": current_input.get("emergency_reserve", 0),
            "investment_capacity": advisor.get("investment_capacity", 0),
            "previous_health_score": previous_snapshot.get("health_score") if previous_snapshot else None,
        })
        previous_model = previous_snapshot.get("recommended_model") if previous_snapshot else None
        new_model = advisor["recommended_model"]
        changed = bool(previous_model and previous_model != new_model)
        before_after = {
            "before": previous_model or "sem histórico",
            "after": new_model,
            "before_health_score": previous_snapshot.get("health_score") if previous_snapshot else None,
            "after_health_score": health["health_score"],
        }
        reason = cls._reason(changed, previous_model, new_model, health, advisor)
        return {
            "recommended_model": new_model,
            "model_label": advisor["model_label"],
            "changed": changed,
            "change_reason": reason,
            "confidence_score": advisor["confidence_score"],
            "comparison": before_after,
            "health": health,
            "advisor": advisor,
        }

    @staticmethod
    def _reason(changed: bool, old: str | None, new: str, health: dict[str, Any], advisor: dict[str, Any]) -> str:
        if not old:
            return "Este é o primeiro modelo recomendado com base na sua renda, despesas, dívidas e reserva."
        if not changed:
            return "Seu modelo atual continua adequado para este mês."
        if health.get("evolution_trend") == "melhorando":
            return "Sua situação melhorou; o Vinance está ajustando o modelo para uma fase mais equilibrada."
        return "Sua situação mudou; o Vinance ajustou o modelo para proteger sua organização financeira."
