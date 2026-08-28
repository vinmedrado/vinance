from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass
class BacktestResult:
    equity_curve: pd.DataFrame
    metrics: dict[str, float]


def run_long_only_backtest(
    frame: pd.DataFrame,
    initial_cash: float = 10_000.0,
    fee_bps: float = 10.0,
    slippage_bps: float = 5.0,
) -> BacktestResult:
    data = frame.sort_values("open_time").copy()
    cash = initial_cash
    units = 0.0
    equity_rows: list[dict[str, object]] = []
    total_cost_bps = (fee_bps + slippage_bps) / 10_000

    for row in data.itertuples(index=False):
        price = float(row.close)
        signal = getattr(row, "signal", "HOLD")
        if signal == "BUY" and units == 0 and cash > 0:
            units = (cash * (1 - total_cost_bps)) / price
            cash = 0.0
        elif signal == "SELL" and units > 0:
            cash = units * price * (1 - total_cost_bps)
            units = 0.0
        equity_rows.append({"open_time": row.open_time, "equity": cash + units * price})

    curve = pd.DataFrame(equity_rows)
    final_equity = float(curve["equity"].iloc[-1]) if not curve.empty else initial_cash
    running_max = curve["equity"].cummax() if not curve.empty else pd.Series(dtype=float)
    drawdown = curve["equity"] / running_max - 1 if not curve.empty else pd.Series(dtype=float)
    metrics = {
        "initial_cash": initial_cash,
        "final_equity": final_equity,
        "return_pct": (final_equity / initial_cash - 1) * 100,
        "max_drawdown_pct": float(drawdown.min() * 100) if not drawdown.empty else 0.0,
    }
    return BacktestResult(curve, metrics)
