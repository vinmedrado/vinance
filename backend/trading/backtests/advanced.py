from __future__ import annotations

from dataclasses import dataclass
from math import sqrt

import numpy as np
import pandas as pd


@dataclass
class AdvancedBacktestResult:
    equity_curve: pd.DataFrame
    trades: pd.DataFrame
    metrics: dict[str, float]


def run_advanced_long_backtest(
    frame: pd.DataFrame,
    initial_cash: float = 10_000.0,
    fee_bps: float = 10.0,
    slippage_bps: float = 5.0,
    buy_threshold: float = 0.65,
    exit_threshold: float = 0.48,
    stop_loss_pct: float = 0.015,
    take_profit_pct: float = 0.025,
    max_bars_in_trade: int = 36,
    cooldown_bars: int = 6,
) -> AdvancedBacktestResult:
    data = frame.sort_values("open_time").reset_index(drop=True).copy()
    if data.empty:
        return AdvancedBacktestResult(pd.DataFrame(), pd.DataFrame(), {
            "initial_cash": initial_cash,
            "final_equity": initial_cash,
            "return_pct": 0.0,
            "max_drawdown_pct": 0.0,
            "trades": 0,
        })

    cost = (fee_bps + slippage_bps) / 10_000
    cash = initial_cash
    units = 0.0
    entry_price = 0.0
    entry_time = None
    entry_index = -1
    cooldown_until = -1
    equity_rows: list[dict[str, object]] = []
    trades: list[dict[str, object]] = []

    for index, row in data.iterrows():
        price = float(row["close"])
        high = float(row.get("high", price))
        low = float(row.get("low", price))
        probability = float(row.get("probability_up", 0.5))

        if units == 0 and index >= cooldown_until and probability >= buy_threshold:
            executed_entry = price * (1 + cost)
            units = cash / executed_entry
            cash = 0.0
            entry_price = executed_entry
            entry_time = row["open_time"]
            entry_index = index

        elif units > 0:
            stop_price = entry_price * (1 - stop_loss_pct)
            target_price = entry_price * (1 + take_profit_pct)
            exit_price = None
            reason = None

            if low <= stop_price:
                exit_price, reason = stop_price, "STOP_LOSS"
            elif high >= target_price:
                exit_price, reason = target_price, "TAKE_PROFIT"
            elif probability <= exit_threshold:
                exit_price, reason = price, "MODEL_EXIT"
            elif index - entry_index >= max_bars_in_trade:
                exit_price, reason = price, "TIME_EXIT"

            if exit_price is not None:
                executed_exit = exit_price * (1 - cost)
                cash = units * executed_exit
                pnl_pct = (executed_exit / entry_price - 1) * 100
                trades.append({
                    "entry_time": entry_time,
                    "exit_time": row["open_time"],
                    "entry_price": entry_price,
                    "exit_price": executed_exit,
                    "pnl_pct": pnl_pct,
                    "exit_reason": reason,
                    "bars_held": index - entry_index,
                })
                units = 0.0
                entry_price = 0.0
                entry_time = None
                cooldown_until = index + cooldown_bars

        equity_rows.append({
            "open_time": row["open_time"],
            "equity": cash + units * price,
        })

    if units > 0:
        final_price = float(data.iloc[-1]["close"]) * (1 - cost)
        cash = units * final_price
        trades.append({
            "entry_time": entry_time,
            "exit_time": data.iloc[-1]["open_time"],
            "entry_price": entry_price,
            "exit_price": final_price,
            "pnl_pct": (final_price / entry_price - 1) * 100,
            "exit_reason": "END_OF_TEST",
            "bars_held": len(data) - 1 - entry_index,
        })
        equity_rows[-1]["equity"] = cash

    curve = pd.DataFrame(equity_rows)
    trades_frame = pd.DataFrame(trades)
    final_equity = float(curve["equity"].iloc[-1])
    returns = curve["equity"].pct_change().fillna(0.0)
    running_max = curve["equity"].cummax()
    drawdown = curve["equity"] / running_max - 1
    negative_returns = returns[returns < 0]

    annual_factor = sqrt(365 * 24 * 12)  # candles de 5 minutos
    sharpe = float(returns.mean() / returns.std(ddof=0) * annual_factor) if returns.std(ddof=0) > 0 else 0.0
    sortino = float(returns.mean() / negative_returns.std(ddof=0) * annual_factor) if not negative_returns.empty and negative_returns.std(ddof=0) > 0 else 0.0

    if trades_frame.empty:
        wins = losses = pd.Series(dtype=float)
    else:
        wins = trades_frame.loc[trades_frame["pnl_pct"] > 0, "pnl_pct"]
        losses = trades_frame.loc[trades_frame["pnl_pct"] < 0, "pnl_pct"]

    gross_profit = float(wins.sum()) if not wins.empty else 0.0
    gross_loss = abs(float(losses.sum())) if not losses.empty else 0.0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else (999.0 if gross_profit > 0 else 0.0)
    buy_hold_return = (float(data.iloc[-1]["close"]) / float(data.iloc[0]["close"]) - 1) * 100

    metrics = {
        "initial_cash": initial_cash,
        "final_equity": final_equity,
        "return_pct": (final_equity / initial_cash - 1) * 100,
        "buy_hold_return_pct": buy_hold_return,
        "excess_return_pct": (final_equity / initial_cash - 1) * 100 - buy_hold_return,
        "max_drawdown_pct": float(drawdown.min() * 100),
        "sharpe": sharpe,
        "sortino": sortino,
        "trades": int(len(trades_frame)),
        "win_rate_pct": float((trades_frame["pnl_pct"] > 0).mean() * 100) if not trades_frame.empty else 0.0,
        "profit_factor": float(profit_factor),
        "average_trade_pct": float(trades_frame["pnl_pct"].mean()) if not trades_frame.empty else 0.0,
        "best_trade_pct": float(trades_frame["pnl_pct"].max()) if not trades_frame.empty else 0.0,
        "worst_trade_pct": float(trades_frame["pnl_pct"].min()) if not trades_frame.empty else 0.0,
    }
    return AdvancedBacktestResult(curve, trades_frame, metrics)
