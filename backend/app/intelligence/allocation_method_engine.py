from __future__ import annotations

from dataclasses import asdict
from typing import Any

from backend.app.intelligence.budget_model_advisor_service import BudgetAdvisorInput, BudgetModelAdvisorService


class AllocationMethodEngine:
    """Engine formal de método financeiro do Vinance.

    Ele mantém a regra de orçamento no backend, de forma extensível e vendável:
    ERP -> BudgetAdvisorInput -> método financeiro -> limites -> explicação -> frontend.
    """

    @classmethod
    def build(cls, collected: BudgetAdvisorInput | dict[str, Any], advisor: dict[str, Any] | None = None) -> dict[str, Any]:
        if isinstance(collected, dict):
            collected = BudgetAdvisorInput(**collected)
        advisor = advisor or BudgetModelAdvisorService.recommend(collected)
        method = advisor.get("recommended_model", "50_30_20")
        limits = advisor.get("suggested_limits", {}) or {}
        capacity = float(advisor.get("investment_capacity", 0) or 0)
        income = float(collected.monthly_income or 0)
        expenses = float(collected.total_expenses or 0)
        surplus = max(income - expenses, 0)

        method_labels = {
            "base_zero": "Base Zero",
            "70_20_10": "70/20/10",
            "60_30_10": "60/30/10",
            "50_30_20": "50/30/20",
            "custom_aggressive": "Aceleração patrimonial adaptativa",
            "recovery": "Recuperação financeira",
        }

        return {
            "method": method,
            "method_label": advisor.get("model_label") or method_labels.get(method, method),
            "limits": limits,
            "safe_to_invest": capacity,
            "income": income,
            "expenses": expenses,
            "surplus": surplus,
            "rationale": advisor.get("reason", "Plano calculado a partir das receitas, despesas, reserva e risco financeiro."),
            "action_plan": advisor.get("action_plan", []),
            "warnings": advisor.get("warnings", []),
            "investment_gate": advisor.get("investment_gate", {}),
            "input_summary": advisor.get("input_summary", asdict(collected)),
        }
