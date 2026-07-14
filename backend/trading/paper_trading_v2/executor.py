from __future__ import annotations

import hashlib
import re

from backend.trading.prediction_engine.decision import BUY_CANDIDATE
from backend.trading.prediction_engine.models import PredictionResult

from .config import DEFAULT_CONFIG, PaperTradingConfig
from .models import ExecutionResult, MarketCandle, PaperPosition, PaperTrade, PortfolioState, TargetRules
from .portfolio import PortfolioManager
from .risk import PaperRiskManager


class PaperTradingExecutor:
    def __init__(
        self,
        config: PaperTradingConfig = DEFAULT_CONFIG,
        risk_manager: PaperRiskManager | None = None,
        portfolio_manager: PortfolioManager | None = None,
    ) -> None:
        self.config = config
        self.risk = risk_manager or PaperRiskManager(config)
        self.portfolio = portfolio_manager or PortfolioManager(config)

    def execute(
        self,
        *,
        prediction: PredictionResult,
        entry_candle: MarketCandle,
        future_candles: list[MarketCandle],
        portfolio: PortfolioState,
        candle_index: int = 0,
    ) -> ExecutionResult:
        self.risk.validate_prediction(prediction)
        if prediction.decision != BUY_CANDIDATE:
            return ExecutionResult(None, None, portfolio, f"decision_{prediction.decision.lower()}")

        allowed, reason = self.risk.can_open(portfolio=portfolio, prediction=prediction, candle_index=candle_index)
        if not allowed:
            return ExecutionResult(None, None, portfolio, reason)

        notional = self.risk.position_notional(portfolio)
        if notional <= 0:
            return ExecutionResult(None, None, portfolio, "insufficient_cash")

        entry_price = self._entry_price(entry_candle.close)
        entry_fee = self._fee(notional)
        quantity = notional / entry_price
        target_rules = parse_target_name(prediction.target_name)
        position = PaperPosition(
            position_id=_position_id(prediction.prediction_id, prediction.model_version),
            symbol=prediction.symbol,
            interval=prediction.interval,
            model=prediction.model_name,
            target=prediction.target_name,
            prediction_id=prediction.prediction_id,
            candle_id=prediction.candle_id,
            entry_price=entry_price,
            entry_time=entry_candle.open_time,
            quantity=quantity,
            notional=notional,
            entry_fee=entry_fee,
            confidence=prediction.confidence,
            take_profit_probability=prediction.probability_take_profit,
            stop_loss_probability=prediction.probability_stop_loss,
            neutral_probability=prediction.probability_neutral,
            model_version=prediction.model_version,
            feature_version=prediction.feature_version,
            target_version=target_rules.target_version,
        )
        self.portfolio.open_position(portfolio, position)
        portfolio.last_trade_index[prediction.symbol] = candle_index
        trade = self.close_when_triggered(position=position, candles=future_candles, target_rules=target_rules)
        if trade is not None:
            self.portfolio.close_position(portfolio, position, trade)
        return ExecutionResult(position, trade, portfolio, "opened")

    def close_when_triggered(
        self,
        *,
        position: PaperPosition,
        candles: list[MarketCandle],
        target_rules: TargetRules,
    ) -> PaperTrade | None:
        if not candles:
            return None
        take_profit_price = position.entry_price * (1 + target_rules.take_profit_pct)
        stop_loss_price = position.entry_price * (1 - target_rules.stop_loss_pct)
        usable = candles[: target_rules.horizon_candles]
        for index, candle in enumerate(usable, start=1):
            if candle.open_time <= position.entry_time:
                continue
            if candle.low <= stop_loss_price:
                return self._close(position, candle, stop_loss_price, "STOP_LOSS", index)
            if candle.high >= take_profit_price:
                return self._close(position, candle, take_profit_price, "TAKE_PROFIT", index)
        if usable:
            candle = usable[-1]
            return self._close(position, candle, candle.close, "HORIZON_EXPIRATION", len(usable))
        return None

    def _close(self, position: PaperPosition, candle: MarketCandle, raw_exit_price: float, reason: str, holding_candles: int) -> PaperTrade:
        exit_price = self._exit_price(raw_exit_price)
        gross_pnl = (exit_price - position.entry_price) * position.quantity
        exit_fee = self._fee(exit_price * position.quantity)
        fees = position.entry_fee + exit_fee
        net_pnl = gross_pnl - fees
        return PaperTrade(
            position_id=position.position_id,
            prediction_id=position.prediction_id,
            symbol=position.symbol,
            interval=position.interval,
            entry_price=position.entry_price,
            exit_price=exit_price,
            quantity=position.quantity,
            entry_time=position.entry_time,
            exit_time=candle.open_time,
            exit_reason=reason,
            gross_pnl=gross_pnl,
            fees=fees,
            net_pnl=net_pnl,
            return_pct=net_pnl / position.notional if position.notional else 0.0,
            holding_candles=holding_candles,
        )

    def _entry_price(self, close: float) -> float:
        return close * (1 + (self.config.spread_bps / 2 + self.config.slippage_bps) / 10_000)

    def _exit_price(self, price: float) -> float:
        return price * (1 - (self.config.spread_bps / 2 + self.config.slippage_bps) / 10_000)

    def _fee(self, notional: float) -> float:
        return notional * self.config.fee_bps / 10_000


def parse_target_name(target_name: str) -> TargetRules:
    match = re.fullmatch(r"(v\d+)_(long|short)_tp_(\d+)bps_sl_(\d+)bps_h_(\d+)", target_name)
    if not match:
        raise ValueError(f"Unsupported target_name format: {target_name}")
    version, side, tp_bps, sl_bps, horizon = match.groups()
    if side != "long":
        raise ValueError("Paper Trading V2 currently supports long targets only.")
    return TargetRules(
        side=side,
        take_profit_pct=int(tp_bps) / 10_000,
        stop_loss_pct=int(sl_bps) / 10_000,
        horizon_candles=int(horizon),
        target_version=version,
    )


def _position_id(prediction_id: str, model_version: str) -> str:
    return hashlib.sha256(f"{prediction_id}|{model_version}".encode("utf-8")).hexdigest()[:32]
