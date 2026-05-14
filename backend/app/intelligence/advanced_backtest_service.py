from __future__ import annotations

import math, random
from statistics import mean, pstdev
from typing import Sequence

from backend.app.intelligence.schemas import AdvancedBacktestOut, AdvancedBacktestRequest, AllocationOut, BacktestScenario, FinancialProfileOut

DISCLAIMER = "O Vinance fornece análises e simulações educacionais baseadas em dados históricos e modelos quantitativos. Isso não constitui recomendação financeira."
MARKET_RETURNS = {"cash": 0.055, "fixed_income": 0.095, "etfs": 0.115, "fiis": 0.105, "equities": 0.13, "bdrs": 0.12, "crypto": 0.18}
MARKET_VOL = {"cash": 0.005, "fixed_income": 0.025, "etfs": 0.13, "fiis": 0.12, "equities": 0.2, "bdrs": 0.18, "crypto": 0.45}


def _weighted(allocation: AllocationOut, table: dict[str, float]) -> float:
    total = 0.0
    for item in allocation.suggested_allocation:
        total += table.get(item.market, table.get(item.market.lower(), 0.08)) * item.percentage / 100
    return total


def _max_drawdown(values: Sequence[float]) -> float:
    peak = values[0] if values else 1
    worst = 0.0
    for v in values:
        peak = max(peak, v)
        if peak > 0:
            worst = min(worst, (v / peak) - 1)
    return abs(worst) * 100


class AdvancedBacktestService:
    """Backtest quantitativo interno com tradução para linguagem de usuário."""

    @staticmethod
    def run(*, profile: FinancialProfileOut | object, allocation: AllocationOut, request: AdvancedBacktestRequest | None = None) -> AdvancedBacktestOut:
        req = request or AdvancedBacktestRequest()
        months = int(req.horizon_months or 120)
        contribution = float(req.monthly_contribution or getattr(profile, 'monthly_investment_capacity', 0) or 0)
        target = float(getattr(profile, 'target_amount', 0) or 0)
        annual_return = _weighted(allocation, MARKET_RETURNS)
        annual_vol = max(_weighted(allocation, MARKET_VOL), 0.01)
        monthly_return = (1 + annual_return) ** (1/12) - 1
        monthly_vol = annual_vol / math.sqrt(12)
        cost_drag = (req.transaction_cost_bps + req.slippage_bps) / 10000 / 12
        tax_drag = max(req.tax_rate, 0) * max(monthly_return, 0) * 0.08
        rng = random.Random(req.seed)
        values = []
        value = 0.0
        returns = []
        for _ in range(months):
            simulated_r = rng.gauss(monthly_return, monthly_vol) - cost_drag - tax_drag
            value = max(0.0, value * (1 + simulated_r) + contribution)
            values.append(value)
            returns.append(simulated_r)
        final = values[-1] if values else 0
        invested = contribution * months
        years = max(months / 12, 1/12)
        cagr = ((final / invested) ** (1/years) - 1) * 100 if invested > 0 and final > 0 else 0
        vol = pstdev(returns) * math.sqrt(12) * 100 if len(returns) > 1 else 0
        avg = mean(returns) * 12 if returns else 0
        downside = [min(r, 0) for r in returns]
        downside_dev = pstdev(downside) * math.sqrt(12) if len(downside) > 1 else 0.0001
        sharpe = (avg - 0.06) / (vol/100) if vol else 0
        sortino = (avg - 0.06) / downside_dev if downside_dev else 0
        mdd = _max_drawdown(values)
        calmar = cagr / mdd if mdd else cagr
        ibov = invested * ((1 + 0.105/12) ** months) if invested else 0
        cdi = invested * ((1 + 0.095/12) ** months) if invested else 0
        success = 0 if target <= 0 else max(1, min(99, 50 + (final - target) / target * 45))
        rolling = []
        for start in range(0, max(months-12, 1), 12):
            window = values[start:min(start+12, len(values))]
            if window:
                rolling.append({"month": float(start+1), "ending_value": round(window[-1], 2), "drawdown_pct": round(_max_drawdown(window), 2)})
        scenarios = [
            BacktestScenario(name="pessimista", estimated_final_amount=round(final*0.78,2), estimated_gain=round(max(final*0.78-invested,0),2), chance_to_reach_goal_pct=round(max(success-25,1),2) if target else None),
            BacktestScenario(name="base", estimated_final_amount=round(final,2), estimated_gain=round(max(final-invested,0),2), chance_to_reach_goal_pct=round(success,2) if target else None),
            BacktestScenario(name="otimista", estimated_final_amount=round(final*1.22,2), estimated_gain=round(max(final*1.22-invested,0),2), chance_to_reach_goal_pct=round(min(success+20,99),2) if target else None),
        ]
        risk_label = "baixo" if mdd < 8 else "moderado" if mdd < 22 else "elevado"
        summary = f"Com aportes de R$ {contribution:,.2f}/mês, a simulação educativa chegou a aproximadamente R$ {final:,.2f} no cenário base.".replace(',', 'X').replace('.', ',').replace('X', '.')
        return AdvancedBacktestOut(
            internal_metrics={"CAGR": round(cagr,2), "max_drawdown": round(mdd,2), "volatility": round(vol,2), "Sharpe": round(sharpe,3), "Sortino": round(sortino,3), "Calmar": round(calmar,3), "downside_deviation": round(downside_dev*100,2), "benchmark_alpha": round(((final - ibov) / ibov * 100) if ibov else 0,2)},
            benchmark_comparison={"CDI_simulado": round(cdi,2), "Ibovespa_simulado": round(ibov,2), "carteira_sugerida": round(final,2)},
            walk_forward={"windows_tested": float(max(1, len(rolling))), "median_window_value": round(mean([r['ending_value'] for r in rolling]) if rolling else final,2), "stability_score": round(max(0, 100-mdd-vol),2)},
            rolling_windows=rolling[:24],
            scenarios=scenarios,
            user_summary=summary,
            risk_label=risk_label,
            disclaimer=DISCLAIMER,
        )
