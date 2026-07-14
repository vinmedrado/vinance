from __future__ import annotations

import json
import math
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, pstdev
from typing import Any

from .config import DEFAULT_CONFIG, PaperTradingConfig
from .models import PaperPosition, PaperTrade, PortfolioSnapshot, PortfolioState


class PaperTradingReportWriter:
    def __init__(self, config: PaperTradingConfig = DEFAULT_CONFIG) -> None:
        self.config = config

    def write_all(self, portfolio: PortfolioState) -> dict[str, Path]:
        self.config.output_root.mkdir(parents=True, exist_ok=True)
        payloads = {
            "positions": [position_to_dict(item) for item in portfolio.positions],
            "equity_curve": [snapshot_to_dict(item) for item in portfolio.equity_curve],
            "portfolio_summary": portfolio_summary(portfolio),
            "daily_results": [
                {"date": day.isoformat(), "net_pnl": pnl, "return": pnl / portfolio.initial_capital}
                for day, pnl in sorted(portfolio.daily_results.items())
            ],
            "trade_log": [trade_to_dict(item) for item in portfolio.trades],
        }
        paths: dict[str, Path] = {}
        for name, payload in payloads.items():
            path = self.config.output_root / f"{name}.json"
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
            paths[name] = path
        return paths


def portfolio_summary(portfolio: PortfolioState) -> dict[str, Any]:
    metrics = calculate_metrics(portfolio.trades, portfolio.equity_curve, portfolio.initial_capital)
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "initial_capital": portfolio.initial_capital,
        "cash": portfolio.cash,
        "equity": portfolio.equity,
        "invested_capital": portfolio.invested_capital,
        "cumulative_profit": portfolio.cumulative_profit,
        "drawdown": portfolio.max_drawdown,
        **metrics,
    }


def calculate_metrics(
    trades: list[PaperTrade],
    equity_curve: list[PortfolioSnapshot],
    initial_capital: float,
) -> dict[str, Any]:
    pnls = [trade.net_pnl for trade in trades]
    wins = [value for value in pnls if value > 0]
    losses = [value for value in pnls if value < 0]
    gross_profit = sum(wins)
    gross_loss = sum(losses)
    net_profit = sum(pnls)
    returns = [trade.return_pct for trade in trades]
    downside = [value for value in returns if value < 0]
    max_drawdown = max((snapshot.drawdown for snapshot in equity_curve), default=0.0)
    average_win = mean(wins) if wins else 0.0
    average_loss = mean(losses) if losses else 0.0
    average_trade = mean(pnls) if pnls else 0.0
    return {
        "net_profit": net_profit,
        "gross_profit": gross_profit,
        "gross_loss": gross_loss,
        "profit_factor": gross_profit / abs(gross_loss) if gross_loss else math.inf if gross_profit else 0.0,
        "win_rate": len(wins) / len(trades) if trades else 0.0,
        "average_win": average_win,
        "average_loss": average_loss,
        "average_trade": average_trade,
        "payoff_ratio": average_win / abs(average_loss) if average_loss else math.inf if average_win else 0.0,
        "sharpe": _ratio(returns),
        "sortino": _ratio(returns, downside_only=True),
        "expectancy": average_trade,
        "max_drawdown": max_drawdown,
        "recovery_factor": net_profit / (initial_capital * max_drawdown) if max_drawdown else math.inf if net_profit > 0 else 0.0,
        "number_of_trades": len(trades),
        "winning_trades": len(wins),
        "losing_trades": len(losses),
        "average_time_in_position": mean([trade.holding_candles for trade in trades]) if trades else 0.0,
    }


def _ratio(values: list[float], *, downside_only: bool = False) -> float:
    sample = [value for value in values if value < 0] if downside_only else values
    if not values or len(sample) < 2:
        return 0.0
    denominator = pstdev(sample)
    if denominator == 0:
        return 0.0
    return mean(values) / denominator


def position_to_dict(position: PaperPosition) -> dict[str, Any]:
    return asdict(position)


def trade_to_dict(trade: PaperTrade) -> dict[str, Any]:
    return asdict(trade)


def snapshot_to_dict(snapshot: PortfolioSnapshot) -> dict[str, Any]:
    return asdict(snapshot)
