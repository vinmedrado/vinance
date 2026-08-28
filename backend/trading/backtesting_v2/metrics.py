from __future__ import annotations

import math
from collections import Counter, defaultdict
from datetime import datetime
from statistics import mean, pstdev
from typing import Any

from backend.trading.paper_trading_v2.config import PaperTradingConfig
from backend.trading.paper_trading_v2.models import PaperTrade, PortfolioSnapshot
from backend.trading.prediction_engine.decision import AVOID, BUY_CANDIDATE, HOLD
from backend.trading.prediction_engine.models import PredictionResult


def calculate_backtest_metrics(
    *,
    trades: list[PaperTrade],
    equity_curve: list[PortfolioSnapshot],
    predictions: list[PredictionResult],
    initial_capital: float,
    blocked_reasons: dict[str, int] | None = None,
    paper_config: PaperTradingConfig | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    final_capital: float | None = None,
    candles: Any = None,
    blocked_by_confidence: int | None = None,
    blocked_by_risk: int | None = None,
) -> dict[str, Any]:
    blocked_reasons = dict(blocked_reasons or {})
    if blocked_by_confidence is not None:
        blocked_reasons["confidence"] = blocked_by_confidence
    if blocked_by_risk is not None:
        blocked_reasons["risk"] = blocked_by_risk
    paper_config = paper_config or PaperTradingConfig()
    final_capital = final_capital if final_capital is not None else (equity_curve[-1].equity if equity_curve else initial_capital)
    pnls = [trade.net_pnl for trade in trades]
    wins = [value for value in pnls if value > 0]
    losses = [value for value in pnls if value < 0]
    neutrals = [value for value in pnls if value == 0]
    gross_profit = sum(wins)
    gross_loss = sum(losses)
    net_profit = sum(pnls)
    returns = _snapshot_returns(equity_curve)
    downside = [value for value in returns if value < 0]
    drawdowns = [snapshot.drawdown for snapshot in equity_curve]
    max_drawdown = max(drawdowns, default=0.0)
    average_drawdown = mean([value for value in drawdowns if value > 0]) if any(value > 0 for value in drawdowns) else 0.0
    average_win = mean(wins) if wins else 0.0
    average_loss = mean(losses) if losses else 0.0
    average_trade = mean(pnls) if pnls else 0.0
    total_notional = sum(_trade_notional(trade) for trade in trades)
    signal_counts = Counter(prediction.decision for prediction in predictions)
    exit_counts = Counter(trade.exit_reason for trade in trades)
    return {
        "capital_initial": initial_capital,
        "capital_final": final_capital,
        "total_return": (final_capital / initial_capital - 1) if initial_capital else 0.0,
        "annualized_return": _annualized_return(initial_capital, final_capital, start_time, end_time),
        "net_profit": net_profit,
        "gross_profit": gross_profit,
        "gross_loss": gross_loss,
        "profit_factor": gross_profit / abs(gross_loss) if gross_loss else (math.inf if gross_profit else 0.0),
        "win_rate": len(wins) / len(trades) if trades else 0.0,
        "loss_rate": len(losses) / len(trades) if trades else 0.0,
        "average_win": average_win,
        "average_loss": average_loss,
        "average_trade": average_trade,
        "payoff_ratio": average_win / abs(average_loss) if average_loss else (math.inf if average_win else 0.0),
        "expectancy": average_trade,
        "sharpe_ratio": _ratio(returns),
        "sharpe": _ratio(returns),
        "sortino_ratio": _ratio(returns, sample=downside),
        "sortino": _ratio(returns, sample=downside),
        "calmar_ratio": _calmar(initial_capital, final_capital, start_time, end_time, max_drawdown),
        "max_drawdown": max_drawdown,
        "average_drawdown": average_drawdown,
        "recovery_factor": net_profit / (initial_capital * max_drawdown) if max_drawdown else (math.inf if net_profit > 0 else 0.0),
        "number_of_trades": len(trades),
        "winning_trades": len(wins),
        "losing_trades": len(losses),
        "neutral_trades": len(neutrals),
        "average_time_in_position": mean([trade.holding_candles for trade in trades]) if trades else 0.0,
        "average_exposure": _average_exposure(equity_curve),
        "average_invested_capital": mean([snapshot.invested_capital for snapshot in equity_curve]) if equity_curve else 0.0,
        "total_fees": sum(trade.fees for trade in trades),
        "total_slippage": total_notional * paper_config.slippage_bps / 10_000,
        "total_spread": total_notional * paper_config.spread_bps / 10_000,
        "signals_buy_candidate": signal_counts.get(BUY_CANDIDATE, 0),
        "signals_hold": signal_counts.get(HOLD, 0),
        "signals_avoid": signal_counts.get(AVOID, 0),
        "signals_blocked_by_confidence": blocked_reasons.get("confidence", 0),
        "signals_blocked_by_risk": sum(value for key, value in blocked_reasons.items() if key != "confidence"),
        "tp_hits": exit_counts.get("TAKE_PROFIT", 0),
        "sl_hits": exit_counts.get("STOP_LOSS", 0),
        "horizon_expirations": exit_counts.get("HORIZON_EXPIRATION", 0),
    }


def drawdown_curve(equity_curve: list[PortfolioSnapshot]) -> list[dict[str, Any]]:
    return [{"timestamp": item.timestamp, "drawdown": item.drawdown, "equity": item.equity} for item in equity_curve]


def daily_results(trades: list[PaperTrade], initial_capital: float) -> list[dict[str, Any]]:
    grouped: dict[Any, float] = defaultdict(float)
    for trade in trades:
        grouped[trade.exit_time.date()] += trade.net_pnl
    return [{"date": key.isoformat(), "net_pnl": value, "return": value / initial_capital} for key, value in sorted(grouped.items())]


def monthly_results(trades: list[PaperTrade], initial_capital: float) -> list[dict[str, Any]]:
    grouped: dict[str, float] = defaultdict(float)
    for trade in trades:
        grouped[trade.exit_time.strftime("%Y-%m")] += trade.net_pnl
    return [{"month": key, "net_pnl": value, "return": value / initial_capital} for key, value in sorted(grouped.items())]


def signal_analysis(predictions: list[PredictionResult], trades: list[PaperTrade]) -> dict[str, Any]:
    by_decision = Counter(prediction.decision for prediction in predictions)
    by_confidence = Counter(_confidence_bucket(prediction.confidence) for prediction in predictions)
    by_exit = Counter(trade.exit_reason for trade in trades)
    by_weekday = Counter(trade.exit_time.strftime("%A") for trade in trades)
    by_hour = Counter(str(trade.exit_time.hour) for trade in trades)
    return {
        "by_decision": dict(by_decision),
        "by_confidence": dict(by_confidence),
        "by_exit_reason": dict(by_exit),
        "by_day_of_week": dict(by_weekday),
        "by_hour": dict(by_hour),
        "by_volatility_regime": {},
    }


def _snapshot_returns(equity_curve: list[PortfolioSnapshot]) -> list[float]:
    returns: list[float] = []
    previous = None
    for snapshot in equity_curve:
        if previous is not None and previous > 0:
            returns.append(snapshot.equity / previous - 1)
        previous = snapshot.equity
    return returns


def _ratio(values: list[float], *, sample: list[float] | None = None) -> float:
    denominator_sample = values if sample is None else sample
    if len(values) < 2 or len(denominator_sample) < 2:
        return 0.0
    denominator = pstdev(denominator_sample)
    if denominator == 0:
        return 0.0
    return mean(values) / denominator


def _annualized_return(initial: float, final: float, start: datetime | None, end: datetime | None) -> float:
    if not start or not end or final <= 0 or initial <= 0 or end <= start:
        return 0.0
    years = (end - start).total_seconds() / (365.25 * 24 * 60 * 60)
    if years <= 0:
        return 0.0
    return (final / initial) ** (1 / years) - 1


def _calmar(initial: float, final: float, start: datetime | None, end: datetime | None, max_drawdown: float) -> float:
    if max_drawdown == 0:
        return math.inf if final > initial else 0.0
    return _annualized_return(initial, final, start, end) / max_drawdown


def _average_exposure(equity_curve: list[PortfolioSnapshot]) -> float:
    if not equity_curve:
        return 0.0
    exposed = [1.0 if snapshot.invested_capital > 0 else 0.0 for snapshot in equity_curve]
    return mean(exposed)


def _trade_notional(trade: PaperTrade) -> float:
    return trade.entry_price * trade.quantity + trade.exit_price * trade.quantity


def _confidence_bucket(value: float) -> str:
    if value >= 0.85:
        return "0.85-1.00"
    if value >= 0.70:
        return "0.70-0.85"
    if value >= 0.55:
        return "0.55-0.70"
    return "0.00-0.55"
