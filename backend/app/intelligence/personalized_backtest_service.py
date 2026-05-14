from __future__ import annotations

from datetime import date
from math import pow

from backend.app.intelligence.benchmarks import ANNUAL_BENCHMARK_RETURNS, SCENARIO_MULTIPLIERS
from backend.app.intelligence.schemas import BacktestScenario, PersonalizedBacktestOut

DISCLAIMER = "O Vinance fornece simulações e análises educacionais baseadas em dados históricos e modelos estatísticos. Isso não constitui recomendação financeira."


def _months_until(target_date: date | None, default: int = 60) -> int:
    if not target_date:
        return default
    today = date.today()
    months = (target_date.year - today.year) * 12 + (target_date.month - today.month)
    return max(months, 1)


def _future_value_monthly(monthly: float, months: int, annual_return: float) -> float:
    if months <= 0:
        return 0.0
    monthly_rate = pow(1 + annual_return, 1 / 12) - 1
    if abs(monthly_rate) < 1e-9:
        return monthly * months
    return monthly * ((pow(1 + monthly_rate, months) - 1) / monthly_rate)


class PersonalizedBacktestService:
    @staticmethod
    def simulate(*, profile, allocation, capacity) -> PersonalizedBacktestOut:
        risk = getattr(profile, "risk_profile", "moderate") or "moderate"
        annual_return = {"conservative": 0.075, "moderate": 0.105, "aggressive": 0.135}.get(risk, 0.105)
        worst_drop = {"conservative": -8.0, "moderate": -18.0, "aggressive": -32.0}.get(risk, -18.0)
        monthly = max(float(getattr(capacity, "monthly_contribution_capacity", 0) or getattr(profile, "monthly_investment_capacity", 0) or 0), 0)
        months = _months_until(getattr(profile, "target_date", None), 60)
        target = float(getattr(profile, "target_amount", 0) or 0)

        base_final = _future_value_monthly(monthly, months, annual_return)
        scenarios: list[BacktestScenario] = []
        for name, multiplier in SCENARIO_MULTIPLIERS.items():
            final_amount = _future_value_monthly(monthly, months, annual_return * multiplier)
            chance = None
            if target > 0:
                ratio = final_amount / target
                chance = max(5.0, min(95.0, ratio * 70))
            scenarios.append(BacktestScenario(name=name, estimated_final_amount=round(final_amount, 2), estimated_gain=round(max(final_amount - monthly * months, 0), 2), chance_to_reach_goal_pct=round(chance, 2) if chance is not None else None))

        chance_base = None
        if target > 0:
            chance_base = max(5.0, min(95.0, (base_final / target) * 70))
        benchmark_comparison = {
            name: round(_future_value_monthly(monthly, months, ret), 2)
            for name, ret in ANNUAL_BENCHMARK_RETURNS.items()
        }
        risk_label = {"conservative": "baixo", "moderate": "médio", "aggressive": "alto"}.get(risk, "médio")
        summary = f"Com aporte de R$ {monthly:,.2f}/mês por {months} meses, o cenário base acumula aproximadamente R$ {base_final:,.2f}.".replace(",", "X").replace(".", ",").replace("X", ".")
        return PersonalizedBacktestOut(
            monthly_contribution=round(monthly, 2),
            horizon_months=months,
            simulated_historical_return=round(base_final, 2),
            worst_simulated_drop_pct=worst_drop,
            estimated_goal_success_chance_pct=round(chance_base, 2) if chance_base is not None else None,
            risk_label=risk_label,
            benchmark_comparison=benchmark_comparison,
            scenarios=scenarios,
            plain_language_summary=summary,
            disclaimer=DISCLAIMER,
        )
