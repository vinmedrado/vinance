from __future__ import annotations

from backend.trading.prediction_engine.models import PredictionResult

from .config import DEFAULT_CONFIG, PaperTradingConfig
from .models import PortfolioState


class PaperRiskManager:
    def __init__(self, config: PaperTradingConfig = DEFAULT_CONFIG) -> None:
        self.config = config

    def validate_prediction(self, prediction: PredictionResult) -> None:
        if not self.config.paper_only or prediction.reason.get("paper_only") is not True:
            raise RuntimeError("Paper Trading V2 requires PAPER_ONLY predictions.")
        if prediction.feature_version != self.config.feature_version:
            raise ValueError(f"feature_version must be {self.config.feature_version}; found {prediction.feature_version}")
        target_version = str(prediction.target_name).split("_", 1)[0]
        if target_version != self.config.target_version:
            raise ValueError(f"target_version must be {self.config.target_version}; found {target_version}")
        if not prediction.model_version:
            raise ValueError("Prediction model_version is required.")
        if prediction.confidence < self.config.min_confidence:
            raise ValueError(
                f"Prediction confidence {prediction.confidence:.6f} below minimum {self.config.min_confidence:.6f}"
            )

    def can_open(
        self,
        *,
        portfolio: PortfolioState,
        prediction: PredictionResult,
        candle_index: int,
    ) -> tuple[bool, str]:
        key = (prediction.symbol, prediction.interval, prediction.candle_id, prediction.model_version)
        if key in portfolio.executed_keys:
            return False, "duplicate_prediction"
        if len([position for position in portfolio.positions if position.status == "OPEN"]) >= self.config.max_open_positions:
            return False, "max_open_positions"
        last_index = portfolio.last_trade_index.get(prediction.symbol)
        if last_index is not None and candle_index - last_index <= self.config.cooldown_candles:
            return False, "cooldown"
        today_loss = abs(min(portfolio.daily_results.get(prediction.open_time.date(), 0.0), 0.0))
        if portfolio.initial_capital > 0 and today_loss / portfolio.initial_capital >= self.config.max_daily_loss:
            return False, "max_daily_loss"
        return True, "allowed"

    def position_notional(self, portfolio: PortfolioState) -> float:
        equity_limit = portfolio.equity * min(
            self.config.fixed_fraction,
            self.config.max_position_size,
            self.config.max_capital_per_trade,
        )
        return max(min(equity_limit, portfolio.cash), 0.0)
