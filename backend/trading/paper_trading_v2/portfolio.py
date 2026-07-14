from __future__ import annotations

from datetime import datetime

from .config import DEFAULT_CONFIG, PaperTradingConfig
from .models import PaperPosition, PaperTrade, PortfolioSnapshot, PortfolioState


class PortfolioManager:
    def __init__(self, config: PaperTradingConfig = DEFAULT_CONFIG) -> None:
        self.config = config

    def initial_state(self) -> PortfolioState:
        return PortfolioState(
            initial_capital=self.config.initial_capital,
            cash=self.config.initial_capital,
            equity=self.config.initial_capital,
            peak_equity=self.config.initial_capital,
        )

    def open_position(self, portfolio: PortfolioState, position: PaperPosition) -> None:
        portfolio.cash -= position.notional + position.entry_fee
        portfolio.invested_capital += position.notional
        portfolio.positions.append(position)
        portfolio.executed_keys.add((position.symbol, position.interval, position.candle_id, position.model_version))
        self.mark_to_market(portfolio, timestamp=position.entry_time)

    def close_position(self, portfolio: PortfolioState, position: PaperPosition, trade: PaperTrade) -> None:
        position.status = "CLOSED"
        portfolio.cash += trade.exit_price * trade.quantity - (trade.fees - position.entry_fee)
        portfolio.invested_capital = max(portfolio.invested_capital - position.notional, 0.0)
        portfolio.cumulative_profit += trade.net_pnl
        portfolio.trades.append(trade)
        day = trade.exit_time.date()
        portfolio.daily_results[day] = portfolio.daily_results.get(day, 0.0) + trade.net_pnl
        self.mark_to_market(portfolio, timestamp=trade.exit_time)

    def mark_to_market(self, portfolio: PortfolioState, *, timestamp: datetime, last_price: float | None = None) -> PortfolioSnapshot:
        open_value = 0.0
        if last_price is not None:
            open_value = sum(position.quantity * last_price for position in portfolio.positions if position.status == "OPEN")
        else:
            open_value = sum(position.notional for position in portfolio.positions if position.status == "OPEN")
        portfolio.equity = portfolio.cash + open_value
        portfolio.peak_equity = max(portfolio.peak_equity, portfolio.equity)
        drawdown = 0.0 if portfolio.peak_equity <= 0 else (portfolio.peak_equity - portfolio.equity) / portfolio.peak_equity
        portfolio.max_drawdown = max(portfolio.max_drawdown, drawdown)
        snapshot = PortfolioSnapshot(
            timestamp=timestamp,
            cash=portfolio.cash,
            equity=portfolio.equity,
            invested_capital=portfolio.invested_capital,
            cumulative_profit=portfolio.cumulative_profit,
            drawdown=drawdown,
            daily_return=portfolio.daily_results.get(timestamp.date(), 0.0) / portfolio.initial_capital,
            total_return=(portfolio.equity - portfolio.initial_capital) / portfolio.initial_capital,
        )
        portfolio.equity_curve.append(snapshot)
        return snapshot
