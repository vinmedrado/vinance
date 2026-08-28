from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterator

from backend.trading.paper_trading_v2.executor import PaperTradingExecutor, parse_target_name
from backend.trading.paper_trading_v2.models import (
    ExecutionResult,
    MarketCandle,
    PaperPosition,
    PaperTrade,
    PortfolioSnapshot,
    PortfolioState,
    TargetRules,
)
from backend.trading.paper_trading_v2.portfolio import PortfolioManager
from backend.trading.prediction_engine.models import PredictionResult

from .config import BEST_CASE, STOP_LOSS_FIRST, TAKE_PROFIT_FIRST, WORST_CASE
from .models import HistoricalCandle


class ConsolidatedPortfolioManager(PortfolioManager):
    """Keeps Paper Trading V2 state transitions but records one snapshot per candle."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._record_snapshots = False

    @contextmanager
    def recording_snapshot(self) -> Iterator[None]:
        previous = self._record_snapshots
        self._record_snapshots = True
        try:
            yield
        finally:
            self._record_snapshots = previous

    def mark_to_market(
        self,
        portfolio: PortfolioState,
        *,
        timestamp: datetime,
        last_price: float | None = None,
    ) -> PortfolioSnapshot:
        previous_peak = portfolio.peak_equity
        previous_max_drawdown = portfolio.max_drawdown
        snapshot = super().mark_to_market(portfolio, timestamp=timestamp, last_price=last_price)
        if not self._record_snapshots:
            portfolio.equity_curve.pop()
            portfolio.peak_equity = previous_peak
            portfolio.max_drawdown = previous_max_drawdown
        return snapshot

    def record_candle_snapshot(
        self,
        portfolio: PortfolioState,
        *,
        candle: MarketCandle,
    ) -> PortfolioSnapshot:
        with self.recording_snapshot():
            return self.mark_to_market(portfolio, timestamp=candle.open_time, last_price=candle.close)


class BacktestingPaperExecutor(PaperTradingExecutor):
    def __init__(self, *args, intracandle_policy: str = STOP_LOSS_FIRST, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.intracandle_policy = intracandle_policy

    def close_on_candle(
        self,
        *,
        position: PaperPosition,
        candle: MarketCandle,
        holding_candles: int,
    ) -> PaperTrade | None:
        if holding_candles <= 0 or candle.open_time <= position.entry_time:
            return None
        target_rules = parse_target_name(position.target)
        take_profit_price = position.entry_price * (1 + target_rules.take_profit_pct)
        stop_loss_price = position.entry_price * (1 - target_rules.stop_loss_pct)
        hit_tp = candle.high >= take_profit_price
        hit_sl = candle.low <= stop_loss_price
        if hit_tp and hit_sl:
            reason, price = self._resolve_intracandle(position, take_profit_price, stop_loss_price)
            return self._close(position, candle, price, reason, holding_candles)
        if hit_sl:
            return self._close(position, candle, stop_loss_price, "STOP_LOSS", holding_candles)
        if hit_tp:
            return self._close(position, candle, take_profit_price, "TAKE_PROFIT", holding_candles)
        if holding_candles >= target_rules.horizon_candles:
            return self._close(position, candle, candle.close, "HORIZON_EXPIRATION", holding_candles)
        return None

    def close_when_triggered(
        self,
        *,
        position: PaperPosition,
        candles: list[MarketCandle],
        target_rules: TargetRules,
    ) -> PaperTrade | None:
        for holding_candles, candle in enumerate(candles[: target_rules.horizon_candles], start=1):
            trade = self.close_on_candle(
                position=position,
                candle=candle,
                holding_candles=holding_candles,
            )
            if trade is not None:
                return trade
        return None

    def _resolve_intracandle(self, position: PaperPosition, tp_price: float, sl_price: float) -> tuple[str, float]:
        if self.intracandle_policy in {STOP_LOSS_FIRST, WORST_CASE}:
            return "STOP_LOSS", sl_price
        if self.intracandle_policy in {TAKE_PROFIT_FIRST, BEST_CASE}:
            return "TAKE_PROFIT", tp_price
        raise ValueError(f"Unsupported intracandle_policy: {self.intracandle_policy}")


@dataclass(frozen=True)
class CandleSimulationResult:
    opened_position: PaperPosition | None
    closed_trades: tuple[PaperTrade, ...]
    reason: str


class BacktestSimulator:
    def __init__(self, config) -> None:
        self.config = config
        self.portfolio = ConsolidatedPortfolioManager(config.paper_config)
        self.executor = BacktestingPaperExecutor(
            config.paper_config,
            intracandle_policy=config.intracandle_policy,
            portfolio_manager=self.portfolio,
        )
        self._entry_indexes: dict[str, int] = {}
        self._active_positions: dict[str, PaperPosition] = {}

    def initial_state(self) -> PortfolioState:
        self._entry_indexes.clear()
        self._active_positions.clear()
        return self.portfolio.initial_state()

    def process_candle(
        self,
        *,
        portfolio: PortfolioState,
        candle: HistoricalCandle | MarketCandle,
        candle_index: int,
        prediction: PredictionResult | None = None,
    ) -> CandleSimulationResult:
        market_candle = candle.candle if isinstance(candle, HistoricalCandle) else candle
        closed: list[PaperTrade] = []

        for position in list(self._active_positions.values()):
            entry_index = self._entry_indexes[position.position_id]
            trade = self.executor.close_on_candle(
                position=position,
                candle=market_candle,
                holding_candles=candle_index - entry_index,
            )
            if trade is not None:
                self.portfolio.close_position(portfolio, position, trade)
                self._entry_indexes.pop(position.position_id, None)
                self._active_positions.pop(position.position_id, None)
                closed.append(trade)

        # Position sizing for a new signal sees exits and current candle prices,
        # but this intermediate state is not emitted as a separate snapshot.
        self.portfolio.mark_to_market(
            portfolio,
            timestamp=market_candle.open_time,
            last_price=market_candle.close,
        )

        opened = None
        reason = "no_prediction"
        try:
            if prediction is not None:
                execution: ExecutionResult = self.executor.execute(
                    prediction=prediction,
                    entry_candle=market_candle,
                    future_candles=[],
                    portfolio=portfolio,
                    candle_index=candle_index,
                )
                opened = execution.opened_position
                reason = execution.reason
                if opened is not None:
                    self._entry_indexes[opened.position_id] = candle_index
                    self._active_positions[opened.position_id] = opened
        finally:
            self.portfolio.record_candle_snapshot(portfolio, candle=market_candle)
        return CandleSimulationResult(opened, tuple(closed), reason)

    def execute_signal(
        self,
        *,
        prediction: PredictionResult,
        candle,
        future_candles,
        portfolio: PortfolioState,
        candle_index: int = 0,
    ) -> ExecutionResult:
        entry = candle.candle if isinstance(candle, HistoricalCandle) else candle
        opened = self.process_candle(
            portfolio=portfolio,
            candle=entry,
            candle_index=candle_index,
            prediction=prediction,
        )
        closed_trade = None
        for offset, future in enumerate(future_candles, start=1):
            future_candle = future.candle if isinstance(future, HistoricalCandle) else future
            outcome = self.process_candle(
                portfolio=portfolio,
                candle=future_candle,
                candle_index=candle_index + offset,
            )
            if outcome.closed_trades:
                closed_trade = outcome.closed_trades[0]
                break
        return ExecutionResult(opened.opened_position, closed_trade, portfolio, opened.reason)


def equity_temporal_integrity(equity_curve: list[PortfolioSnapshot]) -> dict[str, int | bool]:
    timestamps = [snapshot.timestamp for snapshot in equity_curve]
    regressions = sum(current < previous for previous, current in zip(timestamps, timestamps[1:]))
    duplicate_timestamps = len(timestamps) - len(set(timestamps))
    return {
        "equity_records_total": len(timestamps),
        "equity_unique_timestamps": len(set(timestamps)),
        "equity_duplicate_timestamps": duplicate_timestamps,
        "equity_time_regressions": regressions,
        "temporal_integrity_valid": regressions == 0,
    }


def validate_temporal_integrity(equity_curve: list[PortfolioSnapshot]) -> dict[str, int | bool]:
    integrity = equity_temporal_integrity(equity_curve)
    if not integrity["temporal_integrity_valid"]:
        raise ValueError(
            "Equity curve contains temporal regressions: "
            f"{integrity['equity_time_regressions']}"
        )
    return integrity


def horizon_for_target(target_name: str) -> int:
    return parse_target_name(target_name).horizon_candles


def future_window(
    candles: tuple[HistoricalCandle, ...] | list[HistoricalCandle],
    index: int,
    target_name: str,
) -> tuple[HistoricalCandle, ...]:
    horizon = horizon_for_target(target_name)
    return tuple(candles[index + 1 : index + 1 + horizon])
