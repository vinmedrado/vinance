from __future__ import annotations

from backend.app.intelligence.schemas import CapacityOut


def _money(value: float) -> str:
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


class FinancialCapacityService:
    """Calcula capacidade financeira em linguagem simples, sem jargão técnico."""

    @staticmethod
    def calculate(
        *,
        monthly_income: float,
        monthly_expenses: float,
        available_to_invest: float | None = None,
        emergency_reserve_months: float = 0,
        risk_profile: str = "moderate",
    ) -> CapacityOut:
        income = max(float(monthly_income or 0), 0.0)
        expenses = max(float(monthly_expenses or 0), 0.0)
        surplus = max(income - expenses, 0.0)
        manual_available = max(float(available_to_invest or 0), 0.0)
        base_available = manual_available if manual_available > 0 else surplus

        expenses_ratio = (expenses / income * 100) if income else 0.0
        investable_ratio = (base_available / income * 100) if income else 0.0
        reserve_target = expenses * max(float(emergency_reserve_months or 6), 3.0)

        risk_factor = {"conservative": 0.45, "moderate": 0.65, "aggressive": 0.8}.get(risk_profile, 0.65)
        healthy_limit = min(base_available, surplus * risk_factor) if surplus > 0 else 0.0
        safety_margin = max(surplus - healthy_limit, 0.0)

        if income <= 0 or expenses_ratio >= 95:
            financial_risk = "alto"
        elif expenses_ratio >= 80:
            financial_risk = "médio"
        else:
            financial_risk = "baixo"

        alerts: list[str] = []
        if income <= 0:
            alerts.append("Cadastre sua renda mensal para receber uma sugestão mais precisa.")
        if surplus <= 0:
            alerts.append("Antes de investir, o ideal é reorganizar o fluxo mensal para criar sobra positiva.")
        if emergency_reserve_months < 3:
            alerts.append("Sua reserva parece baixa. Priorize uma reserva antes de assumir mais risco.")
        if expenses_ratio > 85:
            alerts.append("Suas despesas estão consumindo grande parte da renda. O aporte sugerido foi reduzido por segurança.")

        summary = (
            f"Você pode investir aproximadamente {_money(healthy_limit)}/mês mantendo uma margem segura."
            if healthy_limit > 0 else
            "Ainda não há margem segura para investir. O foco recomendado é reduzir despesas e montar reserva."
        )

        return CapacityOut(
            monthly_surplus=round(surplus, 2),
            expenses_ratio_pct=round(expenses_ratio, 2),
            investable_ratio_pct=round(investable_ratio, 2),
            recommended_emergency_reserve=round(reserve_target, 2),
            healthy_investment_limit=round(healthy_limit, 2),
            financial_risk=financial_risk,
            safety_margin=round(safety_margin, 2),
            monthly_contribution_capacity=round(healthy_limit, 2),
            plain_language_summary=summary,
            alerts=alerts,
        )
