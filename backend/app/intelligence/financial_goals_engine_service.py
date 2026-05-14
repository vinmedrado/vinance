from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
import math

from backend.app.intelligence.schemas import BacktestScenario, FinancialGoalEngineIn, FinancialGoalEngineOut

ANNUAL_RETURN_BY_RISK = {"conservative": 0.075, "moderate": 0.105, "aggressive": 0.135}
ANNUAL_VOL_BY_RISK = {"conservative": 0.055, "moderate": 0.11, "aggressive": 0.19}
DEFAULT_INFLATION = 0.045


def _months_until(target_date: date | None, today: date | None = None) -> int:
    today = today or date.today()
    if not target_date or target_date <= today:
        return 12
    return max((target_date.year - today.year) * 12 + target_date.month - today.month, 1)


def _future_value_monthly(current: float, contribution: float, months: int, annual_return: float) -> float:
    r = (1 + annual_return) ** (1 / 12) - 1
    value = current * ((1 + r) ** months)
    if r == 0:
        value += contribution * months
    else:
        value += contribution * (((1 + r) ** months - 1) / r)
    return value


def _required_monthly(target: float, current: float, months: int, annual_return: float) -> float:
    r = (1 + annual_return) ** (1 / 12) - 1
    current_future = current * ((1 + r) ** months)
    missing = max(target - current_future, 0)
    if missing <= 0:
        return 0
    if r == 0:
        return missing / months
    return missing * r / (((1 + r) ** months - 1))


class FinancialGoalsEngineService:
    """Calcula metas financeiras com cenários simples e explicáveis."""

    @staticmethod
    def evaluate(payload: FinancialGoalEngineIn, *, organization_id: str | None = None, user_id: str | None = None, goal_id: int | None = None, today: date | None = None) -> FinancialGoalEngineOut:
        today = today or date.today()
        months = _months_until(payload.target_date, today)
        years = months / 12
        target = max(float(payload.target_amount), 0.0)
        current = max(float(payload.current_amount), 0.0)
        contribution = max(float(payload.monthly_contribution), 0.0)
        annual_return = ANNUAL_RETURN_BY_RISK.get(payload.risk_profile, ANNUAL_RETURN_BY_RISK["moderate"])
        vol = ANNUAL_VOL_BY_RISK.get(payload.risk_profile, ANNUAL_VOL_BY_RISK["moderate"])
        adjusted_target = target * ((1 + DEFAULT_INFLATION) ** years)
        projected = _future_value_monthly(current, contribution, months, annual_return)
        required = _required_monthly(adjusted_target, current, months, annual_return)
        amount_remaining = max(adjusted_target - current, 0)

        # Probabilidade educativa: distância até alvo ajustada por risco e tempo.
        gap_ratio = max((adjusted_target - projected) / adjusted_target, -1.0) if adjusted_target > 0 else 0
        base_prob = 72 - (gap_ratio * 55) - (vol * 35)
        success_probability = max(5, min(95, base_prob))

        if contribution <= 0:
            completion_months = None
        else:
            completion_months = 0
            value = current
            while value < adjusted_target and completion_months < 600:
                value = value * ((1 + annual_return) ** (1 / 12)) + contribution
                completion_months += 1
        estimated_completion_date = today + timedelta(days=30 * completion_months) if completion_months is not None else None
        delay_months = max((completion_months or months) - months, 0)

        def scenario(name: str, multiplier: float) -> BacktestScenario:
            val = _future_value_monthly(current, contribution, months, annual_return * multiplier)
            chance = max(1, min(99, success_probability + (multiplier - 1) * 60))
            return BacktestScenario(name=name, estimated_final_amount=round(val, 2), estimated_gain=round(max(val - current - contribution * months, 0), 2), chance_to_reach_goal_pct=round(chance, 2))

        scenarios = [scenario("pessimista", 0.55), scenario("base", 1.0), scenario("otimista", 1.35)]
        if projected >= adjusted_target:
            summary = "Sua meta parece alcançável no prazo com o aporte informado, mantendo uma margem razoável."
        elif required > contribution:
            summary = f"Para aumentar a chance de atingir a meta, o aporte mensal estimado deveria ficar próximo de R$ {required:,.2f}.".replace(',', 'X').replace('.', ',').replace('X', '.')
        else:
            summary = "A meta está próxima do equilíbrio, mas exige disciplina de aporte e revisão periódica."

        explanations = [
            "A meta foi ajustada por inflação para evitar subestimar o valor futuro necessário.",
            "A probabilidade é uma estimativa educativa baseada em prazo, aporte e perfil de risco.",
            "Os cenários ajudam a visualizar o impacto de mercados mais fracos ou mais fortes sem prometer resultado.",
        ]
        return FinancialGoalEngineOut(
            id=goal_id,
            organization_id=organization_id,
            user_id=user_id,
            goal_type=payload.goal_type,
            target_amount=round(target, 2),
            current_amount=round(current, 2),
            target_date=payload.target_date,
            monthly_contribution=round(contribution, 2),
            inflation_adjusted_target=round(adjusted_target, 2),
            risk_profile=payload.risk_profile,
            investment_horizon=payload.investment_horizon,
            success_probability=round(success_probability, 2),
            estimated_completion_date=estimated_completion_date,
            amount_remaining=round(amount_remaining, 2),
            required_monthly_contribution=round(required, 2),
            months_to_goal=months,
            delay_months=delay_months,
            scenarios=scenarios,
            plain_language_summary=summary,
            explanations=explanations,
        )
