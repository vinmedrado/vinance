from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any


@dataclass(frozen=True)
class MarketCandle:
    candle_id: int
    symbol: str
    interval: str
    open_time: datetime
    open: float
    high: float
    low: float
    close: float


@dataclass(frozen=True)
class TargetRules:
    side: str
    take_profit_pct: float
    stop_loss_pct: float
    horizon_candles: int
    target_version: str


@dataclass
class PaperPosition:
    position_id: str
    symbol: str
    interval: str
    model: str
    target: str
    prediction_id: str
    candle_id: int
    entry_price: float
    entry_time: datetime
    quantity: float
    notional: float
    entry_fee: float
    confidence: float
    take_profit_probability: float
    stop_loss_probability: float
    neutral_probability: float
    model_version: str
    feature_version: str
    target_version: str
    status: str = "OPEN"


@dataclass
class PaperTrade:
    position_id: str
    prediction_id: str
    symbol: str
    interval: str
    entry_price: float
    exit_price: float
    quantity: float
    entry_time: datetime
    exit_time: datetime
    exit_reason: str
    gross_pnl: float
    fees: float
    net_pnl: float
    return_pct: float
    holding_candles: int


@dataclass
class PortfolioSnapshot:
    timestamp: datetime
    cash: float
    equity: float
    invested_capital: float
    cumulative_profit: float
    drawdown: float
    daily_return: float
    total_return: float


@dataclass
class PortfolioState:
    initial_capital: float
    cash: float
    equity: float
    invested_capital: float = 0.0
    cumulative_profit: float = 0.0
    peak_equity: float = 0.0
    max_drawdown: float = 0.0
    positions: list[PaperPosition] = field(default_factory=list)
    trades: list[PaperTrade] = field(default_factory=list)
    equity_curve: list[PortfolioSnapshot] = field(default_factory=list)
    daily_results: dict[date, float] = field(default_factory=dict)
    last_trade_index: dict[str, int] = field(default_factory=dict)
    executed_keys: set[tuple[str, str, int, str]] = field(default_factory=set)


@dataclass(frozen=True)
class ExecutionResult:
    opened_position: PaperPosition | None
    closed_trade: PaperTrade | None
    portfolio: PortfolioState
    reason: str
    reports: dict[str, Any] = field(default_factory=dict)
